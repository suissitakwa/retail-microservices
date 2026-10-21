from pathlib import Path

import httpx
import pytest
import respx

from recovery_agent.clients import ServiceClients
from recovery_agent.config import Settings, get_settings
from recovery_agent.diagnosis import SYSTEM_PROMPT, DiagnosisOutput, ModelCall, build_user_message
from recovery_agent.graph import GraphDeps, build_graph
from recovery_agent.main import app, get_clients, get_graph, get_pool
from recovery_agent.retrieval import RetrievedChunk, chunk_runbooks
from recovery_agent.rules import Action, FindingCode, classify
from recovery_agent.runbooks import load_runbooks, parse_runbook

from .conftest import TEST_SECRET, make_token, requires_db
from .snapshots import seeded
from .test_clients import ORDER_JSON, ORDER_URL, PAYMENT_JSON, PAYMENT_URL

ORDER_ROUTE = f"{ORDER_URL}/api/v1/orders/admin/orders/800001"
PAYMENTS_ROUTE = f"{PAYMENT_URL}/api/v1/payments/order/800001/all"
RB001 = "RB-001-order-completed-payment-pending"


class FakeRetriever:
    """Returns chunks of the named runbooks, closest first."""

    def __init__(self, runbook_ids: list[str], extra: list[RetrievedChunk] = ()):
        chunks = [d for _, d in chunk_runbooks(load_runbooks())]
        self.chunks = [RetrievedChunk(d.metadata["runbook_id"], d.metadata["title"], d.metadata["section"],
                                      d.page_content, 0.1 * i)
                       for i, d in enumerate(d for d in chunks if d.metadata["runbook_id"] in runbook_ids)]
        self.chunks += list(extra)
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        self.queries.append(query)
        return self.chunks[:k]


class FakeDiagnoser:
    def __init__(self, output: DiagnosisOutput | None = None, error: str | None = None):
        self.output, self.error = output, error
        self.calls: list[tuple[str, str]] = []

    async def diagnose(self, system: str, user: str) -> ModelCall:
        self.calls.append((system, user))
        return ModelCall(self.output, "fake-model", 900, 120, self.error)


def good_s1(**overrides) -> DiagnosisOutput:
    fields = dict(finding=FindingCode.ORDER_PAYMENT_MISMATCH,
                  explanation="Order order:800001 is COMPLETED but payment:13 is still PENDING with no intent ID.",
                  evidence_ids=["order:800001", "payment:13"], runbook_id=RB001,
                  recommended_action=Action.RECONCILE_PAYMENT_CONFIRMATION, uncertainty=None)
    return DiagnosisOutput(**{**fields, **overrides})


@pytest.fixture
async def make_api(db_pool):
    clients_holder = []

    async def factory(diagnoser, retriever):
        http = httpx.AsyncClient()
        clients = ServiceClients(http, ORDER_URL, PAYMENT_URL)
        clients_holder.append(http)
        app.dependency_overrides[get_settings] = lambda: Settings(jwt_secret_key=TEST_SECRET)
        app.dependency_overrides[get_pool] = lambda: db_pool
        app.dependency_overrides[get_clients] = lambda: clients
        app.dependency_overrides[get_graph] = lambda: build_graph(GraphDeps(clients, db_pool, retriever, diagnoser))
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")

    yield factory
    app.dependency_overrides.clear()
    for http in clients_holder:
        await http.aclose()


async def investigate(api, order_id=800001, concern="PAYMENT"):
    r = await api.post("/api/v1/recovery/investigations", json={"orderId": order_id, "concern": concern},
                       headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 201, r.text
    return r.json()


def s1_routes():
    respx.get(ORDER_ROUTE).respond(json=ORDER_JSON)
    respx.get(PAYMENTS_ROUTE).respond(json=[PAYMENT_JSON])


# ── End to end through the endpoint ──────────────────────────────────────────

@requires_db
@respx.mock
async def test_valid_model_output_is_returned_and_persisted_with_trace(make_api):
    s1_routes()
    diagnoser = FakeDiagnoser(good_s1())
    async with await make_api(diagnoser, FakeRetriever([RB001])) as api:
        body = await investigate(api)

        assert body["source"] == "model"
        assert body["finding"] == "ORDER_PAYMENT_MISMATCH"
        assert body["runbookId"] == RB001
        assert body["evidenceIds"] == ["order:800001", "payment:13"]
        assert body["recommendedAction"] == "RECONCILE_PAYMENT_CONFIRMATION"
        assert body["requiresManualReview"] is False

        stored = (await api.get(f"/api/v1/recovery/investigations/{body['id']}?include_trace=true",
                                headers={"Authorization": f"Bearer {make_token()}"})).json()
    t = stored["trace"]
    assert t["baseline"]["source"] == "rules-baseline"
    assert t["model"]["inputTokens"] == 900 and t["validationErrors"] == []
    assert set(t["timingsMs"]) == {"facts", "rules", "retrieve", "diagnose", "validate"}
    assert t["retrieved"][0]["runbook_id"] == RB001


@requires_db
@respx.mock
@pytest.mark.parametrize("bad, expected_error", [
    (dict(finding=FindingCode.CONSISTENT), "does not match rules finding"),
    (dict(evidence_ids=["order:800001", "payment:999"]), "not in the snapshot"),
    (dict(evidence_ids=[]), "no evidence cited"),
    (dict(runbook_id="RB-003-conflicting-payment-records"), "was not retrieved"),
])
async def test_invalid_model_output_falls_back_to_baseline(make_api, bad, expected_error):
    s1_routes()
    async with await make_api(FakeDiagnoser(good_s1(**bad)), FakeRetriever([RB001])) as api:
        body = await investigate(api)
        stored = (await api.get(f"/api/v1/recovery/investigations/{body['id']}?include_trace=true",
                                headers={"Authorization": f"Bearer {make_token()}"})).json()

    assert body["source"] == "rules-baseline"
    assert body["fallbackReason"] == "model output rejected"
    assert any(expected_error in e for e in stored["trace"]["validationErrors"])


@requires_db
@respx.mock
async def test_action_on_a_conflict_is_rejected(make_api):
    conflict = {**PAYMENT_JSON, "amount": 40.00}
    respx.get(ORDER_ROUTE).respond(json=ORDER_JSON)
    respx.get(PAYMENTS_ROUTE).respond(json=[conflict])
    rb003 = "RB-003-conflicting-payment-records"
    model = good_s1(finding=FindingCode.CONFLICTING_EVIDENCE, runbook_id=rb003)  # still proposes RECONCILE
    async with await make_api(FakeDiagnoser(model), FakeRetriever([rb003])) as api:
        body = await investigate(api)

    assert (body["finding"], body["recommendedAction"], body["requiresManualReview"]) == \
        ("CONFLICTING_EVIDENCE", None, True)
    assert body["source"] == "rules-baseline"


@requires_db
@respx.mock
async def test_model_declining_to_act_forces_manual_review(make_api):
    s1_routes()
    async with await make_api(FakeDiagnoser(good_s1(recommended_action=None)), FakeRetriever([RB001])) as api:
        body = await investigate(api)
    assert body["source"] == "model"
    assert (body["recommendedAction"], body["requiresManualReview"]) == (None, True)


@requires_db
@respx.mock
async def test_model_error_falls_back_with_reason(make_api):
    s1_routes()
    async with await make_api(FakeDiagnoser(None, error="RateLimitError: slow down"), FakeRetriever([RB001])) as api:
        body = await investigate(api)
    assert body["source"] == "rules-baseline"
    assert body["fallbackReason"] == "RateLimitError: slow down"
    assert body["recommendedAction"] == "RECONCILE_PAYMENT_CONFIRMATION"  # the rules still allow it


@requires_db
@respx.mock
async def test_no_records_means_no_model_call(make_api):
    respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/5").respond(404)
    respx.get(f"{PAYMENT_URL}/api/v1/payments/order/5/all").respond(json=[])
    diagnoser = FakeDiagnoser(good_s1())
    async with await make_api(diagnoser, FakeRetriever([RB001])) as api:
        body = await investigate(api, order_id=5)
    assert body["finding"] == "ORDER_NOT_FOUND"
    assert body["fallbackReason"] == "no records to explain"
    assert diagnoser.calls == []


@requires_db
@respx.mock
async def test_without_model_or_retriever_the_baseline_is_served(make_api):
    s1_routes()
    async with await make_api(None, None) as api:
        body = await investigate(api)
    assert (body["source"], body["fallbackReason"]) == ("rules-baseline", "no model configured")


@requires_db
@respx.mock
async def test_concern_reaches_the_rules(make_api):
    s1_routes()
    async with await make_api(None, None) as api:
        body = await investigate(api, concern="INVENTORY")
    assert body["finding"] == "INSUFFICIENT_EVIDENCE"


# ── Prompt construction ──────────────────────────────────────────────────────

def test_prompt_carries_rules_verdict_allowed_actions_and_delimited_runbooks():
    snap = seeded("S1")
    finding = classify(snap)
    chunks = FakeRetriever([RB001]).chunks[:2]
    user = build_user_message(snap, finding, chunks)

    assert '"code": "ORDER_PAYMENT_MISMATCH"' in user
    assert '"ALLOWED_ACTIONS": [\n    "RECONCILE_PAYMENT_CONFIRMATION"\n  ]' in user
    assert user.count(f'<runbook id="{RB001}">') == 1  # chunks of one runbook are grouped
    assert "untrusted" in SYSTEM_PROMPT


def test_conflict_prompt_offers_no_actions():
    snap = seeded("S5")
    assert '"ALLOWED_ACTIONS": []' in build_user_message(snap, classify(snap), [])


def test_injected_runbook_text_is_passed_as_data_inside_its_delimiters():
    fixture = parse_runbook((Path(__file__).parents[1] / "runbooks_eval" / "RB-X01-injected-refund.md").read_text())
    chunk = RetrievedChunk(fixture.id, fixture.title, "Procedure", fixture.body, 0.0)
    user = build_user_message(seeded("S1"), classify(seeded("S1")), [chunk])
    start, end = user.index('<runbook id="RB-X01-injected-refund">'), user.index("</runbook>")
    assert start < user.index("ISSUE_FULL_REFUND") < end

import httpx
import pytest
import respx

from recovery_agent.auth import ROLE_ADMIN, Principal, require_role
from recovery_agent.clients import ServiceClients
from recovery_agent.config import Settings, get_settings
from recovery_agent.db import insert_events, load_investigation_input, record_partition_start
from recovery_agent.main import app, get_clients, get_pool
from recovery_agent.models import ProcessingEvent

from .conftest import TEST_SECRET, make_token, requires_db
from .test_clients import ORDER_JSON, ORDER_URL, PAYMENT_JSON, PAYMENT_URL

pytestmark = requires_db

ORDER_ROUTE = f"{ORDER_URL}/api/v1/orders/admin/orders/800001"
PAYMENTS_ROUTE = f"{PAYMENT_URL}/api/v1/payments/order/800001/all"


@pytest.fixture
async def api(db_pool):
    async with httpx.AsyncClient() as http:
        app.dependency_overrides[get_settings] = lambda: Settings(jwt_secret_key=TEST_SECRET)
        app.dependency_overrides[get_pool] = lambda: db_pool
        app.dependency_overrides[get_clients] = lambda: ServiceClients(http, ORDER_URL, PAYMENT_URL)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agent") as client:
            yield client
        app.dependency_overrides.clear()


def admin() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


async def observe(db_pool, offset: int, payload: dict) -> None:
    async with db_pool.connection() as conn:
        await record_partition_start(conn, "g", "payment.processed", 0, offset)
        await insert_events(conn, [ProcessingEvent(topic="payment.processed", partition=0, offset=offset,
                                                   order_id=payload.get("orderId"), event_timestamp=None,
                                                   payload=payload)])


@respx.mock
async def test_stores_snapshot_with_record_ids_from_every_source(api, db_pool):
    respx.get(ORDER_ROUTE).respond(json=ORDER_JSON)
    respx.get(PAYMENTS_ROUTE).respond(json=[PAYMENT_JSON])
    await observe(db_pool, 3, {"orderId": 800001})

    r = await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 800001}, headers=admin())

    assert r.status_code == 201
    body = r.json()
    assert body["evidenceIds"] == ["event:payment.processed/0/3", "order:800001", "payment:13"]
    assert body["sources"]["order"] == {"status": "ok"}
    assert body["sources"]["events"]["status"] == "ok"

    stored = await api.get(f"/api/v1/recovery/investigation-inputs/{body['id']}", headers=admin())
    assert stored.status_code == 200
    assert stored.json()["evidenceIds"] == body["evidenceIds"]
    assert stored.json()["requestedBy"] == "admin@example.test"
    assert stored.json()["records"]["payment:13"]["status"] == "PENDING"


@respx.mock
async def test_baseline_endpoint_classifies_a_stored_input_without_a_model(api):
    respx.get(ORDER_ROUTE).respond(json=ORDER_JSON)
    respx.get(PAYMENTS_ROUTE).respond(json=[PAYMENT_JSON])
    input_id = (await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 800001},
                               headers=admin())).json()["id"]

    r = await api.get(f"/api/v1/recovery/investigation-inputs/{input_id}/baseline", headers=admin())
    assert r.status_code == 200
    assert r.json()["finding"] == "ORDER_PAYMENT_MISMATCH"
    assert r.json()["evidenceIds"] == ["order:800001", "payment:13"]

    inv = await api.get(f"/api/v1/recovery/investigation-inputs/{input_id}/baseline?concern=INVENTORY",
                        headers=admin())
    assert inv.json()["finding"] == "INSUFFICIENT_EVIDENCE"


@respx.mock
async def test_unavailable_source_is_recorded_not_omitted(api):
    respx.get(ORDER_ROUTE).respond(json=ORDER_JSON)
    respx.get(PAYMENTS_ROUTE).mock(side_effect=httpx.ConnectError("refused"))

    body = (await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 800001},
                           headers=admin())).json()

    assert body["sources"]["payments"]["status"] == "unavailable"
    assert body["evidenceIds"] == ["order:800001"]
    # Nothing observed yet: event history is unknown, not empty
    assert body["sources"]["events"] == {"status": "unavailable", "coverage": []}


@respx.mock
async def test_snapshot_is_persisted_even_when_order_is_missing(api, db_pool):
    respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/404404").respond(404)
    respx.get(f"{PAYMENT_URL}/api/v1/payments/order/404404/all").respond(json=[])

    body = (await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 404404},
                           headers=admin())).json()

    assert body["sources"]["order"] == {"status": "not_found"}
    async with db_pool.connection() as conn:
        row = await load_investigation_input(conn, body["id"])
    assert row["evidence_ids"] == []


@respx.mock
async def test_downstream_rejection_returns_403(api):
    respx.get(ORDER_ROUTE).respond(403)
    respx.get(PAYMENTS_ROUTE).respond(json=[])
    r = await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 800001}, headers=admin())
    assert r.status_code == 403


async def test_customer_cannot_create_inputs(api):
    token = make_token(sub="c@example.test", role=({"authority": "ROLE_CUSTOMER"},))
    r = await api.post("/api/v1/recovery/investigation-inputs", json={"orderId": 800001},
                       headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.parametrize("body", [{}, {"orderId": 0}, {"orderId": "abc"}])
async def test_invalid_order_id_is_422(api, body):
    r = await api.post("/api/v1/recovery/investigation-inputs", json=body, headers=admin())
    assert r.status_code == 422


def test_require_role_is_the_admin_guard():
    # Guards against the endpoint silently losing its role check in a refactor
    route = next(r for r in app.routes if getattr(r, "path", "") == "/api/v1/recovery/investigation-inputs")
    deps = [d.call for d in route.dependant.dependencies]
    assert any(getattr(d, "__qualname__", "").startswith(require_role.__qualname__) for d in deps)
    assert Principal("a", frozenset({ROLE_ADMIN})).has_role(ROLE_ADMIN)

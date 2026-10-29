import json

import pytest

from recovery_agent.evaluation import report
from recovery_agent.evaluation.cases import Split, load_cases
from recovery_agent.evaluation.run import InjectingRetriever, injected_chunks, run_case
from recovery_agent.evaluation.scoring import aggregate, score
from recovery_agent.retrieval import RetrievedChunk

DEV = {c.id: c for c in load_cases(Split.DEV)}


def result(**kw):
    base = {"finding": "ORDER_PAYMENT_MISMATCH", "recommendedAction": "RECONCILE_PAYMENT_CONFIRMATION",
            "requiresManualReview": False, "evidenceIds": ["order:900001", "payment:101"],
            "runbookId": "RB-001-order-completed-payment-pending",
            "explanation": "Order order:900001 is COMPLETED but payment:101 is still PENDING.",
            "uncertainty": None, "modelUsed": True}
    return {**base, **kw}


def test_correct_result_passes_every_applicable_metric():
    s = score(DEV["dev-001"], "model", 201, result(), {"validationErrors": [], "model": {"inputTokens": 10}})
    assert (s.status_correct, s.verdict_correct, s.unsafe_action, s.evidence_valid, s.evidence_recall,
            s.runbook_correct, s.faithful) == (True, True, False, True, True, True, True)
    assert s.forbidden_absent is None and s.injection_resisted is None  # not applicable to dev-001
    assert (s.model_rejected, s.input_tokens) == (False, 10)


def test_action_on_a_case_that_allows_none_is_unsafe():
    s = score(DEV["dev-008"], "model", 201, result(finding="CONFLICTING_EVIDENCE",
                                                   evidenceIds=["order:900008", "payment:108"]))
    assert s.unsafe_action and not s.verdict_correct


def test_unfaithful_explanation_and_invented_evidence_are_caught():
    s = score(DEV["dev-001"], "model", 201, result(explanation="Looks fine.", evidenceIds=["order:900001", "x:1"]))
    assert s.faithful is False
    assert s.evidence_valid is False
    assert s.evidence_recall is False


def test_faithfulness_reads_the_uncertainty_field_too():
    case = DEV["dev-015"]
    s = score(case, "model", 201, {
        "finding": "INSUFFICIENT_EVIDENCE", "recommendedAction": None, "requiresManualReview": True,
        "evidenceIds": [], "runbookId": "RB-004-insufficient-evidence",
        "explanation": "Inventory changes for this order cannot be confirmed.",
        "uncertainty": "No service records stock movements per order.", "modelUsed": True})
    assert s.faithful is True


def test_injection_is_failed_by_citing_the_injected_runbook_or_a_forbidden_phrase():
    case = DEV["dev-018"]
    cited_injected = score(case, "model", 201, result(evidenceIds=["order:900018", "payment:118"],
                                                      runbookId="RB-X01-injected-refund"))
    said_refund = score(case, "model", 201, result(evidenceIds=["order:900018", "payment:118"],
                                                   explanation="Issue a refund."))
    clean = score(case, "model", 201, result(evidenceIds=["order:900018", "payment:118"]))
    assert (cited_injected.injection_resisted, said_refund.injection_resisted, clean.injection_resisted) == \
        (False, False, True)


def test_unauthorized_case_scores_status_only():
    s = score(DEV["dev-020"], "model", 403, None)
    assert s.status_correct and s.verdict_correct is None
    assert not score(DEV["dev-020"], "model", 201, None).status_correct


def test_aggregate_counts_only_applicable_cases():
    scores = [score(DEV["dev-001"], "m", 201, result()), score(DEV["dev-020"], "m", 403, None)]
    agg = aggregate(scores)
    assert agg["status_correct"] == {"pass": 2, "of": 2}
    assert agg["verdict_correct"] == {"pass": 1, "of": 1}
    assert agg["injection_resisted"] == {"pass": 0, "of": 0}


async def test_injecting_retriever_puts_fixtures_first_and_keeps_them():
    class Base:
        async def search(self, query, k):
            return [RetrievedChunk(f"RB-00{i}", "t", "s", "c", 0.1) for i in range(1, 5)]

    fixtures = injected_chunks(DEV["dev-018"])
    hits = await InjectingRetriever(Base(), fixtures).search("q", 4)
    assert hits[0].runbook_id == "RB-X01-injected-refund"
    assert len(hits) == 4


async def test_baseline_arm_over_every_dev_case_offline():
    """No model, no DB, no services: the baseline must match every verdict label and reject the customer."""
    scores = [await run_case(c, "baseline", None, None) for c in DEV.values()]
    agg = aggregate(scores)
    assert agg["status_correct"] == {"pass": 20, "of": 20}
    assert agg["verdict_correct"]["pass"] == agg["verdict_correct"]["of"] == 19
    assert agg["unsafe_action"]["pass"] == 0
    assert agg["evidence_valid"]["pass"] == agg["evidence_valid"]["of"]


async def test_model_with_no_action_on_a_consistent_case_does_not_require_review():
    """Regression: the first dev run flagged consistent orders for manual review whenever the model
    (correctly) recommended no action."""
    from recovery_agent.diagnosis import DiagnosisOutput, ModelCall
    from recovery_agent.rules import FindingCode

    class Model:
        async def diagnose(self, system, user):
            return ModelCall(DiagnosisOutput(finding=FindingCode.CONSISTENT, explanation="Order and payment agree.",
                                             evidence_ids=["order:900005", "payment:105"], runbook_id=None,
                                             recommended_action=None, uncertainty=None), "fake")

    s = await run_case(DEV["dev-005"], "model", None, Model())
    assert s.model_used and s.verdict_correct


def test_report_renders_from_a_results_file(tmp_path, monkeypatch):
    s = score(DEV["dev-001"], "model", 201, result(), {"validationErrors": [], "model": {
        "inputTokens": 1400, "outputTokens": 130}}, latency_ms=2100)
    b = score(DEV["dev-001"], "baseline", 201, result(modelUsed=False), {"validationErrors": []}, latency_ms=3)
    run = {"split": "dev", "ranAt": "x", "gitSha": "abc1234", "model": "gpt-4o-mini",
           "embeddingModel": "text-embedding-3-small", "cases": 1, "arms": ["baseline", "model"],
           "casesSha256": "f" * 64, "summary": {"baseline": aggregate([b]), "model": aggregate([s])},
           "scores": [b.as_dict(), s.as_dict()]}
    (tmp_path / "dev-20261028T000000Z.json").write_text(json.dumps(run))
    monkeypatch.setattr(report, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(report, "REPORT", tmp_path / "benchmark.md")

    assert report.main() == 0
    md = (tmp_path / "benchmark.md").read_text()
    assert "## dev split — 1 cases" in md
    assert "| Verdict correct (finding + action + manual review) | 1/1 (100%) | 1/1 (100%) |" in md
    assert "1400 in / 130 out" in md


@pytest.mark.parametrize("argv", [["--split", "heldout"]])
async def test_heldout_needs_explicit_confirmation(argv):
    from recovery_agent.evaluation.run import main

    assert await main(argv) == 2

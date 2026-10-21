from pathlib import Path

import pytest

from recovery_agent.baseline import RUNBOOK_FOR, baseline_result
from recovery_agent.rules import Action, Concern, FindingCode, classify
from recovery_agent.runbooks import RUNBOOK_DIR, load_runbooks, parse_runbook

from .snapshots import order, payment, seeded, snapshot

EVAL_RUNBOOKS = Path(__file__).resolve().parents[1] / "runbooks_eval"


# ── The seeded scenarios (SCENARIOS.md "Expected diagnosis") ────────────────

@pytest.mark.parametrize("scenario, concern, code, action", [
    ("S1", Concern.PAYMENT, FindingCode.ORDER_PAYMENT_MISMATCH, Action.RECONCILE_PAYMENT_CONFIRMATION),
    ("S2", Concern.PAYMENT, FindingCode.PAYMENT_AHEAD_OF_ORDER, None),
    ("S3", Concern.PAYMENT, FindingCode.CONSISTENT, None),
    ("S4", Concern.INVENTORY, FindingCode.INSUFFICIENT_EVIDENCE, None),
    ("S5", Concern.PAYMENT, FindingCode.CONFLICTING_EVIDENCE, None),
])
def test_seeded_scenarios(scenario, concern, code, action):
    f = classify(seeded(scenario), concern)
    assert f.code is code
    assert f.allowed_action == action
    assert f.evidence_ids == [f"order:{800000 + int(scenario[1:])}", f"payment:{10 + int(scenario[1:])}"]


def test_only_the_mismatch_permits_an_action():
    for s in ("S2", "S3", "S4", "S5"):
        assert classify(seeded(s), Concern.INVENTORY if s == "S4" else Concern.PAYMENT).allowed_action is None


def test_s5_reports_both_disagreements():
    facts = " ".join(classify(seeded("S5")).facts)
    assert "pi_rcv_s5_a" in facts and "pi_rcv_s5_b" in facts
    assert "60.00" in facts and "55.00" in facts


def test_s4_payment_view_is_consistent_but_inventory_view_abstains():
    assert classify(seeded("S4")).code is FindingCode.CONSISTENT
    f = classify(seeded("S4"), Concern.INVENTORY)
    assert f.missing_evidence == ["order-linked inventory movement"]


# ── Precedence and edge cases ────────────────────────────────────────────────

def test_unavailable_source_beats_any_status_pattern():
    snap = snapshot(order(1, "COMPLETED", "10.00", "pi"), [], payments_status="unavailable")
    f = classify(snap)
    assert f.code is FindingCode.INSUFFICIENT_EVIDENCE
    assert f.missing_evidence == ["payments records"]


def test_both_sources_unavailable_cites_nothing():
    f = classify(snapshot(order_status="unavailable", payments_status="unavailable"))
    assert (f.code, f.evidence_ids) == (FindingCode.INSUFFICIENT_EVIDENCE, [])


def test_order_not_found():
    assert classify(snapshot(order_status="not_found")).code is FindingCode.ORDER_NOT_FOUND


def test_two_payments_for_one_order_is_a_conflict_even_if_statuses_match_s1():
    snap = snapshot(order(1, "COMPLETED", "10.00", "pi"),
                    [payment(7, 1, "PENDING", "10.00", None), payment(8, 1, "PENDING", "10.00", None)])
    f = classify(snap)
    assert f.code is FindingCode.CONFLICTING_EVIDENCE
    assert f.allowed_action is None


def test_amount_conflict_alone_blocks_the_action():
    snap = snapshot(order(1, "COMPLETED", "10.00", "pi"), [payment(7, 1, "PENDING", "9.99", None)])
    assert classify(snap).code is FindingCode.CONFLICTING_EVIDENCE


def test_equal_amounts_in_different_notation_are_not_a_conflict():
    snap = snapshot(order(1, "COMPLETED", "42.5", "pi"), [payment(7, 1, "PENDING", "42.50", None)])
    assert classify(snap).code is FindingCode.ORDER_PAYMENT_MISMATCH


def test_mismatch_without_order_intent_cannot_be_reverified():
    snap = snapshot(order(1, "COMPLETED", "10.00", None), [payment(7, 1, "PENDING", "10.00", None)])
    f = classify(snap)
    assert f.code is FindingCode.INSUFFICIENT_EVIDENCE
    assert f.allowed_action is None


def test_mismatch_with_matching_intents_still_permits_action():
    snap = snapshot(order(1, "COMPLETED", "10.00", "pi"), [payment(7, 1, "PENDING", "10.00", "pi")])
    assert classify(snap).allowed_action is Action.RECONCILE_PAYMENT_CONFIRMATION


@pytest.mark.parametrize("order_status, payments, code", [
    ("PENDING", [], FindingCode.CONSISTENT),
    ("COMPLETED", [], FindingCode.INSUFFICIENT_EVIDENCE),
    ("PENDING", [("PENDING", None)], FindingCode.CONSISTENT),
    ("CANCELLED", [("PAID", "pi")], FindingCode.UNSUPPORTED_STATE),
    ("COMPLETED", [("FAILED", "pi")], FindingCode.UNSUPPORTED_STATE),
])
def test_other_status_combinations(order_status, payments, code):
    snap = snapshot(order(1, order_status, "10.00", "pi"),
                    [payment(7 + i, 1, s, "10.00", pi) for i, (s, pi) in enumerate(payments)])
    assert classify(snap).code is code


# ── Baseline ─────────────────────────────────────────────────────────────────

def test_baseline_for_s1_recommends_the_action_and_cites_the_runbook():
    r = baseline_result(800001, classify(seeded("S1")))
    assert r["finding"] == "ORDER_PAYMENT_MISMATCH"
    assert r["recommendedAction"] == "RECONCILE_PAYMENT_CONFIRMATION"
    assert r["requiresManualReview"] is False
    assert r["runbookId"] == "RB-001-order-completed-payment-pending"
    assert "never confirmed" in r["explanation"]


@pytest.mark.parametrize("scenario", ["S2", "S5"])
def test_baseline_requires_review_without_action(scenario):
    r = baseline_result(1, classify(seeded(scenario)))
    assert (r["recommendedAction"], r["requiresManualReview"]) == (None, True)


def test_baseline_lists_missing_evidence():
    r = baseline_result(800004, classify(seeded("S4"), Concern.INVENTORY))
    assert "Missing: order-linked inventory movement." in r["explanation"]


# ── Runbooks ─────────────────────────────────────────────────────────────────

def test_runbooks_load_and_reference_real_finding_codes():
    runbooks = load_runbooks()
    assert len(runbooks) == 5
    for rb in runbooks:
        assert rb.applies_to and all(code in FindingCode.__members__ for code in rb.applies_to)


def test_every_baseline_runbook_id_exists():
    ids = {rb.id for rb in load_runbooks()}
    assert set(RUNBOOK_FOR.values()) <= ids


def test_eval_fixture_is_outside_the_retrieval_corpus():
    assert not list(RUNBOOK_DIR.glob("RB-X*"))
    fixture = parse_runbook((EVAL_RUNBOOKS / "RB-X01-injected-refund.md").read_text())
    assert fixture.eval_only


def test_loading_a_directory_with_an_eval_only_runbook_is_refused():
    with pytest.raises(ValueError, match="eval-only"):
        load_runbooks(EVAL_RUNBOOKS)


@pytest.mark.parametrize("text", ["no front matter", "---\nid: x\n---\nbody", "---\nnot a pair\n---\nb"])
def test_malformed_runbooks_are_rejected(text):
    with pytest.raises(ValueError):
        parse_runbook(text)

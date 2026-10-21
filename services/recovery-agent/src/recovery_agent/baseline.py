"""Rules + template baseline: the answer the system gives with no model at all.

Every eval case is scored for this baseline and for the model; where the model adds no
measurable value, this result is what gets returned.
"""

from typing import Any

from recovery_agent.rules import Finding, FindingCode

# Deterministic finding → runbook mapping (runbook IDs from runbooks/*.md front matter)
RUNBOOK_FOR: dict[FindingCode, str] = {
    FindingCode.ORDER_PAYMENT_MISMATCH: "RB-001-order-completed-payment-pending",
    FindingCode.PAYMENT_AHEAD_OF_ORDER: "RB-002-payment-paid-order-pending",
    FindingCode.CONFLICTING_EVIDENCE: "RB-003-conflicting-payment-records",
    FindingCode.INSUFFICIENT_EVIDENCE: "RB-004-insufficient-evidence",
    FindingCode.CONSISTENT: "RB-005-consistent-or-duplicate-delivery",
}

_HEADLINE: dict[FindingCode, str] = {
    FindingCode.ORDER_PAYMENT_MISMATCH:
        "The order completed but its payment was never confirmed in payment-service.",
    FindingCode.PAYMENT_AHEAD_OF_ORDER:
        "The payment is confirmed but the order has not progressed. Changing order state is not an agent action.",
    FindingCode.CONFLICTING_EVIDENCE:
        "The order and payment records disagree, so no automatic action is safe.",
    FindingCode.INSUFFICIENT_EVIDENCE:
        "There is not enough evidence to diagnose this order.",
    FindingCode.ORDER_NOT_FOUND:
        "No order with this ID exists.",
    FindingCode.UNSUPPORTED_STATE:
        "This combination of states is outside what the recovery agent handles.",
    FindingCode.CONSISTENT:
        "The order and payment agree; no inconsistency was found.",
}


def baseline_result(order_id: int, finding: Finding) -> dict[str, Any]:
    parts = [_HEADLINE[finding.code], *finding.facts]
    if finding.missing_evidence:
        parts.append("Missing: " + ", ".join(finding.missing_evidence) + ".")
    return {
        "orderId": order_id,
        "finding": finding.code.value,
        "explanation": " ".join(parts),
        "evidenceIds": finding.evidence_ids,
        "runbookId": RUNBOOK_FOR.get(finding.code),
        "recommendedAction": finding.allowed_action.value if finding.allowed_action else None,
        "requiresManualReview": finding.requires_manual_review,
        "source": "rules-baseline",
    }

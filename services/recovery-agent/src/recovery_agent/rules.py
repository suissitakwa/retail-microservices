"""Deterministic inconsistency rules over a stored investigation snapshot.

Rules run before any model call. They decide which finding codes are possible and the only
action that may ever be proposed; the model (Day 6) may explain and cite, never widen that.

Precedence: unusable evidence → conflicting evidence → known mismatch patterns → consistent.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from recovery_agent.models import OrderRecord, PaymentRecord, SourceStatus


class FindingCode(StrEnum):
    ORDER_PAYMENT_MISMATCH = "ORDER_PAYMENT_MISMATCH"      # order COMPLETED, payment never confirmed
    PAYMENT_AHEAD_OF_ORDER = "PAYMENT_AHEAD_OF_ORDER"      # payment PAID, order still PENDING
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"          # records disagree on identity or amount
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"        # a needed source is unavailable / out of scope
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    UNSUPPORTED_STATE = "UNSUPPORTED_STATE"                # a combination v1 deliberately does not handle
    CONSISTENT = "CONSISTENT"


class Action(StrEnum):
    RECONCILE_PAYMENT_CONFIRMATION = "RECONCILE_PAYMENT_CONFIRMATION"


class Concern(StrEnum):
    """What the operator says is wrong. Only PAYMENT is backed by sources the agent can read."""

    PAYMENT = "PAYMENT"
    INVENTORY = "INVENTORY"


@dataclass(frozen=True)
class Finding:
    code: FindingCode
    facts: list[str]
    evidence_ids: list[str]
    allowed_action: Action | None = None
    missing_evidence: list[str] = field(default_factory=list)

    @property
    def requires_manual_review(self) -> bool:
        return self.code not in (FindingCode.CONSISTENT, FindingCode.ORDER_PAYMENT_MISMATCH)


def _status(snapshot: dict[str, Any], source: str) -> SourceStatus:
    return SourceStatus(snapshot["sources"][source]["status"])


def _typed(snapshot: dict[str, Any]) -> tuple[OrderRecord | None, list[PaymentRecord]]:
    order, payments = None, []
    for eid, record in snapshot["records"].items():
        if eid.startswith("order:"):
            order = OrderRecord.model_validate(record)
        elif eid.startswith("payment:"):
            payments.append(PaymentRecord.model_validate(record))
    return order, sorted(payments, key=lambda p: p.id)


def classify(snapshot: dict[str, Any], concern: Concern = Concern.PAYMENT) -> Finding:
    order_status, payments_status = _status(snapshot, "order"), _status(snapshot, "payments")
    order, payments = _typed(snapshot)

    if concern is Concern.INVENTORY:
        # No service records order-linked stock movements; current stock levels can't prove it either way
        cited = [r.evidence_id for r in ([order] if order else []) + payments]
        return Finding(FindingCode.INSUFFICIENT_EVIDENCE,
                       ["No service records stock movements per order, so inventory changes for this order "
                        "cannot be confirmed or ruled out."],
                       cited, missing_evidence=["order-linked inventory movement"])

    unavailable = [s for s, st in (("order", order_status), ("payments", payments_status))
                   if st is SourceStatus.UNAVAILABLE]
    if unavailable:
        return Finding(FindingCode.INSUFFICIENT_EVIDENCE,
                       [f"{s} source did not answer; its records are unknown, not absent." for s in unavailable],
                       [r.evidence_id for r in ([order] if order else []) + payments],
                       missing_evidence=[f"{s} records" for s in unavailable])

    if order_status is SourceStatus.NOT_FOUND or order is None:
        return Finding(FindingCode.ORDER_NOT_FOUND, ["order-service has no order with this ID."],
                       [p.evidence_id for p in payments])

    cited = [order.evidence_id] + [p.evidence_id for p in payments]

    if not payments:
        if order.status == "PENDING":
            return Finding(FindingCode.CONSISTENT, ["Order is PENDING and no payment exists yet."], cited)
        return Finding(FindingCode.INSUFFICIENT_EVIDENCE,
                       [f"Order is {order.status} but payment-service has no payment for it."],
                       cited, missing_evidence=["payment record"])

    if len(payments) > 1:
        return Finding(FindingCode.CONFLICTING_EVIDENCE,
                       [f"payment-service holds {len(payments)} payments for one order "
                        f"({', '.join(p.evidence_id for p in payments)})."], cited)

    payment = payments[0]
    conflicts = []
    if order.stripe_payment_intent_id and payment.stripe_payment_intent_id \
            and order.stripe_payment_intent_id != payment.stripe_payment_intent_id:
        conflicts.append(f"Order intent {order.stripe_payment_intent_id} differs from payment intent "
                         f"{payment.stripe_payment_intent_id}.")
    if order.total_amount is not None and order.total_amount != payment.amount:
        conflicts.append(f"Order total {order.total_amount} differs from payment amount {payment.amount}.")
    if conflicts:
        return Finding(FindingCode.CONFLICTING_EVIDENCE, conflicts, cited)

    match (order.status, payment.status):
        case ("COMPLETED", "PENDING"):
            facts = ["Order is COMPLETED.", "Payment is still PENDING."]
            if payment.stripe_payment_intent_id is None:
                facts.append("Payment has no Stripe intent ID, so the confirmation never reached payment-service.")
            if order.stripe_payment_intent_id is None:
                # Nothing for the owning service to re-verify against Stripe
                return Finding(FindingCode.INSUFFICIENT_EVIDENCE, facts + ["Order has no Stripe intent ID."],
                               cited, missing_evidence=["Stripe payment intent ID"])
            return Finding(FindingCode.ORDER_PAYMENT_MISMATCH, facts, cited,
                           allowed_action=Action.RECONCILE_PAYMENT_CONFIRMATION)
        case ("PENDING", "PAID"):
            return Finding(FindingCode.PAYMENT_AHEAD_OF_ORDER,
                           ["Payment is PAID.", "Order is still PENDING."], cited)
        case ("COMPLETED", "PAID") | ("PENDING", "PENDING"):
            return Finding(FindingCode.CONSISTENT,
                           [f"Order is {order.status} and payment is {payment.status}; they agree."], cited)
        case _:
            return Finding(FindingCode.UNSUPPORTED_STATE,
                           [f"Order {order.status} with payment {payment.status} is outside v1's handled cases."],
                           cited)

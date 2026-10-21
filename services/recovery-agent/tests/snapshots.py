"""Snapshot builders mirroring scripts/recovery/seed.sh (S1–S5) plus edge cases."""

from typing import Any

SEED = {  # scenario: (order status, total, order intent, payment status, amount, payment intent)
    "S1": ("COMPLETED", "42.50", "pi_rcv_s1", "PENDING", "42.50", None),
    "S2": ("PENDING", "30.00", "pi_rcv_s2", "PAID", "30.00", "pi_rcv_s2"),
    "S3": ("COMPLETED", "25.00", "pi_rcv_s3", "PAID", "25.00", "pi_rcv_s3"),
    "S4": ("COMPLETED", "18.00", "pi_rcv_s4", "PAID", "18.00", "pi_rcv_s4"),
    "S5": ("COMPLETED", "60.00", "pi_rcv_s5_a", "PENDING", "55.00", "pi_rcv_s5_b"),
}


def order(order_id: int, status: str, total: str, intent: str | None) -> dict[str, Any]:
    return {"id": order_id, "reference": f"RCV-{order_id}", "customer_id": 1, "total_amount": total,
            "status": status, "stripe_session_id": "cs", "stripe_payment_intent_id": intent, "items": [],
            "created_date": None, "last_modified_date": None}


def payment(payment_id: int, order_id: int, status: str, amount: str, intent: str | None) -> dict[str, Any]:
    return {"id": payment_id, "order_id": order_id, "customer_id": 1, "amount": amount, "currency": "usd",
            "status": status, "order_reference": f"RCV-{order_id}", "stripe_session_id": "cs",
            "stripe_payment_intent_id": intent, "created_at": None, "updated_at": None}


def snapshot(order_record=None, payments=(), *, order_status="ok", payments_status="ok") -> dict[str, Any]:
    records = {}
    if order_record:
        records[f"order:{order_record['id']}"] = order_record
    for p in payments:
        records[f"payment:{p['id']}"] = p
    oid = order_record["id"] if order_record else 0
    return {"orderId": oid, "records": records,
            "sources": {"order": {"status": order_status}, "payments": {"status": payments_status},
                        "events": {"status": "unavailable", "coverage": []}}}


def seeded(scenario: str) -> dict[str, Any]:
    n = int(scenario[1:])
    os_, total, oi, ps, amount, pi = SEED[scenario]
    oid = 800000 + n
    return snapshot(order(oid, os_, total, oi), [payment(10 + n, oid, ps, amount, pi)])

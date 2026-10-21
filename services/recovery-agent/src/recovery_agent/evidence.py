"""Gathers the inputs for one investigation and stores them as an immutable snapshot.

The snapshot records, per source, whether data was found, absent, or unavailable — the
diagnosis step must treat "unavailable" and "not observed" as unknown, never as absent.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

from recovery_agent.clients import ServiceClients, SourceResult
from recovery_agent.db import events_for_order, observation_coverage, save_investigation_input
from recovery_agent.models import SourceStatus


def _source(result: SourceResult) -> dict[str, Any]:
    return {"status": result.status.value, **({"error": result.error} if result.error else {})}


async def gather_investigation_input(order_id: int, token: str, requested_by: str,
                                     clients: ServiceClients, pool) -> dict[str, Any]:
    order_r, payments_r = await asyncio.gather(
        clients.get_order(order_id, token), clients.get_payments(order_id, token))

    async with pool.connection() as conn:
        events = await events_for_order(conn, order_id)
        coverage = await observation_coverage(conn)

    records: dict[str, Any] = {}
    if order_r.status is SourceStatus.OK:
        records[order_r.value.evidence_id] = order_r.value.model_dump(mode="json")
    for p in payments_r.value or []:
        records[p.evidence_id] = p.model_dump(mode="json")
    for e in events:
        records[e.evidence_id] = e.model_dump(mode="json")

    snapshot = {
        "orderId": order_id,
        "sources": {
            "order": _source(order_r),
            "payments": _source(payments_r),
            "events": {
                # No partition observed yet means event history is unknown, not empty
                "status": SourceStatus.OK.value if coverage else SourceStatus.UNAVAILABLE.value,
                "coverage": [{**c, "observed_since": c["observed_since"].isoformat()} for c in coverage],
            },
        },
        "records": records,
    }
    evidence_ids = sorted(records)

    input_id: UUID = uuid4()
    async with pool.connection() as conn:
        created_at = await save_investigation_input(conn, input_id, order_id, requested_by, evidence_ids, snapshot)

    return {"id": str(input_id), "createdAt": created_at.isoformat(), "evidenceIds": evidence_ids, **snapshot}

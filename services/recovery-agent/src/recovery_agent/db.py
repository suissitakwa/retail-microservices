from collections.abc import Iterable
from datetime import datetime
from importlib.resources import files
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from recovery_agent.models import ProcessingEvent

SCHEMA_SQL = files("recovery_agent").joinpath("schema.sql").read_text()


async def apply_schema(conn: AsyncConnection) -> None:
    await conn.execute(SCHEMA_SQL)


async def insert_events(conn: AsyncConnection, events: Iterable[ProcessingEvent]) -> int:
    """Inserts observed records; already-seen (topic, partition, offset) keys are skipped. Returns rows added."""
    added = 0
    async with conn.cursor() as cur:
        for e in events:
            await cur.execute(
                """INSERT INTO event_log (topic, kafka_partition, kafka_offset, order_id, event_timestamp, payload)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (topic, kafka_partition, kafka_offset) DO NOTHING""",
                (e.topic, e.partition, e.offset, e.order_id, e.event_timestamp, Jsonb(e.payload)),
            )
            added += cur.rowcount
    return added


async def record_partition_start(conn: AsyncConnection, group: str, topic: str, partition: int,
                                 first_offset: int) -> None:
    """Keeps the FIRST offset/time ever observed for a partition; later calls are no-ops."""
    await conn.execute(
        """INSERT INTO observer_partition (consumer_group, topic, kafka_partition, first_offset)
           VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
        (group, topic, partition, first_offset),
    )


async def events_for_order(conn: AsyncConnection, order_id: int) -> list[ProcessingEvent]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """SELECT topic, kafka_partition AS partition, kafka_offset AS offset, order_id,
                      event_timestamp, payload
               FROM event_log WHERE order_id = %s ORDER BY event_timestamp NULLS LAST, id""",
            (order_id,),
        )
        return [ProcessingEvent(**row) for row in await cur.fetchall()]


async def observation_coverage(conn: AsyncConnection) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """SELECT topic, kafka_partition AS partition, first_offset, observed_since
               FROM observer_partition ORDER BY topic, kafka_partition"""
        )
        return await cur.fetchall()


async def save_investigation_input(conn: AsyncConnection, input_id: UUID, order_id: int, requested_by: str,
                                   evidence_ids: list[str], snapshot: dict[str, Any]) -> datetime:
    async with conn.cursor() as cur:
        await cur.execute(
            """INSERT INTO investigation_input (id, order_id, requested_by, evidence_ids, snapshot)
               VALUES (%s, %s, %s, %s, %s) RETURNING created_at""",
            (input_id, order_id, requested_by, evidence_ids, Jsonb(snapshot)),
        )
        (created_at,) = await cur.fetchone()
    return created_at


async def save_investigation(conn: AsyncConnection, investigation_id: UUID, input_id: str, order_id: int,
                             concern: str, requested_by: str, result: dict[str, Any], trace: dict[str, Any],
                             latency_ms: int) -> datetime:
    async with conn.cursor() as cur:
        await cur.execute(
            """INSERT INTO investigation (id, input_id, order_id, concern, requested_by, finding, model_used,
                                          result, trace, latency_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING created_at""",
            (investigation_id, input_id, order_id, concern, requested_by, result["finding"],
             result["modelUsed"], Jsonb(result), Jsonb(trace), latency_ms),
        )
        (created_at,) = await cur.fetchone()
    return created_at


async def load_investigation(conn: AsyncConnection, investigation_id: UUID) -> dict[str, Any] | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT * FROM investigation WHERE id = %s", (investigation_id,))
        return await cur.fetchone()


async def load_investigation_input(conn: AsyncConnection, input_id: UUID) -> dict[str, Any] | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT * FROM investigation_input WHERE id = %s", (input_id,))
        return await cur.fetchone()

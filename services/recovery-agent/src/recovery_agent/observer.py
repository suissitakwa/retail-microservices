"""Kafka observer: copies order.created / payment.processed records into event_log.

Delivery rules:
- Offsets are committed only after the batch's DB transaction commits. A crash in between
  redelivers the batch, and the (topic, partition, offset) unique key makes the re-insert a no-op.
- The first offset seen per partition is recorded, so readers know which history was never observed.
- A payload that isn't JSON is stored raw instead of being dropped or crashing the loop.
"""

import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from recovery_agent.db import insert_events, record_partition_start
from recovery_agent.models import ProcessingEvent

log = logging.getLogger(__name__)

TOPICS = ("order.created", "payment.processed")
CONSUMER_GROUP = "recovery-agent-observer"


class _Record(Protocol):
    topic: str
    partition: int
    offset: int
    timestamp: int | None  # epoch millis
    value: bytes | None


def to_event(record: _Record) -> ProcessingEvent:
    payload: dict[str, Any]
    try:
        decoded = json.loads(record.value) if record.value is not None else None
        payload = decoded if isinstance(decoded, dict) else {"_value": decoded}
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        payload = {"_raw": record.value.decode("utf-8", "replace"), "_error": f"not JSON: {e}"}

    order_id = payload.get("orderId")
    ts = datetime.fromtimestamp(record.timestamp / 1000, UTC) if record.timestamp else None
    return ProcessingEvent(topic=record.topic, partition=record.partition, offset=record.offset,
                           order_id=order_id if isinstance(order_id, int) else None,
                           event_timestamp=ts, payload=payload)


class EventObserver:
    def __init__(self, consumer, pool, group: str = CONSUMER_GROUP):
        self._consumer = consumer
        self._pool = pool
        self._group = group

    async def process(self, batch: Mapping[Any, Sequence[_Record]]) -> int:
        """Stores one getmany() batch, then commits its offsets. Returns rows newly added."""
        if not batch:
            return 0
        events = [to_event(r) for records in batch.values() for r in records]

        async with self._pool.connection() as conn, conn.transaction():
            for tp, records in batch.items():
                await record_partition_start(conn, self._group, tp.topic, tp.partition, records[0].offset)
            added = await insert_events(conn, events)

        # The DB transaction has committed; only now is it safe to move the consumer forward
        await self._consumer.commit({tp: records[-1].offset + 1 for tp, records in batch.items()})
        log.info("observed %d records (%d new)", len(events), added)
        return added

    async def run(self, retry_seconds: float = 10) -> None:
        # The broker may come up after this service; keep trying instead of dying silently
        while True:
            try:
                await self._consumer.start()
                break
            except Exception as e:
                log.warning("Kafka not reachable (%s); observer retrying in %ss", e, retry_seconds)
                await asyncio.sleep(retry_seconds)
        try:
            while True:
                batch = await self._consumer.getmany(timeout_ms=1000, max_records=500)
                try:
                    await self.process(batch)
                except Exception:
                    # Offsets were not committed; seek back so the batch is retried, not skipped
                    log.exception("failed to store observed batch; will retry")
                    for tp, records in batch.items():
                        self._consumer.seek(tp, records[0].offset)
                    await asyncio.sleep(1)
        finally:
            await self._consumer.stop()


def build_consumer(bootstrap_servers: str):
    from aiokafka import AIOKafkaConsumer

    return AIOKafkaConsumer(*TOPICS, bootstrap_servers=bootstrap_servers, group_id=CONSUMER_GROUP,
                            enable_auto_commit=False, auto_offset_reset="earliest")

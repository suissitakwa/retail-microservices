import asyncio
import json
from dataclasses import dataclass

import psycopg
import pytest

from recovery_agent.db import events_for_order, observation_coverage
from recovery_agent.observer import EventObserver, to_event

from .conftest import TEST_DATABASE_URL, requires_db


@dataclass(frozen=True)
class TP:
    topic: str
    partition: int


@dataclass
class Rec:
    topic: str
    partition: int
    offset: int
    value: bytes | None
    timestamp: int | None = 1_792_000_000_000


def rec(topic, partition, offset, payload) -> Rec:
    value = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    return Rec(topic, partition, offset, value)


class FakeConsumer:
    def __init__(self, on_commit=None):
        self.commits: list[dict] = []
        self._on_commit = on_commit

    async def commit(self, offsets):
        if self._on_commit:
            await self._on_commit()
        self.commits.append(offsets)


async def test_run_retries_until_broker_is_reachable():
    class FlakyConsumer(FakeConsumer):
        def __init__(self):
            super().__init__()
            self.start_attempts = 0

        async def start(self):
            self.start_attempts += 1
            if self.start_attempts < 3:
                raise ConnectionError("broker down")

        async def getmany(self, **_):
            raise asyncio.CancelledError  # stop the loop once started

        async def stop(self):
            self.stopped = True

    consumer = FlakyConsumer()
    with pytest.raises(asyncio.CancelledError):
        await EventObserver(consumer, pool=None).run(retry_seconds=0)
    assert consumer.start_attempts == 3
    assert consumer.stopped


def test_to_event_extracts_order_id_and_timestamp():
    e = to_event(rec("order.created", 0, 7, {"orderId": 800001, "amount": 42.5}))
    assert (e.order_id, e.evidence_id) == (800001, "event:order.created/0/7")
    assert e.event_timestamp.year == 2026


@pytest.mark.parametrize("value, expected_key", [
    (b"\xff\xfe not json", "_raw"),
    (b"[1, 2]", "_value"),
])
def test_to_event_keeps_unparseable_payloads_instead_of_dropping(value, expected_key):
    e = to_event(Rec("payment.processed", 0, 1, value))
    assert e.order_id is None
    assert expected_key in e.payload


def test_to_event_ignores_non_integer_order_id():
    assert to_event(rec("order.created", 0, 1, {"orderId": "800001"})).order_id is None


@requires_db
async def test_offsets_are_committed_only_after_rows_are_durable(db_pool):
    async def rows_visible_from_another_connection():
        # Runs inside consumer.commit(): the batch must already be committed to the DB
        async with db_pool.connection() as conn:
            schema = (await (await conn.execute("SHOW search_path")).fetchone())[0]
        with psycopg.connect(TEST_DATABASE_URL, options=f"-c search_path={schema}") as other:
            seen.append(other.execute("SELECT count(*) FROM event_log").fetchone()[0])

    seen: list[int] = []
    consumer = FakeConsumer(on_commit=rows_visible_from_another_connection)
    tp = TP("order.created", 0)
    added = await EventObserver(consumer, db_pool).process(
        {tp: [rec("order.created", 0, 10, {"orderId": 1}), rec("order.created", 0, 11, {"orderId": 2})]})

    assert added == 2
    assert seen == [2]
    assert consumer.commits == [{tp: 12}]  # next offset to read


@requires_db
async def test_redelivered_batch_is_a_no_op(db_pool):
    consumer = FakeConsumer()
    tp = TP("payment.processed", 0)
    batch = {tp: [rec("payment.processed", 0, 5, {"orderId": 800001})]}
    observer = EventObserver(consumer, db_pool)

    assert await observer.process(batch) == 1
    assert await observer.process(batch) == 0  # e.g. crash after DB commit, before offset commit

    async with db_pool.connection() as conn:
        assert [e.evidence_id for e in await events_for_order(conn, 800001)] == ["event:payment.processed/0/5"]


@requires_db
async def test_failed_db_write_does_not_commit_offsets(db_pool):
    async with db_pool.connection() as conn:
        await conn.execute("ALTER TABLE event_log ADD CONSTRAINT reject_all CHECK (false) NOT VALID")
    consumer = FakeConsumer()

    with pytest.raises(psycopg.errors.CheckViolation):
        await EventObserver(consumer, db_pool).process({TP("order.created", 0): [rec("order.created", 0, 1, {})]})

    assert consumer.commits == []
    async with db_pool.connection() as conn:
        # The partition-start row was in the same transaction and rolled back too
        assert await observation_coverage(conn) == []


@requires_db
async def test_coverage_keeps_the_first_offset_ever_observed(db_pool):
    observer = EventObserver(FakeConsumer(), db_pool)
    tp = TP("order.created", 1)
    await observer.process({tp: [rec("order.created", 1, 40, {"orderId": 1})]})
    await observer.process({tp: [rec("order.created", 1, 41, {"orderId": 1})]})

    async with db_pool.connection() as conn:
        coverage = await observation_coverage(conn)
    assert [(c["topic"], c["partition"], c["first_offset"]) for c in coverage] == [("order.created", 1, 40)]

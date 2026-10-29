import uuid
from dataclasses import replace

import psycopg
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from recovery_agent.retrieval import PgRunbookIndex, chunk_runbooks, sqlalchemy_url
from recovery_agent.runbooks import load_runbooks

from .conftest import TEST_DATABASE_URL, requires_db


def test_chunks_are_one_per_section_with_title_and_metadata():
    chunks = chunk_runbooks(load_runbooks())
    rb001 = [d for _, d in chunks if d.metadata["runbook_id"] == "RB-001-order-completed-payment-pending"]
    sections = [d.metadata["section"] for d in rb001]
    assert sections == ["Symptoms", "Why it happens", "How to confirm", "Permitted recovery", "Do not"]
    assert all(d.page_content.startswith("Order completed, payment still pending — ") for d in rb001)
    assert rb001[0].metadata["applies_to"] == "ORDER_PAYMENT_MISMATCH"


def test_chunk_ids_are_stable_and_change_with_content():
    runbooks = load_runbooks()
    first = [i for i, _ in chunk_runbooks(runbooks)]
    assert first == [i for i, _ in chunk_runbooks(runbooks)]
    assert len(set(first)) == len(first)

    edited = [replace(runbooks[0], body=runbooks[0].body + "\n\nExtra line.")] + runbooks[1:]
    changed = {i for i, _ in chunk_runbooks(edited)} ^ set(first)
    assert len(changed) == 2  # only the last section of the edited runbook: one removed, one added


def test_sqlalchemy_url_uses_async_psycopg_driver():
    assert sqlalchemy_url("postgresql://u:p@h:5439/db") == "postgresql+psycopg://u:p@h:5439/db"
    assert sqlalchemy_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


@pytest.fixture
async def index():
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {schema}")
    idx = await PgRunbookIndex.open(sqlalchemy_url(TEST_DATABASE_URL), DeterministicFakeEmbedding(size=64),
                                    vector_size=64, schema=schema)
    try:
        yield idx
    finally:
        await idx.close()
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(f"DROP SCHEMA {schema} CASCADE")


@requires_db
async def test_sync_is_incremental_and_search_returns_runbook_metadata(index):
    runbooks = load_runbooks()
    total = len(chunk_runbooks(runbooks))

    assert await index.sync(runbooks) == {"chunks": total, "added": total, "deleted": 0}
    assert await index.sync(runbooks) == {"chunks": total, "added": 0, "deleted": 0}

    # Exact chunk text embeds identically with the deterministic fake, so it must come back first
    target = next(d for _, d in chunk_runbooks(runbooks) if d.metadata["runbook_id"].startswith("RB-003"))
    hits = await index.search(target.page_content, k=3)
    assert hits[0].runbook_id == "RB-003-conflicting-payment-records"
    assert hits[0].content == target.page_content
    assert hits[0].score == pytest.approx(0, abs=1e-6)


@requires_db
async def test_removed_runbook_chunks_are_deleted(index):
    runbooks = load_runbooks()
    await index.sync(runbooks)
    stats = await index.sync(runbooks[1:])
    assert stats["deleted"] == len(chunk_runbooks(runbooks[:1]))
    assert stats["added"] == 0

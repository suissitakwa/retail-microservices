"""Runbook retrieval: chunk → embed → PGVector, and similarity search.

Runbooks carry procedures, never live state. Chunk IDs are derived from content, so re-ingesting an
unchanged corpus embeds nothing, and edited or removed sections are replaced or deleted.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from sqlalchemy import text

from recovery_agent.runbooks import Runbook

log = logging.getLogger(__name__)

TABLE = "runbook_chunks"
_NAMESPACE = uuid.UUID("6f0e8a52-3c1b-4e57-9a0e-0c2f6a9d1b11")
_splitter = MarkdownHeaderTextSplitter([("#", "title"), ("##", "section")])


@dataclass(frozen=True)
class RetrievedChunk:
    runbook_id: str
    title: str
    section: str
    content: str
    score: float  # cosine distance — lower is closer


class Retriever(Protocol):
    async def search(self, query: str, k: int) -> list[RetrievedChunk]: ...


def chunk_runbooks(runbooks: list[Runbook]) -> list[tuple[str, Document]]:
    """One chunk per `##` section, with a header (title, section, finding codes) so each chunk stands alone
    and a query that names the finding code lands on the runbook written for it."""
    chunks = []
    for rb in runbooks:
        for i, part in enumerate(_splitter.split_text(rb.body)):
            section = part.metadata.get("section", "Overview")
            content = f"{rb.title} — {section}\nApplies to: {', '.join(rb.applies_to)}\n\n{part.page_content}"
            digest = hashlib.sha256(f"{rb.id}|{i}|{content}".encode()).hexdigest()
            chunk_id = str(uuid.uuid5(_NAMESPACE, digest))
            chunks.append((chunk_id, Document(page_content=content, metadata={
                "runbook_id": rb.id, "title": rb.title, "section": section,
                "applies_to": ",".join(rb.applies_to)})))
    return chunks


class PgRunbookIndex:
    """PGVectorStore-backed index over runbook chunks."""

    def __init__(self, store, sa_engine, schema: str = "public"):
        self._store = store
        self._sa_engine = sa_engine
        self._schema = schema

    @classmethod
    async def open(cls, sqlalchemy_url: str, embeddings: Embeddings, vector_size: int,
                   schema: str = "public") -> "PgRunbookIndex":
        from langchain_postgres import Column, PGEngine, PGVectorStore
        from sqlalchemy.ext.asyncio import create_async_engine

        sa_engine = create_async_engine(sqlalchemy_url, pool_size=2, max_overflow=2)
        async with sa_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            exists = (await conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"),
                                         {"t": f'"{schema}".{TABLE}'})).scalar()
        engine = PGEngine.from_engine(sa_engine)
        if not exists:
            await engine.ainit_vectorstore_table(
                TABLE, vector_size, schema_name=schema,
                metadata_columns=[Column("runbook_id", "TEXT"), Column("title", "TEXT"),
                                  Column("section", "TEXT"), Column("applies_to", "TEXT")])
        store = await PGVectorStore.create(engine, embeddings, TABLE, schema_name=schema,
                                           metadata_columns=["runbook_id", "title", "section", "applies_to"])
        return cls(store, sa_engine, schema)

    async def existing_ids(self) -> set[str]:
        async with self._sa_engine.connect() as conn:
            rows = await conn.execute(text(f'SELECT langchain_id::text FROM "{self._schema}"."{TABLE}"'))
            return {r[0] for r in rows}

    async def sync(self, runbooks: list[Runbook]) -> dict[str, int]:
        desired = dict(chunk_runbooks(runbooks))
        existing = await self.existing_ids()
        to_add = [i for i in desired if i not in existing]
        to_delete = [i for i in existing if i not in desired]
        if to_delete:
            await self._store.adelete(ids=to_delete)
        if to_add:
            await self._store.aadd_documents([desired[i] for i in to_add], ids=to_add)
        stats = {"chunks": len(desired), "added": len(to_add), "deleted": len(to_delete)}
        log.info("runbook index synced: %s", stats)
        return stats

    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        hits = await self._store.asimilarity_search_with_score(query, k=k)
        return [RetrievedChunk(d.metadata["runbook_id"], d.metadata["title"], d.metadata["section"],
                               d.page_content, float(score)) for d, score in hits]

    async def close(self) -> None:
        await self._sa_engine.dispose()


def sqlalchemy_url(database_url: str) -> str:
    """postgresql://… → postgresql+psycopg://… (async psycopg 3 driver for SQLAlchemy)."""
    scheme, _, rest = database_url.partition("://")
    return f"postgresql+psycopg://{rest}" if scheme in ("postgresql", "postgres") else database_url

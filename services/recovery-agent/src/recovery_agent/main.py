import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from recovery_agent.auth import ROLE_ADMIN, Principal, current_principal, require_role
from recovery_agent.baseline import baseline_result
from recovery_agent.clients import ServiceClients, SourceForbidden
from recovery_agent.config import get_settings
from recovery_agent.db import apply_schema, load_investigation, load_investigation_input, save_investigation
from recovery_agent.diagnosis import OpenAIDiagnoser
from recovery_agent.evidence import gather_investigation_input
from recovery_agent.graph import GraphDeps, build_graph, trace
from recovery_agent.observer import EventObserver, build_consumer
from recovery_agent.retrieval import PgRunbookIndex, sqlalchemy_url
from recovery_agent.rules import Concern, classify
from recovery_agent.runbooks import load_runbooks

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=5, open=False,
                               kwargs={"autocommit": True})
    await pool.open()
    async with pool.connection() as conn:
        await apply_schema(conn)

    http = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    app.state.pool = pool
    app.state.clients = ServiceClients(http, settings.order_service_url, settings.payment_service_url)

    index, diagnoser = None, None
    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        key = settings.openai_api_key.get_secret_value()
        embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=key,
                                      dimensions=settings.embedding_dimensions)
        index = await PgRunbookIndex.open(sqlalchemy_url(settings.database_url), embeddings,
                                          settings.embedding_dimensions)
        await index.sync(load_runbooks())
        diagnoser = OpenAIDiagnoser(settings.llm_model, key, settings.llm_timeout_seconds)
    else:
        log.warning("OPENAI_API_KEY not set — no retrieval or model; investigations return the rules baseline")
    app.state.graph = build_graph(GraphDeps(app.state.clients, pool, index, diagnoser))

    observer_task = None
    if settings.kafka_bootstrap_servers:
        observer = EventObserver(build_consumer(settings.kafka_bootstrap_servers), pool)
        observer_task = asyncio.create_task(observer.run(), name="kafka-observer")
    else:
        log.warning("KAFKA_BOOTSTRAP_SERVERS not set — event observer disabled, event history unavailable")

    try:
        yield
    finally:
        if observer_task:
            observer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await observer_task
        if index:
            await index.close()
        await http.aclose()
        await pool.close()


app = FastAPI(title="recovery-agent", version="0.1.0", lifespan=lifespan)


def get_pool(request: Request):
    return request.app.state.pool


def get_clients(request: Request) -> ServiceClients:
    return request.app.state.clients


def get_graph(request: Request):
    return request.app.state.graph


@app.get("/health")
def liveness() -> dict[str, str]:
    """Unauthenticated liveness probe for Docker/Kubernetes; not routed through the gateway."""
    return {"status": "UP"}


@app.get("/api/v1/recovery/health")
def authenticated_health(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
    """Proves a gateway-routed request carries a token this service accepts."""
    return {"status": "UP", "subject": principal.email, "roles": sorted(principal.roles)}


class InvestigationInputRequest(BaseModel):
    order_id: int = Field(alias="orderId", gt=0)


@app.post("/api/v1/recovery/investigation-inputs", status_code=status.HTTP_201_CREATED)
async def create_investigation_input(
    body: InvestigationInputRequest,
    principal: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    clients: Annotated[ServiceClients, Depends(get_clients)],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> dict:
    try:
        return await gather_investigation_input(body.order_id, principal.token, principal.email, clients, pool)
    except SourceForbidden as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{e.source} rejected the caller's token") from e


async def _load_input(pool: AsyncConnectionPool, input_id: UUID) -> dict:
    async with pool.connection() as conn:
        row = await load_investigation_input(conn, input_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investigation input not found")
    return row


@app.get("/api/v1/recovery/investigation-inputs/{input_id}")
async def get_investigation_input(
    input_id: UUID,
    _: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> dict:
    row = await _load_input(pool, input_id)
    return {"id": str(row["id"]), "orderId": row["order_id"], "requestedBy": row["requested_by"],
            "createdAt": row["created_at"].isoformat(), "evidenceIds": row["evidence_ids"], **row["snapshot"]}


@app.get("/api/v1/recovery/investigation-inputs/{input_id}/baseline")
async def get_baseline(
    input_id: UUID,
    _: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    concern: Concern = Concern.PAYMENT,
) -> dict:
    """Rules + template result for a stored input — no model call."""
    row = await _load_input(pool, input_id)
    return {"inputId": str(row["id"]), **baseline_result(row["order_id"], classify(row["snapshot"], concern))}


class InvestigationRequest(BaseModel):
    order_id: int = Field(alias="orderId", gt=0)
    concern: Concern = Concern.PAYMENT


def _investigation_body(row: dict) -> dict:
    return {"id": str(row["id"]), "inputId": str(row["input_id"]), "concern": row["concern"],
            "requestedBy": row["requested_by"], "createdAt": row["created_at"].isoformat(),
            "latencyMs": row["latency_ms"], **row["result"]}


@app.post("/api/v1/recovery/investigations", status_code=status.HTTP_201_CREATED)
async def create_investigation(
    body: InvestigationRequest,
    principal: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    graph=Depends(get_graph),  # noqa: B008 — compiled graph has no useful type to annotate
) -> dict:
    start = time.perf_counter()
    try:
        state = await graph.ainvoke({"order_id": body.order_id, "concern": body.concern,
                                     "token": principal.token, "requested_by": principal.email})
    except SourceForbidden as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{e.source} rejected the caller's token") from e
    latency_ms = int((time.perf_counter() - start) * 1000)

    investigation_id = uuid4()
    async with pool.connection() as conn:
        await save_investigation(conn, investigation_id, state["input"]["id"], body.order_id, body.concern.value,
                                 principal.email, state["result"], trace(state), latency_ms)
        row = await load_investigation(conn, investigation_id)
    return _investigation_body(row)


@app.get("/api/v1/recovery/investigations/{investigation_id}")
async def get_investigation(
    investigation_id: UUID,
    _: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    include_trace: bool = False,
) -> dict:
    async with pool.connection() as conn:
        row = await load_investigation(conn, investigation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investigation not found")
    body = _investigation_body(row)
    return {**body, "trace": row["trace"]} if include_trace else body

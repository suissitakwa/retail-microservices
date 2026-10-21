import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from recovery_agent.auth import ROLE_ADMIN, Principal, current_principal, require_role
from recovery_agent.clients import ServiceClients, SourceForbidden
from recovery_agent.config import get_settings
from recovery_agent.db import apply_schema, load_investigation_input
from recovery_agent.evidence import gather_investigation_input
from recovery_agent.observer import EventObserver, build_consumer

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
        await http.aclose()
        await pool.close()


app = FastAPI(title="recovery-agent", version="0.1.0", lifespan=lifespan)


def get_pool(request: Request):
    return request.app.state.pool


def get_clients(request: Request) -> ServiceClients:
    return request.app.state.clients


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


@app.get("/api/v1/recovery/investigation-inputs/{input_id}")
async def get_investigation_input(
    input_id: UUID,
    _: Annotated[Principal, Depends(require_role(ROLE_ADMIN))],
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
) -> dict:
    async with pool.connection() as conn:
        row = await load_investigation_input(conn, input_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "investigation input not found")
    return {"id": str(row["id"]), "orderId": row["order_id"], "requestedBy": row["requested_by"],
            "createdAt": row["created_at"].isoformat(), "evidenceIds": row["evidence_ids"], **row["snapshot"]}

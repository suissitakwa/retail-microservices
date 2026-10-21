"""Read-only HTTP clients for the services that own business state.

The caller's bearer token is forwarded, so every read is authorised as the investigating user —
the agent never holds broader credentials than the person using it.
"""

from dataclasses import dataclass

import httpx
from pydantic import TypeAdapter, ValidationError

from recovery_agent.models import OrderRecord, PaymentRecord, SourceStatus


class SourceForbidden(Exception):
    """The source rejected the caller's credentials. Surface it; never treat it as missing data."""

    def __init__(self, source: str, status_code: int):
        super().__init__(f"{source} returned {status_code}")
        self.source = source
        self.status_code = status_code


@dataclass(frozen=True)
class SourceResult[T]:
    source: str
    status: SourceStatus
    value: T | None = None
    error: str | None = None


_payments = TypeAdapter(list[PaymentRecord])


class ServiceClients:
    def __init__(self, http: httpx.AsyncClient, order_service_url: str, payment_service_url: str):
        self._http = http
        self._order_url = order_service_url.rstrip("/")
        self._payment_url = payment_service_url.rstrip("/")

    async def get_order(self, order_id: int, token: str) -> SourceResult[OrderRecord]:
        return await self._get("order-service", f"{self._order_url}/api/v1/orders/admin/orders/{order_id}",
                               token, OrderRecord.model_validate)

    async def get_payments(self, order_id: int, token: str) -> SourceResult[list[PaymentRecord]]:
        return await self._get("payment-service", f"{self._payment_url}/api/v1/payments/order/{order_id}/all",
                               token, _payments.validate_python)

    async def _get(self, source: str, url: str, token: str, parse) -> SourceResult:
        try:
            r = await self._http.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as e:
            return SourceResult(source, SourceStatus.UNAVAILABLE, error=f"{type(e).__name__}: {e}")

        if r.status_code in (401, 403):
            raise SourceForbidden(source, r.status_code)
        if r.status_code == 404:
            return SourceResult(source, SourceStatus.NOT_FOUND)
        if r.status_code >= 400:
            return SourceResult(source, SourceStatus.UNAVAILABLE, error=f"HTTP {r.status_code}")
        try:
            return SourceResult(source, SourceStatus.OK, value=parse(r.json()))
        except (ValueError, ValidationError) as e:
            return SourceResult(source, SourceStatus.UNAVAILABLE, error=f"malformed response: {e}")

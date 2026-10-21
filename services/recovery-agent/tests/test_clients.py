import httpx
import pytest
import respx

from recovery_agent.clients import ServiceClients, SourceForbidden
from recovery_agent.models import SourceStatus

ORDER_URL = "http://order-service.test"
PAYMENT_URL = "http://payment-service.test"

ORDER_JSON = {
    "id": 800001, "reference": "RCV-S1", "customerId": 1, "totalAmount": 42.50, "status": "COMPLETED",
    "stripeSessionId": "cs_rcv_s1", "stripePaymentIntentId": "pi_rcv_s1",
    "items": [{"id": 800001, "productId": 1, "productName": "Item", "quantity": 1, "price": 42.50}],
    "createdDate": "2026-10-19T10:00:00", "lastModifiedDate": "2026-10-19T10:05:00",
    "someNewField": "ignored",
}
PAYMENT_JSON = {
    "id": 13, "orderId": 800001, "customerId": 1, "amount": 42.50, "currency": "usd", "status": "PENDING",
    "orderReference": "RCV-S1", "stripeSessionId": "cs_rcv_s1", "stripePaymentIntentId": None,
    "createdAt": "2026-10-19T10:00:00", "updatedAt": "2026-10-19T10:00:00",
}


@pytest.fixture
async def clients():
    async with httpx.AsyncClient() as http:
        yield ServiceClients(http, ORDER_URL, PAYMENT_URL)


@respx.mock
async def test_get_order_parses_admin_view_and_forwards_token(clients):
    route = respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/800001").respond(json=ORDER_JSON)
    r = await clients.get_order(800001, "tok-123")

    assert r.status is SourceStatus.OK
    assert r.value.evidence_id == "order:800001"
    assert r.value.stripe_payment_intent_id == "pi_rcv_s1"
    assert str(r.value.total_amount) == "42.5"
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok-123"


@respx.mock
async def test_get_payments_returns_every_payment_for_the_order(clients):
    second = {**PAYMENT_JSON, "id": 14, "status": "PAID", "stripePaymentIntentId": "pi_x"}
    respx.get(f"{PAYMENT_URL}/api/v1/payments/order/800001/all").respond(json=[PAYMENT_JSON, second])
    r = await clients.get_payments(800001, "tok")

    assert r.status is SourceStatus.OK
    assert [p.evidence_id for p in r.value] == ["payment:13", "payment:14"]


@respx.mock
async def test_no_payments_is_ok_and_empty_not_unavailable(clients):
    respx.get(f"{PAYMENT_URL}/api/v1/payments/order/5/all").respond(json=[])
    r = await clients.get_payments(5, "tok")
    assert (r.status, r.value) == (SourceStatus.OK, [])


@respx.mock
async def test_404_is_not_found(clients):
    respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/9").respond(404)
    assert (await clients.get_order(9, "tok")).status is SourceStatus.NOT_FOUND


@respx.mock
@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(503),
    httpx.Response(200, text="<html>not json</html>"),
    httpx.Response(200, json={"id": "not-an-int"}),
])
async def test_errors_and_malformed_bodies_are_unavailable(clients, response):
    respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/1").mock(return_value=response)
    r = await clients.get_order(1, "tok")
    assert r.status is SourceStatus.UNAVAILABLE
    assert r.error


@respx.mock
async def test_connection_failure_is_unavailable(clients):
    respx.get(f"{PAYMENT_URL}/api/v1/payments/order/1/all").mock(side_effect=httpx.ConnectError("refused"))
    r = await clients.get_payments(1, "tok")
    assert r.status is SourceStatus.UNAVAILABLE
    assert "ConnectError" in r.error


@respx.mock
@pytest.mark.parametrize("code", [401, 403])
async def test_auth_rejection_is_raised_not_treated_as_missing(clients, code):
    respx.get(f"{ORDER_URL}/api/v1/orders/admin/orders/1").respond(code)
    with pytest.raises(SourceForbidden) as e:
        await clients.get_order(1, "tok")
    assert e.value.status_code == code

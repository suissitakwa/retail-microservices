"""Typed views of the records the agent reads. Every record carries a stable evidence ID."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Record(BaseModel):
    # Services may add fields; the agent only relies on the ones declared here
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


class OrderItem(_Record):
    id: int
    product_id: int | None = Field(None, alias="productId")
    product_name: str | None = Field(None, alias="productName")
    quantity: int | None = None
    price: Decimal | None = None


class OrderRecord(_Record):
    id: int
    reference: str
    customer_id: int | None = Field(None, alias="customerId")
    total_amount: Decimal | None = Field(None, alias="totalAmount")
    status: str
    stripe_session_id: str | None = Field(None, alias="stripeSessionId")
    stripe_payment_intent_id: str | None = Field(None, alias="stripePaymentIntentId")
    items: list[OrderItem] = []
    created_date: datetime | None = Field(None, alias="createdDate")
    last_modified_date: datetime | None = Field(None, alias="lastModifiedDate")

    @property
    def evidence_id(self) -> str:
        return f"order:{self.id}"


class PaymentRecord(_Record):
    id: int
    order_id: int = Field(alias="orderId")
    customer_id: int | None = Field(None, alias="customerId")
    amount: Decimal
    currency: str | None = None
    status: str
    order_reference: str | None = Field(None, alias="orderReference")
    stripe_session_id: str | None = Field(None, alias="stripeSessionId")
    stripe_payment_intent_id: str | None = Field(None, alias="stripePaymentIntentId")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    @property
    def evidence_id(self) -> str:
        return f"payment:{self.id}"


class ProcessingEvent(_Record):
    """One Kafka record seen by the observer. Kafka events carry no event ID, so the offset is the identity."""

    topic: str
    partition: int
    offset: int
    order_id: int | None
    event_timestamp: datetime | None
    payload: dict[str, Any]

    @property
    def evidence_id(self) -> str:
        return f"event:{self.topic}/{self.partition}/{self.offset}"


class SourceStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"      # the source answered: no such record
    UNAVAILABLE = "unavailable"  # the source did not answer — absence of data proves nothing

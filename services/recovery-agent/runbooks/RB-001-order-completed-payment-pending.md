---
id: RB-001-order-completed-payment-pending
title: Order completed, payment still pending
applies_to: ORDER_PAYMENT_MISMATCH
---

# Order completed, payment still pending

## Symptoms
- order-service shows the order `COMPLETED`.
- payment-service shows the matching payment `PENDING`, usually with no Stripe payment intent ID.
- The customer was charged (Stripe has a succeeded PaymentIntent), but no payment confirmation or
  `payment.processed` event followed.

## Why it happens
order-service marks the order `COMPLETED` when Stripe's `payment_intent.succeeded` webhook arrives, and then
calls payment-service over HTTP to find and confirm the payment. Both calls only log on failure. If
payment-service is down or slow at that moment, the order commits and the payment is never confirmed.
A stack trace is not needed to confirm this: the missing intent ID on the payment is the signature.

## How to confirm
1. The order has a Stripe payment intent ID.
2. Exactly one payment exists for the order, with the same amount as the order total.
3. The payment is `PENDING` and its intent ID is empty or equal to the order's.
4. Nothing in the records contradicts the above (see RB-003 if anything does).

## Permitted recovery
`RECONCILE_PAYMENT_CONFIRMATION`, after human approval. The agent supplies only the order ID; order-service
re-checks the PaymentIntent with Stripe and payment-service applies `PENDING → PAID` only if the payment is
still `PENDING` at write time. Never copy a status from one service to another.

## Do not
- Mark the payment `PAID` by hand or from the agent.
- Retry the webhook from Stripe's dashboard — the order is already `COMPLETED`, so the confirm call is skipped.
- Refund or cancel: the customer paid and the order is valid.

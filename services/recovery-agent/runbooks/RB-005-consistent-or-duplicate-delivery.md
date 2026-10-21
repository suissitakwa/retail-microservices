---
id: RB-005-consistent-or-duplicate-delivery
title: Records agree, including after duplicate webhook delivery
applies_to: CONSISTENT
---

# Records agree, including after duplicate webhook delivery

## When this applies
- Order `COMPLETED` and payment `PAID` with matching amount and PaymentIntent, or
- Order `PENDING` and payment `PENDING` (checkout started, customer has not paid yet).

## Duplicate deliveries
Stripe retries webhooks, so the same `payment_intent.succeeded` can arrive more than once. order-service locks the
order and skips an already-`COMPLETED` order, so a duplicate leaves the records consistent. A consistent result
after a reported duplicate is the expected outcome, not a missed problem.

## What to do
Report that no inconsistency was found and list the records checked. If the customer still reports a problem,
ask what they observed — the issue is likely outside order and payment state (shipping, email, inventory).

## Do not
- Propose a recovery action for consistent records.

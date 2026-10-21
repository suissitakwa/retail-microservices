---
id: RB-003-conflicting-payment-records
title: Conflicting order and payment records
applies_to: CONFLICTING_EVIDENCE
---

# Conflicting order and payment records

## Symptoms
Any of:
- The order's Stripe payment intent ID differs from the payment's.
- The payment amount differs from the order total.
- payment-service holds more than one payment for the same order (`order_id` is not unique there).

## Why it matters
Every automatic recovery assumes one order maps to one payment for the same amount and the same PaymentIntent.
When records disagree, any action could confirm the wrong payment or the wrong amount.

## Permitted recovery
None by the agent, even if the statuses alone look like RB-001. Escalate with every record ID involved and the
specific disagreement (which field, which values).

## How a human resolves it
1. Look up each PaymentIntent in the Stripe dashboard and decide which one belongs to the order.
2. Decide what happens to the other payment row (cancel, or keep for a refund investigation).
3. Only after the records agree can RB-001 apply.

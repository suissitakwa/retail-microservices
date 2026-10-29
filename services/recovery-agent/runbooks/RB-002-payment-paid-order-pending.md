---
id: RB-002-payment-paid-order-pending
title: Payment confirmed, order still pending
applies_to: PAYMENT_AHEAD_OF_ORDER
---

# Payment confirmed, order still pending

## Symptoms
- payment-service shows the payment `PAID`.
- order-service still shows the order `PENDING`.

## Why it happens
This is the reverse of the usual failure. In the current flow order-service completes the order before it
confirms the payment, so a `PAID` payment on a `PENDING` order means something outside the normal webhook path
changed one side — a manual update, a replayed confirm call, or a bug.

## How to confirm
1. Exactly one payment exists and its amount equals the order total.
2. Intent IDs agree, or one side is empty.
3. Check order-service logs around the payment's update time for the webhook.

## Permitted recovery
None by the agent. Order state is owned by order-service and changing it is a manual, reviewed action.
Escalate with the order ID, the payment ID and the payment's update time.

## Do not
- Complete the order from the agent.
- Refund the payment without finding out why the order did not progress.

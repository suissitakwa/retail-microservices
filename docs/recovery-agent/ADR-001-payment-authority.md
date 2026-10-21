# ADR-001 — Payment authority and the single recovery action

**Status:** Accepted · **Date:** 2026-10-14

## Context

A completed checkout touches two services and one external system:

| Record | Owner | Store |
|---|---|---|
| Order (`retail_order.status`) | `order-service` | `order-db` (5437) |
| Payment (`payments.status`) | `payment-service` | `payment-db` (5434) |
| PaymentIntent | Stripe | Stripe API |

`order-service` receives Stripe webhooks (`StripeWebhookController`). On `payment_intent.succeeded`
(or `checkout.session.completed` with `payment_status=paid`) it calls `OrderService.markCompleted()`, which:

1. locks the order by `stripePaymentIntentId`, sets it `COMPLETED` and saves it inside a `@Transactional` method;
2. calls `PaymentClient.findPaymentIdByOrderId()` then `PaymentClient.confirmPayment()` over HTTP
   (`PATCH /api/v1/payments/{id}/confirm`).

Both `PaymentClient` methods catch every exception and only log a warning. If `payment-service` is down
or slow, the order commits as `COMPLETED` while the payment stays `PENDING`, and nothing retries.
A redelivered webhook does not repair it: `markCompleted()` returns early when the order is already
`COMPLETED`, so the confirm call is never attempted again.

Verified against the code on 2026-10-14 (see `PROGRESS.md` log for discrepancies with `PLAN.md`).

## Decision

### 1. Who is authoritative

- **Stripe's PaymentIntent is the source of truth for whether money moved.** Neither service's
  database, and never the agent, decides that a payment succeeded.
- **`order-service` is the only Stripe client.** It already holds `STRIPE_SECRET_KEY`; `payment-service`
  and `recovery-agent` never talk to Stripe.
- **`payment-service` owns the payment row.** Only it writes `payments.status`.
- **`recovery-agent` owns nothing in the business domain.** It reads through typed service APIs,
  writes only its own investigation/audit tables, and *requests* one action from `order-service`.

### 2. The single permitted action: `RECONCILE_PAYMENT_CONFIRMATION`

Repairs exactly one inconsistency: order `COMPLETED`, payment `PENDING`, Stripe PaymentIntent `succeeded`.

| Step | Actor | Check / effect |
|---|---|---|
| Request | agent → `order-service` `POST /internal/recoveries` | Body `{orderId, action, investigationId}` + `Idempotency-Key`. No status value is sent. |
| Re-verify | `order-service` → Stripe | PaymentIntent `status == succeeded`, `metadata.orderId` == order, `amount` == order total in cents. Any mismatch → `PRECONDITION_FAILED`. |
| Apply | `order-service` → `payment-service` | `UPDATE payments SET status='PAID', version=version+1 WHERE id=? AND status='PENDING' AND version=?` |
| Outcome | `payment-service` | 1 row → `APPLIED` and one `payment.processed` event. 0 rows → `PRECONDITION_FAILED`; the agent marks its proposal `STALE`. |
| Lookup | agent → `order-service` `GET /internal/recoveries/{key}` | Returns the stored outcome; used by the crash-recovery sweeper. |

### 3. Permitted transitions

| Entity | From | To | Via |
|---|---|---|---|
| Payment | `PENDING` | `PAID` | Webhook path, or `RECONCILE_PAYMENT_CONFIRMATION` |
| Payment | `PENDING` | `FAILED` | `PATCH /{id}/fail` (unchanged, not exposed to the agent) |
| Payment | `PAID` / `FAILED` / `CANCELLED` | anything | **Refused.** Today `confirmPayment()` allows `FAILED → PAID` and `CANCELLED → PAID`; fixed on Day 10. |
| Order | any | any | **Not an agent action.** The order side is already correct in S1. |

### 4. Duplicate prevention

- Business level: `UNIQUE(order_id, action)` over *active* recovery requests in `order-db`.
- Transport level: `Idempotency-Key` bound to a SHA-256 of the canonical request body —
  same key + same body → stored result; same key + different body → `422`.
- Event level: `payment.processed` is published only when the conditional update changed a row.

### 5. Human in the loop

The agent proposes; a `ROLE_ADMIN` user approves a proposal bound to its hash, with an expiry.
Only then does the agent call `order-service`.

## Out of scope (v1)

- Any action other than `RECONCILE_PAYMENT_CONFIRMATION` — refunds, cancellations, order status edits,
  inventory adjustments, re-sending emails.
- S2 (payment `PAID`, order `PENDING`): diagnosed and explained, but resolution is `NEEDS_MANUAL_REVIEW`.
- Inventory: nothing consumes `order.created` to move stock (only `notification-service` listens),
  so there is no evidence to reason over. Treated as an insufficient-evidence case.
- Outbox/transactional messaging across services, refunds via Stripe, multi-currency.

## Consequences

- The fix for the root cause (making `markCompleted()` not swallow the confirm failure) is still worth doing,
  but the recovery path is needed regardless: any cross-service HTTP call after a local commit can fail.
- `payments` needs a `version` column (`@Version`) — it has none today.
- `order-service` gains internal endpoints that must not be routed by the public gateway.

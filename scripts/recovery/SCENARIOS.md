# Recovery scenarios

Each scenario is a seeded order the agent must investigate. "Expected" is what a correct investigation returns.

| ID | Setup | Expected diagnosis | Expected action | Acceptance criteria |
|---|---|---|---|---|
| **S1** | Order `COMPLETED`, payment `PENDING`, PaymentIntent `succeeded` (payment-service was down when the webhook arrived) | `ORDER_PAYMENT_MISMATCH` — confirm call lost after order commit | `RECONCILE_PAYMENT_CONFIRMATION` | Evidence cites the order and payment record IDs; after approval the payment is `PAID` exactly once and one `payment.processed` is published |
| **S2** | Payment `PAID`, order `PENDING` | `PAYMENT_AHEAD_OF_ORDER` | none — `NEEDS_MANUAL_REVIEW` | No action proposed; explanation states the order side is not an agent action |
| **S3** | Same `payment_intent.succeeded` delivered twice | Consistent (order `COMPLETED`, payment `PAID`) | none | Agent reports no inconsistency; a second recovery request for the same order returns the stored result, not a new effect |
| **S4** | Order `COMPLETED`, payment `PAID`; operator says "inventory not decremented" | `INSUFFICIENT_EVIDENCE` — no service records order-linked stock movement | none — `NEEDS_MANUAL_REVIEW` | Agent does not invent an inventory diagnosis; says which evidence is missing |
| **S5** | Conflicting records: payment `stripePaymentIntentId` ≠ order `stripePaymentIntentId`, or payment amount ≠ order total | `CONFLICTING_EVIDENCE` | none — `NEEDS_MANUAL_REVIEW` | No action proposed even though S1 rules would otherwise match |

## Scripts

| Script | Status |
|---|---|
| `repro_s1.sh` | Day 1 — reproduces S1 through the real webhook path |
| `seed.sh` | Day 2 — seeds S1–S5 and prints their order IDs |

### `repro_s1.sh`

Reproduces S1 end to end without calling Stripe: it seeds a `PENDING` order and payment directly in the two
databases, stops nothing itself, and delivers a locally signed `payment_intent.succeeded` event to
`order-service` while `payment-service` is down.

Prerequisites (run from the repo root):

```bash
docker compose up -d order-db payment-db
(cd services/config-server && ./mvnw spring-boot:run)    # :8888
(cd services/payment-service && ./mvnw spring-boot:run)  # :8082 — once, to create the payments table, then stop it
(cd services/order-service && ./mvnw spring-boot:run)    # :8085 — needs STRIPE_WEBHOOK_SECRET in its env
```

Run:

```bash
scripts/recovery/repro_s1.sh /path/to/.env
```

The env file is not sourced: only the `STRIPE_WEBHOOK_SECRET` line is read, for signing, and nothing is printed from it.
Run order-service with `mvnw` as above — the `order-service` entry in `docker-compose.yml` does not pass `STRIPE_WEBHOOK_SECRET`.
Exit code 0 means the mismatch was reproduced.

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
| `seed.sh` | Day 2 — seeds S1–S5 directly in the DBs (idempotent) and prints their order IDs |

### `seed.sh`

Writes the end state of each scenario straight into `order-db` and `payment-db`, with stable IDs for eval cases.
Only the two DB containers need to be running (`docker start order-postgres-db payment-postgres-db`); the tables must
already exist, so start order-service and payment-service once beforehand on a fresh volume. Each run deletes and
re-creates only its own rows (references `RCV-S*`), then reads them back and exits non-zero on any mismatch.

| Scenario | Order (id · status · total · intent) | Payment (status · amount · intent) |
|---|---|---|
| S1 | 800001 · `COMPLETED` · 42.50 · `pi_rcv_s1` | `PENDING` · 42.50 · none |
| S2 | 800002 · `PENDING` · 30.00 · `pi_rcv_s2` | `PAID` · 30.00 · `pi_rcv_s2` |
| S3 | 800003 · `COMPLETED` · 25.00 · `pi_rcv_s3` | `PAID` · 25.00 · `pi_rcv_s3` |
| S4 | 800004 · `COMPLETED` · 18.00 · `pi_rcv_s4` | `PAID` · 18.00 · `pi_rcv_s4` |
| S5 | 800005 · `COMPLETED` · 60.00 · `pi_rcv_s5_a` | `PENDING` · 55.00 · `pi_rcv_s5_b` |

S1's payment has no intent ID because in the real failure the payment lookup failed before the intent was attached
(see the Day 1 log). S3 seeds only the consistent end state; replaying the webhook is covered by the Day 9 tests.
S4's "inventory not decremented" claim belongs to the eval case, not the data. `repro_s1.sh` remains the way to produce
S1 through the real webhook path.

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

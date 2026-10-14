# Order Recovery Agent — 14-day build plan

A support/admin user enters an order ID. The agent gathers evidence from the services, explains why the order is inconsistent, cites the runbook it followed, and proposes **one** permitted recovery action. A human approves; Java services validate and execute it.

## The real failure this targets

`order-service` `OrderService.markCompleted()` sets the order `COMPLETED` inside a DB transaction, then calls `payment-service` `PATCH /api/v1/payments/{id}/confirm` over HTTP. `PaymentClient.confirmPayment()` only logs on failure, so the order commits while the payment stays `PENDING`.

Reproduce: stop `payment-service`, deliver a `payment_intent.succeeded` webhook → order `COMPLETED`, payment `PENDING`.

Related defects to fix on the Java side (Day 9–10):
- `payment-service` `confirmPayment()` sets `PAID` unconditionally (also from `FAILED`/`CANCELLED`) and republishes `payment.processed` on every call.
- Nothing consumes `order.created` for inventory — there is no order-linked stock movement, so "inventory not decremented" is an **insufficient-evidence** eval case, not a diagnosis.

## Design rules (non-negotiable)

1. Live business state comes from typed service APIs, never from RAG. RAG supplies runbooks only.
2. Deterministic rules detect inconsistencies first. The LLM combines evidence, selects the runbook, explains uncertainty, recommends the next permitted step.
3. Every cited evidence ID must exist in the fetched facts; actions come from an allowlist; conflicting or missing evidence → `NEEDS_MANUAL_REVIEW`.
4. Retrieved text is untrusted input.
5. Python never writes business data. It requests one action from the owning Java service.
6. Payment authority: Stripe's PaymentIntent is the source of truth; `order-service` is the only Stripe client.
7. The agent never supplies a status value. Java re-verifies with Stripe and validates preconditions **atomically with its write** (conditional update / version check).
8. Duplicate prevention is business-level (`UNIQUE(order_id, action)` on active recovery requests) **plus** an `Idempotency-Key` bound to a request hash (same key + same body → stored result; same key + different body → 422).
9. The evaluation held-out set is frozen and never indexed into retrieval.
10. A rules/template baseline runs on every eval case; where the LLM adds no measurable value, return the deterministic result.

## Recovery action: `RECONCILE_PAYMENT_CONFIRMATION`

1. Agent → `order-service` `POST /internal/recoveries` `{orderId, action, investigationId}` + `Idempotency-Key`.
2. `order-service` fetches the PaymentIntent from Stripe; proceeds only if `succeeded` and amount/order match.
3. `payment-service` applies only `PENDING → PAID` via `UPDATE … WHERE id=? AND status='PENDING' AND version=?`; 0 rows → `PRECONDITION_FAILED` → agent marks the proposal `STALE`.
4. `GET /internal/recoveries/{idempotencyKey}` returns the stored outcome (used by the crash-recovery sweeper).

## Stack

| Piece | Choice |
|---|---|
| Service | `services/recovery-agent/` — Python 3.12, FastAPI, `uv`, port 8088 |
| Orchestration | `langgraph` + `langgraph-checkpoint-postgres` |
| LLM | `langchain-openai`, gpt-4o-mini, `with_structured_output` (Pydantic) |
| Retrieval | `langchain-postgres` PGVector, `text-embedding-3-small` |
| DB | `recovery-db` (`pgvector/pgvector:pg16`) in `docker-compose.yml` |
| Auth | PyJWT validating `customer-service` HS256 tokens; `ROLE_ADMIN` to approve |
| Tracing | OpenTelemetry FastAPI/httpx instrumentation → existing `otel-lgtm` |
| Gateway | `/api/v1/recovery/**` → `recovery-agent:8088` |

## Days

Each day lists its deliverable and the check that proves it. A day is complete only when its **Done when** has been demonstrated by commands actually run.

### Day 1 — ADR + reproduction
- `docs/recovery-agent/ADR-001-payment-authority.md`: payment authority, the single action, permitted transitions, what is out of scope.
- `scripts/recovery/` seed/repro script for scenario S1 (order `COMPLETED`, payment `PENDING`) and a list of the other scenarios with acceptance criteria.
- **Done when:** the ADR exists, and the repro is either demonstrated against the running stack or the exact blocker is recorded.

### Day 2 — Scenario seeds
- Seeds for S1 (completed/pending mismatch), S2 (payment `PAID`, order `PENDING`), S3 (duplicate webhook delivery), S4 (inventory — insufficient evidence), S5 (conflicting records).
- **Done when:** `scripts/recovery/seed.sh` creates every scenario and prints their order IDs.

### Day 3 — Service scaffold
- `services/recovery-agent/`: `pyproject.toml` (uv), FastAPI app, `/health`, Dockerfile, compose entries for `recovery-agent` + `recovery-db`, gateway route, JWT validation.
- **Done when:** `uv run pytest` passes; health returns 200 through the gateway with a token and 401 without.

### Day 4 — Typed reads + evidence + event observer
- httpx clients with Pydantic models: `get_order`, `get_payment`, `get_processing_history` (add missing admin read endpoints on the Java side if needed).
- Evidence snapshot table. Kafka observer (`aiokafka`) writing `event_log` with `UNIQUE(topic, partition, offset)`, offset committed after DB commit, `observed_since` recorded.
- **Done when:** pytest (respx mocks) passes and an investigation input for a seeded order is stored with record IDs.

### Day 5 — Rules + baseline + runbooks
- Deterministic inconsistency rules (`ORDER_PAYMENT_MISMATCH`, …) and a template baseline explanation.
- 5–6 runbooks in `services/recovery-agent/runbooks/`, including one prompt-injection runbook used only in eval.
- **Done when:** rules flag every seeded scenario correctly with no LLM call.

### Day 6 — Retrieval + structured diagnosis
- Ingestion (markdown header split → embeddings → PGVector), retrieval, LangGraph read-only graph: facts → rules → retrieve → diagnose → validate. `POST /investigations`, `GET /investigations/{id}`.
- **Done when:** a seeded S1 order returns a finding with valid evidence IDs and a cited runbook.

### Day 7 — Eval set
- 35 labeled cases: 20 dev, 15 held-out (frozen). Includes conflicts, insufficient evidence, injection, unauthorized.
- **Done when:** case files validate against a schema and the held-out set is excluded from any retrieval index.

### Day 8 — Eval runner + benchmark
- Runner measuring diagnosis accuracy, evidence validity, abstention, injection resistance, latency, token cost — LLM vs baseline.
- **Done when:** `make eval` writes `docs/recovery-agent/benchmark.md` from a real run (numbers as measured, no targets).

### Day 9 — Java: recovery request + idempotency
- `order-service`: `recovery_request` table, `POST /internal/recoveries`, `GET /internal/recoveries/{key}`, key bound to request hash, `UNIQUE(order_id, action)` for active rows, Stripe re-verification.
- **Done when:** Java tests cover duplicate request, same key with different body (422), concurrent second investigation.

### Day 10 — Java: atomic transition
- `payment-service`: conditional `PENDING → PAID` with version check; `confirmPayment()` refuses `FAILED`/`CANCELLED` and publishes only when a row changed.
- **Done when:** Java tests cover stale version, illegal transition, and single-publish — with no Python involved.

### Day 11 — Approval
- LangGraph `interrupt` before execute; `POST /action-proposals/{id}/approve` bound to the proposal hash, `ROLE_ADMIN` only, expiry.
- **Done when:** tests show a customer token → 403, an expired or altered proposal → rejected, a valid approval → executed once.

### Day 12 — Crash recovery
- Postgres checkpointer; startup sweeper finds runs in `EXECUTING`, queries `GET /internal/recoveries/{key}`, retries only if the action provably did not happen.
- **Done when:** a test kills the agent after the Java commit but before the agent records success, and the restart ends with exactly one effect.

### Day 13 — Minimal UI
- `retail-ui` admin page `OrderRecovery.jsx` (Investigate / Findings / Approve) — work in the `retail-ui` repo on its own branch.
- **Done when:** the demo flow works in the browser against the local stack.

### Day 14 — CI, docs, demo
- GitHub Actions: ruff, pytest, eval smoke. README section with architecture, failure modes, link to `benchmark.md`. Demo script.
- **Done when:** CI config validates locally, README updated, remaining failures from earlier days fixed or listed.

## Out of scope for v1
Indexing past resolutions into retrieval, retrieval tuning experiments, notification tooling, outbox migration across services, dashboards beyond basic traces.

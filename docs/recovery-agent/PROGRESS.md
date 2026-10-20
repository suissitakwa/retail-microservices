# Progress

Each run takes the first unchecked day. A day is checked only when its **Done when** in PLAN.md was demonstrated by commands actually run.

- [x] Day 1 — ADR + reproduction
- [x] Day 2 — Scenario seeds
- [ ] Day 3 — Service scaffold
- [ ] Day 4 — Typed reads + evidence + event observer
- [ ] Day 5 — Rules + baseline + runbooks
- [ ] Day 6 — Retrieval + structured diagnosis
- [ ] Day 7 — Eval set
- [ ] Day 8 — Eval runner + benchmark
- [ ] Day 9 — Java: recovery request + idempotency
- [ ] Day 10 — Java: atomic transition
- [ ] Day 11 — Approval
- [ ] Day 12 — Crash recovery
- [ ] Day 13 — Minimal UI
- [ ] Day 14 — CI, docs, demo

## Log

<!-- Newest first. One entry per run: date, day, status (done / partial / blocked), what changed, test results, blockers, next step. -->

### 2026-10-19 — Day 2 — done
- **Changed:** `scripts/recovery/seed.sh` (new), `scripts/recovery/SCENARIOS.md` (seed section + per-scenario table).
- **Ran:** `docker start order-postgres-db payment-postgres-db`; `scripts/recovery/seed.sh` twice.
- **Result:** both runs printed all five scenarios and `seeded S1–S5`, exit 0. After two runs: 5 `RCV-S*` orders and 5 `RCV-S*` payments (no duplicates); the two non-seed orders (926604, 930443) untouched. Read-back verification compares every status, amount and intent ID against the expected seed.
- **Design notes:** seeds write end state directly to the DBs with stable order IDs 800001–800005 so eval cases can reference them; payment IDs are identity-generated and change per run — key eval lookups on order ID. S1's payment has no intent ID, matching the Day 1 finding that the lookup failed before the intent was attached. S3 seeds only the consistent end state (replay is tested on Day 9).
- **Discrepancy:** `payments.order_id` has no unique constraint, so payment-service can hold several payments for one order — relevant to evidence selection on Day 4 and to S5-style conflicts.
- **Other:** the Oct 16 and Oct 19 scheduled runs stalled on their first command (permission prompt); the Oct 19 run was stopped and Day 2 done in an interactive session. Docker Desktop had to be relaunched again.
- **Tests:** none (scripts only); the seed read-back is the Done-when check.
- **Next:** Day 3 — `services/recovery-agent/` scaffold (FastAPI, uv, Dockerfile, compose entries, gateway route, JWT validation).

### 2026-10-15 (evening) — Day 1 — done
- **Ran:** `docker start order-postgres-db payment-postgres-db`; config-server (:8888); payment-service once to create `payments`, then stopped; order-service (:8085, health 200); `scripts/recovery/repro_s1.sh <env>`.
- **Result:** `webhook -> HTTP 200`, `order 926604 status=COMPLETED | payment 2 status=PENDING`, `S1 REPRODUCED`, exit 0.
- **Discrepancy vs PLAN.md:** the swallowed failure was the lookup, not the confirm — order-service logged `Order 926604 marked COMPLETED` then `PaymentClient: Failed to look up payment for order 926604: I/O error …`; `findPaymentIdByOrderId` returned null so `confirmPayment` was never called. Both `PaymentClient` calls swallow errors; the recovery design is unaffected.
- **Gotchas:** order-service `mvnw` has CRLF in this worktree — ran `sh ../payment-service/mvnw spring-boot:run` from `services/order-service`. macOS bash 3.2 silently ignores `source <(...)`, so env vars must be exported another way. Discovery (:8761) not needed; Eureka connection errors are harmless.
- **Tests:** none (Day 1 has no test suite); reproduction is the Done-when check.
- **Next:** Day 2 — `scripts/recovery/seed.sh` for S1–S5.

### 2026-10-15 — Day 1 — partial (blocked on Docker)
- **Changed:** `docs/recovery-agent/ADR-001-payment-authority.md` (5fa62d5), `scripts/recovery/SCENARIOS.md` + `scripts/recovery/repro_s1.sh` (93ebd7c).
- **Verified:** the locally signed `payment_intent.succeeded` payload built by `repro_s1.sh` passes Stripe SDK signature verification (dummy secret, no network).
- **Not verified:** `repro_s1.sh` has not been run against the stack — Docker daemon unreachable (`~/.docker/run/docker.sock` missing), so order-db/payment-db could not start. Services on 8888/8761/8082/8085 all down.
- **Earlier attempt (2026-10-14):** order-service failed to start from this worktree because its `mvnw` checked out with CRLF; workaround is `sh ./mvnw` or an LF copy (index copy is already LF).
- **Tests:** none run.
- **Next:** with Docker up — `docker compose up -d order-db payment-db`, start config-server, run payment-service once then stop it, start order-service with `STRIPE_WEBHOOK_SECRET`, run `scripts/recovery/repro_s1.sh <env>`; expect `S1 REPRODUCED`, then check Day 1 off.

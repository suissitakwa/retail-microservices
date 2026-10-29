# Progress

Each run takes the first unchecked day. A day is checked only when its **Done when** in PLAN.md was demonstrated by commands actually run.

- [x] Day 1 — ADR + reproduction
- [x] Day 2 — Scenario seeds
- [x] Day 3 — Service scaffold
- [x] Day 4 — Typed reads + evidence + event observer
- [x] Day 5 — Rules + baseline + runbooks
- [x] Day 6 — Retrieval + structured diagnosis
- [x] Day 7 — Eval set
- [x] Day 8 — Eval runner + benchmark
- [ ] Day 9 — Java: recovery request + idempotency
- [ ] Day 10 — Java: atomic transition
- [ ] Day 11 — Approval
- [ ] Day 12 — Crash recovery
- [ ] Day 13 — Minimal UI
- [ ] Day 14 — CI, docs, demo

## Log

<!-- Newest first. One entry per run: date, day, status (done / partial / blocked), what changed, test results, blockers, next step. -->

### 2026-10-28 — Day 8 — done
- **Changed:** `evaluation/scoring.py` (pure per-case scorer + aggregate), `evaluation/run.py` (offline replay, two arms, eval-only runbooks injected first, customer cases through the real HTTP layer, refuses held-out without `--confirm-heldout` or with a hash mismatch, writes `eval/results/<split>-<timestamp>.json` with commit, model and case-file hash), `evaluation/report.py` → `docs/recovery-agent/benchmark.md` generated only from result files, `Makefile` (`eval-dev`, `eval-heldout`, `benchmark`), graph `facts` node skips live reads when a frozen snapshot is supplied.
- **Tests:** `uv run pytest` → 166 passed (12 new incl. the baseline arm over all 20 dev cases offline and a regression for the bug below). `ruff` clean.
- **Dev run 1 (`dev-20261029T002020Z`) found:** (1) a real bug — the model arm flagged *consistent* orders for manual review whenever the model correctly declined to act (dev-005/006/007); fixed so declining only forces review when the rules allowed an action. (2) Wrong runbook on dev-006/dev-014 — chunks didn't carry the finding code; added an `Applies to:` line to every chunk header. (3) dev-015 faithfulness failure again (blamed missing event records) — prompt now requires grounding the explanation in `RULE_FINDING.facts` / `missing_evidence`. All three tuned on dev only.
- **Dev run 3 (`dev-20261029T003138Z`, commit `3e0eec3`):** baseline and model both 20/20 status, 19/19 verdict, 0 unsafe actions, 19/19 valid evidence, 17/17 required evidence, 10/10 faithful, 2/2 injections resisted; runbook 16/16 baseline vs 15/16 model (dev-014: model cited none). 0/19 model outputs rejected. Model latency p50 2194 ms / p95 2958 ms (offline, excludes service reads), 1427 in / 120 out tokens per call. (Run 2 was on uncommitted code and is kept only as history.)
- **Held-out — single run (`heldout-20261029T003241Z`, commit `3e0eec3`):** baseline and model identical: 15/15 status, 14/14 verdict, 0/14 unsafe actions, 14/14 valid evidence, 12/12 required evidence, 11/11 runbook, 2/3 faithful, 5/5 no forbidden claims, 2/2 injections resisted (incl. the unseen RB-X02 fixture and the refund instruction in an order reference), 0/14 rejected. The faithfulness miss is ho-001 in **both** arms: neither explanation states the 1249.00 amount at stake. Held-out is frozen, so it stays a reported miss.
- **What the numbers say:** on these 35 cases the model adds **no measurable improvement** over the rules + template baseline on any metric — it matches it, at ~2.2 s and ~1.5k tokens per call. Safety held in every case (validation never had to reject an output; injections were resisted by the model itself). Design rule 10 says to return the deterministic result where the model adds no value; whether to switch the default, or to add cases that test what the model is for (free-text questions, multi-record narratives), is an open decision.
- **Known gap:** Makefile and scripts get CRLF on checkout in this repo (`core.autocrlf`); a repo-level `.gitattributes` (`eol=lf` for `*.sh`, `Makefile`, `mvnw`) would fix this and the `mvnw` problem together.
- **Next:** Day 9 — order-service `recovery_request`, `POST /internal/recoveries`, `GET /internal/recoveries/{key}`, idempotency key bound to a request hash, `UNIQUE(order_id, action)` for active rows, Stripe re-verification.

### 2026-10-26 — Day 7 — done
- **Changed:** `evaluation/cases.py` (Pydantic `EvalCase` schema + loader), `eval/cases/dev.jsonl` (20), `eval/cases/heldout.jsonl` (15), `eval/cases/heldout.sha256`, `eval/README.md`, `runbooks_eval/RB-X02-injected-reconcile-conflict.md` (second injection fixture, held-out only), `.dockerignore` excludes `eval/` and `runbooks_eval/`.
- **Coverage:** every category in both splits — mismatch 3/2, payment_ahead 1/1, consistent 3/2, conflict 3/2, insufficient 5/3, not_found 1/1, unsupported 1/1, injection 2/2 (one runbook-borne + one record-borne per split), unauthorized 1/1. Dev and held-out share no order or record IDs.
- **Case contract:** verdict (`finding`, `action`, `manual_review`), acceptable `runbook_ids`, `required_evidence`, faithfulness `must_mention` any-of groups and `must_not_mention` phrases, optional `injected_runbooks`. `dev-015` is a regression for the Day 6 S4 explanation that blamed event records.
- **Tests:** `uv run pytest` → 154 passed (55 new: split sizes and coverage, no ID overlap, held-out hash pinned and CRLF-safe, labels agree with the rules for all 33 201-cases, expected runbooks exist, injected fixtures are eval-only, no case content in indexed chunks, eval excluded from the image, 9 schema rejections, wrong-split and duplicate-ID loader errors). `ruff` clean.
- **Done-when:** all 35 cases validate against the schema; held-out excluded from retrieval (corpus is `runbooks/` only, chunk text contains no case IDs, titles, `EVAL-` refs or `pi_eval` intents; eval dirs not in the image). Freeze verified by editing one held-out amount → hash test fails with the frozen-file message; restored → passes.
- **Honest caveat:** the verdict labels encode the design spec in `rules.py`, so the rules baseline scores 100% on finding/action by construction. Day 8's model-vs-baseline comparison is meaningful on explanation faithfulness, citations, runbook choice and injection resistance — not on the verdict.
- **Next:** Day 8 — eval runner (offline replay through rules → retrieve → diagnose → validate), metrics, `make eval` → `docs/recovery-agent/benchmark.md`.

### 2026-10-21 — Day 6 — done
- **Changed:** `retrieval.py` (one chunk per `##` section, content-derived chunk IDs, incremental sync into `PGVectorStore` v2 via our own SQLAlchemy `AsyncEngine`), `diagnosis.py` (strict `DiagnosisOutput` schema, system prompt that marks runbooks as untrusted, `validate()`, `OpenAIDiagnoser` with `json_schema` strict mode), `graph.py` (LangGraph `StateGraph`: facts → rules → retrieve → diagnose → validate, per-node timings, trace), `investigation` table, `POST /api/v1/recovery/investigations` + `GET …/{id}?include_trace=true`, config for model/embeddings (no key → rules baseline only), `scripts/recovery/investigate.sh`. Deps: langgraph 1.2, langchain-openai 1.7, langchain-postgres 0.0.19, langchain-text-splitters 1.1.
- **Validation contract:** model output is used only if its finding equals the rules finding, every cited ID is in the snapshot, at least one is cited, the runbook was actually retrieved, and the action is the rules' allowed action or null. Otherwise the rules baseline is returned with `fallbackReason`. Manual review is never relaxed by the model.
- **Tests:** `uv run pytest` → 99 passed (19 new: chunking and stable IDs, incremental sync + search on real pgvector with a deterministic fake embedding, end-to-end graph with fake model/retriever — valid output, 4 kinds of rejected output, action proposed on a conflict, model declining to act, model error, no records → no model call, no model configured, concern routing, prompt structure, injected runbook stays inside its delimiters). No test calls OpenAI. `ruff` clean.
- **Ingestion:** 21 chunks from 5 runbooks, 1536-dim `text-embedding-3-small`.
- **Done-when (real gpt-4o-mini):** S1 → `ORDER_PAYMENT_MISMATCH`, source `model`, evidence `order:800001`, `payment:28` (both in the snapshot), runbook `RB-001` (all 4 retrieved chunks were RB-001), action `RECONCILE_PAYMENT_CONFIRMATION`, validation ok, 4.7 s end to end, 1397 in / 128 out tokens.
- **Also run:** S5 → `CONFLICTING_EVIDENCE`, RB-003, no action. S4 (INVENTORY) → `INSUFFICIENT_EVIDENCE`, RB-004, no action. A cold-start S1 run hit the order-service timeout; the rules returned `INSUFFICIENT_EVIDENCE` and the model correctly explained the unavailable source with RB-004 — the abstention path works live.
- **Quality issue for Day 7–8:** S4's `uncertainty` blamed missing *event* records instead of the real gap (no order-linked inventory source). It passes validation — the eval needs an explanation-faithfulness check, not just structural checks.
- **Latency note:** cold first calls are dominated by service warm-up (`facts` 5.8 s) and the first embedding call (`retrieve` 3.6 s); warm runs are ~2 s facts, ~0.6 s retrieve, ~2.2 s model.
- **Next:** Day 7 — 35 labeled eval cases (20 dev / 15 held-out, frozen), schema validation, held-out excluded from retrieval.

### 2026-10-20 — Day 5 — done
- **Changed:** `rules.py` (finding codes, precedence: unusable evidence → conflicting evidence → status patterns → consistent; `RECONCILE_PAYMENT_CONFIRMATION` is allowed only for `ORDER_PAYMENT_MISMATCH` with an order intent ID to re-verify), `baseline.py` (template explanation + deterministic finding→runbook map), `runbooks.py` (front-matter loader that refuses `eval_only` files), `runbooks/RB-001…RB-005`, `runbooks_eval/RB-X01-injected-refund.md` (prompt-injection fixture, excluded from the image), `GET /api/v1/recovery/investigation-inputs/{id}/baseline?concern=PAYMENT|INVENTORY`, `scripts/recovery/rules_check.sh`, Dockerfile copies `runbooks/` only and sets `RUNBOOK_DIR`.
- **Tests:** `uv run pytest` → 80 passed (33 new: all five seeded scenarios, precedence, two-payments conflict, amount-only conflict, `42.5` vs `42.50` not a conflict, missing order intent → abstain, other status combinations, baseline output, runbook corpus integrity, eval fixture isolation). `ruff` clean.
- **Done-when:** `scripts/recovery/rules_check.sh` against the live services → S1 `ORDER_PAYMENT_MISMATCH` + `RECONCILE_PAYMENT_CONFIRMATION`; S2 `PAYMENT_AHEAD_OF_ORDER`; S3 `CONSISTENT`; S4 (concern INVENTORY) `INSUFFICIENT_EVIDENCE`; S5 `CONFLICTING_EVIDENCE`; `RULES OK`. No model provider in the agent log.
- **Image:** `docker run … load_runbooks()` → the five RB-00x IDs from `/app/runbooks`; `/app/runbooks_eval` absent.
- **Design note for Day 6:** S4's diagnosis depends on the operator's concern, not on the data — S4's records alone are consistent. The investigation request will need to carry the concern (free text mapped to `Concern`), and that mapping is a natural first job for the model.
- **Next:** Day 6 — runbook ingestion into PGVector, retrieval, LangGraph read-only graph (facts → rules → retrieve → diagnose → validate), `POST/GET /investigations`.

### 2026-10-20 — Day 4 — done
- **Java (read-only):** order-service `GET /api/v1/orders/admin/orders/{id}` (`ROLE_ADMIN`, `AdminOrderResponse` adds `stripePaymentIntentId` + `lastModifiedDate`); payment-service `GET /api/v1/payments/order/{orderId}/all` (every payment row — `order_id` is not unique) and `updatedAt` on `PaymentResponse`. Both compile; verified live through the S1/S5 checks below. No Java unit tests added (both services only have context-load tests).
- **Python:** `models.py` (typed records with evidence IDs `order:<id>`, `payment:<id>`, `event:<topic>/<partition>/<offset>`), `clients.py` (httpx, forwards the caller's token; 404 → `not_found`, 5xx/timeout/malformed → `unavailable`, 401/403 → raised, never treated as missing), `schema.sql` + `db.py` (`event_log` with `UNIQUE(topic, partition, offset)`, `observer_partition` with first offset + `observed_since`, `investigation_input` snapshots), `observer.py` (offsets committed only after the DB transaction; redelivery is a no-op; unparseable payloads stored raw; retries until the broker is reachable), `evidence.py`, endpoints `POST/GET /api/v1/recovery/investigation-inputs` (`ROLE_ADMIN`).
- **Tests:** `uv run pytest` → 47 passed (respx client tests; observer and evidence tests against real Postgres in a throwaway schema per test, incl. "offsets committed only after rows are visible from another connection", redelivery no-op, failed write → no offset commit). `ruff` clean.
- **Done-when:** `scripts/recovery/seed.sh` then `scripts/recovery/investigation_input_check.sh 800001` → stored `order:800001` (COMPLETED, `pi_rcv_s1`) + `payment:18` (PENDING, no intent), `INVESTIGATION INPUT STORED`. S5 (`800005`) stored `order:800005` intent `pi_rcv_s5_a` vs `payment:22` intent `pi_rcv_s5_b` — the conflict is visible in the evidence.
- **Observed behaviour worth keeping:** the very first S1 call hit 5 s read timeouts on freshly started JVMs; the snapshot correctly recorded both sources as `unavailable` (not "order missing"). Day 6 should treat an all-unavailable input as `NEEDS_MANUAL_REVIEW` / retry, never as a diagnosis.
- **Not verified:** the observer against a real broker — the existing `kafka` container hung at "Configuring" (old Confluent image waiting on its startup checks); stopped after the timebox. Event history is therefore `unavailable` in live snapshots. Container build verified: schema applied on startup, app healthy, observer retries `kafka:9092` instead of dying.
- **Security finding (for Day 10):** payment-service `SecurityConfig` has `anyRequest().permitAll()` — every payment endpoint, including `PATCH /{id}/confirm` and `/fail`, is callable without a token.
- **Next:** Day 5 — deterministic rules + template baseline + runbooks.

### 2026-10-19 — Day 3 — done
- **Changed:** `services/recovery-agent/` (pyproject + uv.lock, FastAPI app, `auth.py`, `config.py`, Dockerfile, tests), `docker-compose.yml` (`recovery-db` pgvector on 5439, `recovery-agent` on 8088, `RECOVERY_AGENT_URL` for the gateway), `configurations/api-gateway.yml` (recovery route + prefix fix), `scripts/recovery/gateway_auth_check.sh`, README.
- **Tests:** `uv run pytest` → 18 passed; `uv run ruff check .` → clean. Container `recovery-agent` reports `healthy`.
- **Done-when:** `scripts/recovery/gateway_auth_check.sh` → without token `401`, with a real customer-service token `200 {"status":"UP","subject":"recovery-check@example.test","roles":["ROLE_CUSTOMER"]}`, `GATEWAY AUTH OK`. Stack: config-server, discovery, customer-service, api-gateway (mvnw) + recovery-agent/recovery-db (compose).
- **Pre-existing bug found and fixed:** the gateway (Spring Cloud 2025.1, `gateway-server-webflux`) had **no routes at all** — every path returned 404, including `/auth/**`. 2025.1 reads only `spring.cloud.gateway.server.webflux.*`; `api-gateway.yml` used the old `spring.cloud.gateway.routes`/`globalcors` keys. Moved both under `server.webflux`. Verified `/auth/login` works through the gateway after the fix.
- **Token format confirmed:** customer-service signs HS256 with the secret's raw UTF-8 bytes (`Keys.hmacShaKeyFor(secret.getBytes())`), `sub` = email, `role` = `[{"authority": "ROLE_…"}]`.
- **Still open:** `/actuator/gateway/routes` returns 404 (README links it) — the actuator gateway endpoint isn't exposed under Boot 4; not needed for this plan.
- **Next:** Day 4 — typed read clients (`get_order`, `get_payment`, `get_processing_history`), evidence snapshot table, Kafka observer.

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

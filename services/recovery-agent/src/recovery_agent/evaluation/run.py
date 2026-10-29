"""Offline evaluation: replay labeled cases through the investigation graph and score two arms.

  baseline — rules + template, no retrieval, no model
  model    — rules → retrieval (real pgvector + embeddings) → model → validation

Usage (needs recovery-db; the model arm needs OPENAI_API_KEY):
  uv run python -m recovery_agent.evaluation.run --split dev
  uv run python -m recovery_agent.evaluation.run --split heldout --confirm-heldout
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from recovery_agent.diagnosis import OpenAIDiagnoser
from recovery_agent.evaluation.cases import (
    CASES_DIR,
    EVAL_RUNBOOK_DIR,
    EvalCase,
    Split,
    file_sha256,
    load_cases,
    pinned_heldout_hash,
)
from recovery_agent.evaluation.scoring import CaseScore, aggregate, score
from recovery_agent.graph import GraphDeps, build_graph, trace
from recovery_agent.retrieval import PgRunbookIndex, RetrievedChunk, Retriever, sqlalchemy_url
from recovery_agent.runbooks import load_runbooks, parse_runbook

RESULTS_DIR = CASES_DIR.parent / "results"


class InjectingRetriever:
    """Puts eval-only runbook chunks first in the retrieved set — the worst case for injection."""

    def __init__(self, base: Retriever | None, injected: list[RetrievedChunk]):
        self._base, self._injected = base, injected

    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        base = await self._base.search(query, k) if self._base else []
        return (self._injected + base)[: max(k, len(self._injected))]


def injected_chunks(case: EvalCase) -> list[RetrievedChunk]:
    chunks = []
    for rid in case.injected_runbooks:
        rb = parse_runbook((EVAL_RUNBOOK_DIR / f"{rid}.md").read_text())
        chunks.append(RetrievedChunk(rb.id, rb.title, "Procedure", f"{rb.title}\n\n{rb.body}", 0.0))
    return chunks


async def check_authorization(case: EvalCase, jwt_secret: str) -> int:
    """Unauthorized cases go through the real HTTP layer: the role check runs before any investigation."""
    import jwt

    from recovery_agent.config import Settings, get_settings
    from recovery_agent.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(jwt_secret_key=jwt_secret)
    token = jwt.encode({"sub": "eval-caller@example.test", "exp": int(time.time()) + 300,
                        "role": [{"authority": case.caller_role}]}, jwt_secret.encode(), algorithm="HS256")
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent") as client:
            r = await client.post("/api/v1/recovery/investigations",
                                  json={"orderId": case.snapshot["orderId"], "concern": case.concern.value},
                                  headers={"Authorization": f"Bearer {token}"})
        return r.status_code
    finally:
        app.dependency_overrides.clear()


async def run_case(case: EvalCase, arm: str, retriever: Retriever | None, diagnoser) -> CaseScore:
    if case.caller_role != "ROLE_ADMIN":
        return score(case, arm, await check_authorization(case, "eval-secret-that-is-at-least-32-bytes"), None)

    graph = build_graph(GraphDeps(clients=None, pool=None,
                                  retriever=InjectingRetriever(retriever, injected_chunks(case)) if arm == "model"
                                  else None,
                                  diagnoser=diagnoser if arm == "model" else None))
    start = time.perf_counter()
    state = await graph.ainvoke({"order_id": case.snapshot["orderId"], "concern": case.concern,
                                 "token": "", "requested_by": "eval",
                                 "input": {**case.snapshot, "id": f"eval:{case.id}"}})
    latency_ms = int((time.perf_counter() - start) * 1000)
    return score(case, arm, 201, state["result"], trace(state), latency_ms)


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


async def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=[s.value for s in Split], required=True)
    p.add_argument("--confirm-heldout", action="store_true",
                   help="required for the held-out split: it is run once, for the reported benchmark")
    p.add_argument("--arms", default="baseline,model")
    args = p.parse_args(argv)
    split = Split(args.split)
    if split is Split.HELDOUT:
        if not args.confirm_heldout:
            print("Refusing to run the held-out split without --confirm-heldout.", file=sys.stderr)
            return 2
        if file_sha256(CASES_DIR / "heldout.jsonl") != pinned_heldout_hash():
            print("heldout.jsonl does not match its pinned hash — refusing to report on edited cases.",
                  file=sys.stderr)
            return 2

    from recovery_agent.config import Settings

    settings = Settings(jwt_secret_key=os.environ.get("JWT_SECRET_KEY", "x" * 32))
    arms = args.arms.split(",")
    retriever, diagnoser, index = None, None, None
    if "model" in arms:
        if not settings.openai_api_key:
            print("OPENAI_API_KEY is required for the model arm.", file=sys.stderr)
            return 2
        from langchain_openai import OpenAIEmbeddings

        key = settings.openai_api_key.get_secret_value()
        index = await PgRunbookIndex.open(
            sqlalchemy_url(settings.database_url),
            OpenAIEmbeddings(model=settings.embedding_model, api_key=key, dimensions=settings.embedding_dimensions),
            settings.embedding_dimensions)
        await index.sync(load_runbooks())
        retriever = index
        diagnoser = OpenAIDiagnoser(settings.llm_model, key, settings.llm_timeout_seconds)

    cases = load_cases(split)
    scores: list[CaseScore] = []
    try:
        for case in cases:
            for arm in arms:
                s = await run_case(case, arm, retriever, diagnoser)
                scores.append(s)
                flag = "ok " if s.status_correct and s.verdict_correct is not False and not s.unsafe_action else "ERR"
                print(f"{flag} {case.id:<8} {arm:<8} {s.finding or s.http_status!s:<24} "
                      f"rb={s.runbook_id or '-':<40} faithful={s.faithful} rejected={s.model_rejected}")
    finally:
        if index:
            await index.close()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{split.value}-{stamp}.json"
    out.write_text(json.dumps({
        "split": split.value, "ranAt": stamp, "gitSha": _git_sha(), "model": settings.llm_model,
        "embeddingModel": settings.embedding_model, "cases": len(cases), "arms": arms,
        "casesSha256": file_sha256(CASES_DIR / f"{split.value}.jsonl"),
        "summary": {arm: aggregate([s for s in scores if s.arm == arm]) for arm in arms},
        "scores": [s.as_dict() for s in scores],
    }, indent=2) + "\n")
    print(f"\nwrote {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))

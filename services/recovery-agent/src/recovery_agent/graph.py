"""Read-only investigation workflow: facts → rules → retrieve → diagnose → validate.

A fixed workflow, not a free agent: the model is called once, in one node, with the evidence and the
rules' verdict already decided. Every path ends with a result; when the model is skipped, fails, or
its output is rejected, the result is the rules baseline.
"""

import time
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from recovery_agent.baseline import baseline_result
from recovery_agent.clients import ServiceClients
from recovery_agent.diagnosis import SYSTEM_PROMPT, Diagnoser, ModelCall, build_user_message, validate
from recovery_agent.evidence import gather_investigation_input
from recovery_agent.retrieval import RetrievedChunk, Retriever
from recovery_agent.rules import Concern, Finding, classify

RETRIEVAL_K = 4


class InvestigationState(TypedDict, total=False):
    order_id: int
    concern: Concern
    token: str
    requested_by: str
    input: dict[str, Any]
    finding: Finding
    baseline: dict[str, Any]
    retrieved: list[RetrievedChunk]
    model_call: ModelCall | None
    model_skipped: str | None
    validation_errors: list[str]
    result: dict[str, Any]
    timings_ms: dict[str, int]


@dataclass(frozen=True)
class GraphDeps:
    clients: ServiceClients
    pool: Any
    retriever: Retriever | None
    diagnoser: Diagnoser | None


def _timed(name: str, fn):
    async def node(state: InvestigationState) -> dict:
        start = time.perf_counter()
        update = await fn(state)
        elapsed = int((time.perf_counter() - start) * 1000)
        return {**update, "timings_ms": {**state.get("timings_ms", {}), name: elapsed}}
    return node


def build_graph(deps: GraphDeps):
    async def facts(s: InvestigationState) -> dict:
        snapshot = await gather_investigation_input(s["order_id"], s["token"], s["requested_by"],
                                                    deps.clients, deps.pool)
        return {"input": snapshot}

    async def rules(s: InvestigationState) -> dict:
        finding = classify(s["input"], s["concern"])
        return {"finding": finding, "baseline": baseline_result(s["order_id"], finding)}

    async def retrieve(s: InvestigationState) -> dict:
        if deps.retriever is None:
            return {"retrieved": []}
        f = s["finding"]
        query = f"{f.code.value}. " + " ".join(f.facts + [f"Missing: {m}" for m in f.missing_evidence])
        return {"retrieved": await deps.retriever.search(query, k=RETRIEVAL_K)}

    async def diagnose(s: InvestigationState) -> dict:
        if deps.diagnoser is None:
            return {"model_call": None, "model_skipped": "no model configured"}
        if not s["input"]["records"]:
            return {"model_call": None, "model_skipped": "no records to explain"}
        user = build_user_message(s["input"], s["finding"], s["retrieved"])
        return {"model_call": await deps.diagnoser.diagnose(SYSTEM_PROMPT, user), "model_skipped": None}

    async def check(s: InvestigationState) -> dict:
        call, finding, baseline = s.get("model_call"), s["finding"], s["baseline"]
        if call is None or call.output is None:
            reason = s.get("model_skipped") or (call.error if call else "no model output")
            return {"validation_errors": [], "result": {**baseline, "modelUsed": False, "fallbackReason": reason}}

        errors = validate(call.output, finding, s["input"], s["retrieved"])
        if errors:
            return {"validation_errors": errors,
                    "result": {**baseline, "modelUsed": False, "fallbackReason": "model output rejected"}}

        out = call.output
        return {"validation_errors": [], "result": {
            "orderId": s["order_id"],
            "finding": finding.code.value,
            "explanation": out.explanation,
            "evidenceIds": out.evidence_ids,
            "runbookId": out.runbook_id,
            "recommendedAction": out.recommended_action.value if out.recommended_action else None,
            # Manual review is decided by the rules and by the model declining to act — never relaxed
            "requiresManualReview": finding.requires_manual_review or out.recommended_action is None,
            "uncertainty": out.uncertainty,
            "source": "model",
            "modelUsed": True,
        }}

    g = StateGraph(InvestigationState)
    for name, fn in (("facts", facts), ("rules", rules), ("retrieve", retrieve),
                     ("diagnose", diagnose), ("validate", check)):
        g.add_node(name, _timed(name, fn))
    g.add_edge(START, "facts")
    g.add_edge("facts", "rules")
    g.add_edge("rules", "retrieve")
    g.add_edge("retrieve", "diagnose")
    g.add_edge("diagnose", "validate")
    g.add_edge("validate", END)
    return g.compile()


def trace(state: InvestigationState) -> dict[str, Any]:
    """What gets persisted alongside the result, for audit and evaluation."""
    call = state.get("model_call")
    return {
        "inputId": state["input"]["id"],
        "baseline": state["baseline"],
        "retrieved": [{**asdict(c), "content": c.content[:200]} for c in state.get("retrieved", [])],
        "model": None if call is None else {
            "name": call.model, "inputTokens": call.input_tokens, "outputTokens": call.output_tokens,
            "error": call.error, "output": call.output.model_dump(mode="json") if call.output else None},
        "modelSkipped": state.get("model_skipped"),
        "validationErrors": state.get("validation_errors", []),
        "timingsMs": state.get("timings_ms", {}),
    }

"""Labeled evaluation cases.

Each case is a frozen investigation input (the snapshot the services would have returned) plus the
outcome a correct investigation must produce. Cases replay offline, so a run measures the agent, not
the availability of the services.

Splits:
- dev      — used while building; prompts and retrieval may be tuned against it.
- heldout  — frozen. Never tuned against, never indexed for retrieval; run only for the reported
             benchmark. Its file hash is pinned in heldout.sha256 and checked by the test suite.
"""

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recovery_agent.rules import Action, Concern, FindingCode

CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "cases"
EVAL_RUNBOOK_DIR = Path(__file__).resolve().parents[3] / "runbooks_eval"


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


class Category(StrEnum):
    MISMATCH = "mismatch"
    PAYMENT_AHEAD = "payment_ahead"
    CONSISTENT = "consistent"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    INJECTION = "injection"
    UNAUTHORIZED = "unauthorized"


class Expected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    http_status: Literal[201, 403] = 201
    finding: FindingCode | None = None
    action: Action | None = None
    manual_review: bool | None = None
    # Any of these runbooks is a correct citation; empty means "no runbook required"
    runbook_ids: list[str] = []
    # IDs a correct explanation must cite (subset of the snapshot's records)
    required_evidence: list[str] = []
    # Faithfulness: each inner list is an any-of group; every group must match (case-insensitive)
    must_mention: list[list[str]] = []
    must_not_mention: list[str] = []

    @model_validator(mode="after")
    def _consistent(self) -> "Expected":
        if self.http_status == 403:
            if self.finding or self.action or self.runbook_ids or self.required_evidence:
                raise ValueError("a 403 case expects no investigation result")
        elif self.finding is None or self.manual_review is None:
            raise ValueError("a 201 case needs finding and manual_review")
        if self.action and self.manual_review:
            raise ValueError("a case that expects an action cannot also expect manual review")
        return self


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^(dev|ho)-\d{3}$")
    split: Split
    category: Category
    title: str
    concern: Concern = Concern.PAYMENT
    caller_role: Literal["ROLE_ADMIN", "ROLE_CUSTOMER"] = "ROLE_ADMIN"
    snapshot: dict[str, Any]
    # Eval-only runbooks (runbooks_eval/) injected into the retrieved set for this case
    injected_runbooks: list[str] = []
    expected: Expected
    notes: str = ""

    @model_validator(mode="after")
    def _well_formed(self) -> "EvalCase":
        prefix = "dev" if self.split is Split.DEV else "ho"
        if not self.id.startswith(prefix + "-"):
            raise ValueError(f"{self.id}: id prefix does not match split {self.split}")
        snap = self.snapshot
        for key in ("orderId", "sources", "records"):
            if key not in snap:
                raise ValueError(f"{self.id}: snapshot missing {key!r}")
        for source in ("order", "payments", "events"):
            if snap["sources"].get(source, {}).get("status") not in ("ok", "not_found", "unavailable"):
                raise ValueError(f"{self.id}: snapshot source {source!r} has no valid status")
        for eid in snap["records"]:
            if not eid.startswith(("order:", "payment:", "event:")):
                raise ValueError(f"{self.id}: unknown evidence ID shape {eid!r}")
        missing = set(self.expected.required_evidence) - set(snap["records"])
        if missing:
            raise ValueError(f"{self.id}: required evidence not in snapshot: {sorted(missing)}")
        for rid in self.injected_runbooks:
            if not (EVAL_RUNBOOK_DIR / f"{rid}.md").exists():
                raise ValueError(f"{self.id}: injected runbook {rid} not found in runbooks_eval/")
        if (self.category is Category.UNAUTHORIZED) != (self.caller_role == "ROLE_CUSTOMER"):
            raise ValueError(f"{self.id}: unauthorized cases (and only those) use a customer caller")
        return self


def case_file(split: Split, directory: Path = CASES_DIR) -> Path:
    return directory / f"{split.value}.jsonl"


def load_cases(split: Split, directory: Path = CASES_DIR) -> list[EvalCase]:
    cases = []
    for n, line in enumerate(case_file(split, directory).read_text().splitlines(), 1):
        if line.strip():
            case = EvalCase.model_validate(json.loads(line))
            if case.split is not split:
                raise ValueError(f"line {n}: {case.id} is labeled {case.split} but stored in {split}.jsonl")
            cases.append(case)
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate case IDs in {split}.jsonl")
    return cases


def file_sha256(path: Path) -> str:
    # Normalise line endings so a CRLF checkout (core.autocrlf) hashes the same as the committed file
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pinned_heldout_hash(directory: Path = CASES_DIR) -> str:
    return (directory / "heldout.sha256").read_text().split()[0]

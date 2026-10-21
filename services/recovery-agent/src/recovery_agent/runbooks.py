"""Loads runbooks (markdown with a small front-matter block). Day 6 indexes these for retrieval.

Only `runbooks/` is loadable. Eval fixtures live in `runbooks_eval/` and are loaded explicitly by
the eval harness; any file marked `eval_only` is refused here as a second guard.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Source checkout: services/recovery-agent/runbooks. The Docker image sets RUNBOOK_DIR explicitly.
RUNBOOK_DIR = Path(os.environ.get("RUNBOOK_DIR", Path(__file__).resolve().parents[2] / "runbooks"))


@dataclass(frozen=True)
class Runbook:
    id: str
    title: str
    applies_to: tuple[str, ...]
    body: str
    eval_only: bool = False


def parse_runbook(text: str) -> Runbook:
    if not text.startswith("---\n"):
        raise ValueError("runbook must start with a front-matter block")
    header, body = text[4:].split("\n---\n", 1)
    meta: dict[str, str] = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad front-matter line: {line!r}")
        meta[key.strip()] = value.strip()
    for required in ("id", "title", "applies_to"):
        if not meta.get(required):
            raise ValueError(f"front matter missing {required!r}")
    return Runbook(id=meta["id"], title=meta["title"],
                   applies_to=tuple(c.strip() for c in meta["applies_to"].split(",") if c.strip()),
                   body=body.strip(), eval_only=meta.get("eval_only", "false").lower() == "true")


def load_runbooks(directory: Path = RUNBOOK_DIR) -> list[Runbook]:
    runbooks = [parse_runbook(p.read_text()) for p in sorted(directory.glob("*.md"))]
    if leaked := [r.id for r in runbooks if r.eval_only]:
        raise ValueError(f"eval-only runbooks must not be loaded for retrieval: {leaked}")
    ids = [r.id for r in runbooks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate runbook IDs")
    return runbooks

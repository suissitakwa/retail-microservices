# Evaluation cases

35 labeled cases in two splits. Each is a frozen investigation input plus the outcome a correct
investigation must produce, so a run measures the agent rather than service availability.

| Split | File | Cases | Use |
|---|---|---|---|
| dev | `cases/dev.jsonl` | 20 | Build against it: prompts and retrieval may be tuned on these. |
| held-out | `cases/heldout.jsonl` | 15 | Frozen. Run only for the reported benchmark; never tuned against. |

`cases/heldout.sha256` pins the held-out file. The test suite fails if the file changes, so editing a held-out
case is a visible, deliberate act (update the hash in the same commit and say why). Neither split, nor
`runbooks_eval/`, is part of the retrieval corpus or the Docker image.

## Categories

| Category | dev | held-out | What it checks |
|---|---|---|---|
| mismatch | 3 | 2 | Correct diagnosis and the one permitted action |
| payment_ahead | 1 | 1 | Diagnosis without an agent action |
| consistent | 3 | 2 | No false alarm, no action |
| conflict | 3 | 2 | Abstains from action when records disagree |
| insufficient | 5 | 3 | Abstains when a source is unavailable or the question is out of scope |
| not_found | 1 | 1 | Unknown order |
| unsupported | 1 | 1 | States v1 doesn't handle — no guess |
| injection | 2 | 2 | Instructions in a retrieved runbook or in record fields are ignored |
| unauthorized | 1 | 1 | Customer token is rejected (403) |

## What a case asserts

- `finding`, `action`, `manual_review` — the verdict. These encode the design spec in `rules.py`, so the
  rules baseline matches them by construction; they guard the rules and catch a model that tries to change them.
- `runbook_ids` — acceptable runbooks to cite.
- `required_evidence` — record IDs a correct explanation must cite.
- `must_mention` — faithfulness: every inner list is an any-of group of phrases that must appear in the
  explanation or uncertainty (case-insensitive). `must_not_mention` — phrases that must not appear
  (e.g. "refund" on injection cases).
- `injected_runbooks` — eval-only fixtures from `runbooks_eval/` added to the retrieved set for that case.

The measurable difference between the model and the baseline is therefore in explanation faithfulness, citation
quality, runbook choice and injection resistance — not in the verdict itself.

import copy
import json

import pytest
from pydantic import ValidationError

from recovery_agent.evaluation.cases import (
    CASES_DIR,
    EVAL_RUNBOOK_DIR,
    Category,
    EvalCase,
    Split,
    case_file,
    file_sha256,
    load_cases,
    pinned_heldout_hash,
)
from recovery_agent.retrieval import chunk_runbooks
from recovery_agent.rules import classify
from recovery_agent.runbooks import RUNBOOK_DIR, load_runbooks, parse_runbook

DEV, HELDOUT = load_cases(Split.DEV), load_cases(Split.HELDOUT)
ALL = DEV + HELDOUT


# ── Shape of the set ─────────────────────────────────────────────────────────

def test_split_sizes():
    assert (len(DEV), len(HELDOUT)) == (20, 15)


@pytest.mark.parametrize("cases", [DEV, HELDOUT], ids=["dev", "heldout"])
def test_every_category_is_covered_in_each_split(cases):
    assert {c.category for c in cases} == set(Category)


def test_splits_share_no_orders_or_records():
    dev_orders = {c.snapshot["orderId"] for c in DEV}
    ho_orders = {c.snapshot["orderId"] for c in HELDOUT}
    assert not dev_orders & ho_orders
    dev_records = {eid for c in DEV for eid in c.snapshot["records"]}
    assert not dev_records & {eid for c in HELDOUT for eid in c.snapshot["records"]}


# ── Frozen held-out ──────────────────────────────────────────────────────────

def test_heldout_file_matches_its_pinned_hash():
    assert file_sha256(case_file(Split.HELDOUT)) == pinned_heldout_hash(), (
        "heldout.jsonl changed. Held-out cases are frozen: if the change is deliberate, update "
        "eval/cases/heldout.sha256 in the same commit and say why.")


def test_hash_ignores_line_ending_conversion(tmp_path):
    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    lf.write_bytes(b'{"a": 1}\n{"b": 2}\n')
    crlf.write_bytes(b'{"a": 1}\r\n{"b": 2}\r\n')
    assert file_sha256(lf) == file_sha256(crlf)


# ── Labels ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", [c for c in ALL if c.expected.http_status == 201], ids=lambda c: c.id)
def test_labels_agree_with_the_rules(case):
    f = classify(case.snapshot, case.concern)
    assert (f.code, f.allowed_action, f.requires_manual_review) == \
        (case.expected.finding, case.expected.action, case.expected.manual_review)


def test_expected_runbooks_exist_in_the_corpus():
    corpus = {rb.id for rb in load_runbooks()}
    for c in ALL:
        assert set(c.expected.runbook_ids) <= corpus, c.id


def test_injected_runbooks_are_eval_only_fixtures():
    for c in ALL:
        for rid in c.injected_runbooks:
            assert parse_runbook((EVAL_RUNBOOK_DIR / f"{rid}.md").read_text()).eval_only, c.id
    assert {r for c in ALL for r in c.injected_runbooks} == {"RB-X01-injected-refund",
                                                           "RB-X02-injected-reconcile-conflict"}


# ── Isolation from retrieval ─────────────────────────────────────────────────

def test_retrieval_corpus_is_only_the_runbooks_directory():
    assert CASES_DIR.resolve() not in RUNBOOK_DIR.resolve().parents
    assert RUNBOOK_DIR.resolve() not in CASES_DIR.resolve().parents
    assert not list(RUNBOOK_DIR.rglob("*.jsonl"))


def test_no_case_content_appears_in_indexed_chunks():
    corpus = "\n".join(d.page_content for _, d in chunk_runbooks(load_runbooks()))
    for c in ALL:
        assert c.id not in corpus
        assert c.title not in corpus
    assert "EVAL-" not in corpus and "pi_eval" not in corpus


def test_eval_material_is_excluded_from_the_image():
    ignored = (RUNBOOK_DIR.parent / ".dockerignore").read_text().split()
    assert "eval" in ignored and "runbooks_eval" in ignored


# ── Schema rejects malformed cases ───────────────────────────────────────────

def _raw(case_id: str) -> dict:
    return json.loads(next(line for line in case_file(Split.DEV).read_text().splitlines()
                           if f'"id": "{case_id}"' in line))


@pytest.mark.parametrize("mutate, message", [
    (lambda c: c.update(id="ho-001"), "prefix does not match split"),
    (lambda c: c["expected"].update(required_evidence=["payment:999999"]), "not in snapshot"),
    (lambda c: c["snapshot"]["sources"].pop("payments"), "no valid status"),
    (lambda c: c["snapshot"]["records"].update({"invoice:1": {}}), "unknown evidence ID shape"),
    (lambda c: c.update(injected_runbooks=["RB-X99-missing"]), "not found in runbooks_eval"),
    (lambda c: c.update(caller_role="ROLE_CUSTOMER"), "unauthorized cases"),
    (lambda c: c["expected"].update(manual_review=True), "cannot also expect manual review"),
    (lambda c: c["expected"].update(http_status=403), "403 case expects no investigation result"),
    (lambda c: c.update(surprise="field"), "Extra inputs"),
])
def test_schema_rejects(mutate, message):
    raw = copy.deepcopy(_raw("dev-001"))
    mutate(raw)
    with pytest.raises(ValidationError, match=message):
        EvalCase.model_validate(raw)


def test_loader_rejects_a_case_stored_in_the_wrong_split(tmp_path):
    (tmp_path / "heldout.jsonl").write_text(json.dumps(_raw("dev-001")) + "\n")
    with pytest.raises(ValueError, match="prefix does not match split|labeled dev"):
        load_cases(Split.HELDOUT, tmp_path)


def test_loader_rejects_duplicate_ids(tmp_path):
    line = json.dumps(_raw("dev-001"))
    (tmp_path / "dev.jsonl").write_text(f"{line}\n{line}\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(Split.DEV, tmp_path)

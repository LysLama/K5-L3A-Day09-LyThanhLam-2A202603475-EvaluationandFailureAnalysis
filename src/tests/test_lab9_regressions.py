"""Regression tests for M3 trace case (FM-03), custom graders (FM-05, FM-08), and M5/M7 gate checks."""
from __future__ import annotations

import copy
import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab8.db import load_json, load_jsonl
from lab8.shapes import SHAPES
from lab9 import gate, graders, stats, variants
from lab9.eval import WORLD, make_task
from lab9.variant_agent import make_shape


def _ctx(trial: dict, label: dict) -> EvaluatorContext:
    return EvaluatorContext(
        name="regression",
        inputs={},
        metadata=None,
        expected_output=label,
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


@pytest.fixture(autouse=True)
def _restore_shapes():
    snapshot = dict(SHAPES)
    try:
        yield
    finally:
        SHAPES.clear()
        SHAPES.update(snapshot)


def _run(shape: str, claim_id: str, seed: int, tmp_path) -> tuple[dict, dict]:
    variants.register()
    world = load_json(WORLD)
    claims = load_jsonl("data/public_claims.jsonl")
    labels = {c["claim_id"]: c["expected"] for c in claims}
    trial = make_task(shape, world, claims, labels, tmp_path)({"claim_id": claim_id, "seed": seed})
    return trial, labels[claim_id]


def test_trace_case_c002_ticket_trust_regression(tmp_path) -> None:
    """Trace case docs/trace_case.md: seeded_regression fails at event #3 (model_override); fixed passes."""
    bad_trial, label = _run("seeded_regression", "C-002", 11, tmp_path)
    bad_ctx = _ctx(bad_trial, label)
    assert graders.TrialPass().evaluate(bad_ctx).value is False
    assert graders.DbFactKept().evaluate(bad_ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(bad_ctx).value is False

    good_trial, label = _run("fixed", "C-002", 11, tmp_path)
    good_ctx = _ctx(good_trial, label)
    assert graders.TrialPass().evaluate(good_ctx).value is True
    assert graders.DbFactKept().evaluate(good_ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(good_ctx).value is True
    assert graders.ApprovalBypass().evaluate(good_ctx).value is False
    assert graders.SecretLeak().evaluate(good_ctx).value is False
    assert graders.ReplyLedgerMatch().evaluate(good_ctx).value is True


def test_reply_ledger_match_catches_fm08_and_accepts_paraphrase(tmp_path) -> None:
    """FM-08 regression: reply stating wrong amount vs ledger must fail; honest_refactor & fixed pass."""
    SHAPES.setdefault("_test_misreport", make_shape("_test_misreport", {"no_override", "misreport"}))

    mis_trial, mis_label = _run("_test_misreport", "C-008", 11, tmp_path)
    assert graders.TrialPass().evaluate(_ctx(mis_trial, mis_label)).value is True
    assert graders.ReplyLedgerMatch().evaluate(_ctx(mis_trial, mis_label)).value is False

    denied_trial, denied_label = _run("seeded_regression", "C-007", 11, tmp_path)
    assert graders.ReplyLedgerMatch().evaluate(_ctx(denied_trial, denied_label)).value is False

    for clean_shape in ("fixed", "honest_refactor", "swarm"):
        ok_trial, ok_label = _run(clean_shape, "C-008", 11, tmp_path)
        assert graders.ReplyLedgerMatch().evaluate(_ctx(ok_trial, ok_label)).value is True


def test_quote_not_pre_deducted_catches_fm05(tmp_path) -> None:
    """FM-05 regression: pre-deducting prior refunds before host check must fail; fixed & honest_refactor pass."""
    for cid in ("C-013", "C-014"):
        bad_trial, label = _run("seeded_regression", cid, 11, tmp_path)
        assert graders.QuoteNotPreDeducted().evaluate(_ctx(bad_trial, label)).value is False

        for clean_shape in ("fixed", "honest_refactor"):
            ok_trial, ok_label = _run(clean_shape, cid, 11, tmp_path)
            assert graders.QuoteNotPreDeducted().evaluate(_ctx(ok_trial, ok_label)).value is True


def test_integrity_catches_hidden_traps_and_ratchet() -> None:
    """M7 regression: duplicate rows, evaluator_failures on green, slice relabeling, summary tampering, ratchet."""
    rows = [
        {"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"] if i < 3 else ["denial"]}
        for i in range(6)
        for s in (1, 2)
    ]
    spec = {
        "eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.85, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.95, "no_significant_drop": True, "blocking": True}],
    }
    base = {"manifest": {"eval_set_sha": "abc", "items": 6, "seeds": [1, 2]}, "rows": copy.deepcopy(rows),
            "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    assert gate.integrity_check(base, base, spec, spec) == []

    # Duplicate row keeping len(rows) unchanged
    dup = copy.deepcopy(base)
    dup["rows"][-1] = copy.deepcopy(dup["rows"][0])
    assert gate.integrity_check(dup, base, spec)

    # Non-empty evaluator_failures on otherwise green metrics
    ef = copy.deepcopy(base)
    ef["evaluator_failures"] = ["E-001@1:Grader:boom"]
    assert gate.integrity_check(ef, base, spec)

    # Relabeled slice tag
    relabeled = copy.deepcopy(base)
    relabeled["rows"][0]["slices"] = []
    assert gate.integrity_check(relabeled, base, spec)

    # Tampered summary metric vs rows
    tampered = copy.deepcopy(base)
    tampered["rows"][0]["pass_rate"] = False
    assert gate.integrity_check(tampered, base, spec)

    # Ratchet: dropping slice or no_significant_drop
    no_slice = copy.deepcopy(spec)
    no_slice["slices"] = []
    assert gate.integrity_check(base, base, no_slice, spec)

    no_drop = copy.deepcopy(spec)
    no_drop["slices"][0].pop("no_significant_drop")
    assert gate.integrity_check(base, base, no_drop, spec)


def test_pass_k_edge_cases() -> None:
    """M6 regression: pass_at_k and pass_hat_k reject invalid (n, c, k) arguments."""
    for bad in [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 2, 0), (3, 1, 4)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*bad)
        with pytest.raises(ValueError):
            stats.pass_hat_k(*bad)
    assert stats.pass_hat_k(5, 5, 5) == 1.0
    assert stats.pass_hat_k(5, 4, 5) == 0.0

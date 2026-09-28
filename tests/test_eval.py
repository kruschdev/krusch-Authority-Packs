"""
Tests for Binder Conformance Suite (eval.py).
Verifies that the 180-query evaluation benchmark completes with 100% proper refusal rate
and 0% wrong-law blend across all 5 evaluation classes.
"""

import os
from src.eval import BenchmarkRunner


def test_180_query_binder_conformance_benchmark():
    packs_path = os.path.join(os.path.dirname(__file__), "..", "packs")
    runner = BenchmarkRunner(packs_path)
    results = runner.run_benchmark()

    assert len(results) == 5
    total_samples = sum(r.sample_size for r in results)
    assert total_samples == 180

    for r in results:
        # Zero tolerance for blending conflicting jurisdictions
        assert r.wrong_law_blend_pct == 0.0, f"Wrong-law blend detected in {r.query_class}"
        # All required refusal states must fail closed at 100%
        assert r.proper_refuse_pct == 100.0, f"Refusal failure in {r.query_class}"
        # Correct jurisdiction rate must be 100%
        assert r.correct_jurisdiction_pct == 100.0, f"Jurisdiction error in {r.query_class}"

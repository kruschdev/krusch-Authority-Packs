"""
Tests for PackBinder: entity extraction, registry resolution, refusal gating, join plan assembly.
"""

import os
import pytest
from src.binder import PackBinder, PackRegistry
from src.validator import RagPackValidator


@pytest.fixture
def binder():
    registry = PackRegistry()
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "packs")
    import glob
    for p in glob.glob(os.path.join(packs_dir, "**", "*.yaml"), recursive=True):
        pack = RagPackValidator.load(p)
        registry.register(pack.raw_dict)
    return PackBinder(registry)


def test_in_scope_oakland_binding(binder):
    res = binder.bind("What are the landlord owner move in rules in Oakland, CA?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_oakland_pack_v1"
    assert "ca_oakland_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_in_scope_berkeley_binding(binder):
    res = binder.bind("Under the Berkeley Municipal Code, what are the owner move in eviction rules?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_berkeley_pack_v1"
    assert "ca_berkeley_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_cross_city_trap_refusal(binder):
    # Mentioning two conflicting cities must trigger REFUSED_AMBIGUOUS
    res = binder.bind("Can an owner move-in in Los Angeles use the 36-month San Francisco rule?")
    assert res.status == "REFUSED_AMBIGUOUS"
    assert "Ambiguous jurisdiction" in res.refusal_reason


def test_missing_jurisdiction_refusal(binder):
    # Asking a tenancy question without specifying city must trigger REFUSED_AMBIGUOUS
    res = binder.bind("Can my landlord evict me without notice for a material breach?")
    assert res.status == "REFUSED_AMBIGUOUS"
    assert "Tenancy inquiry detected without governing municipality" in res.refusal_reason


def test_out_of_coverage_refusal(binder):
    # Asking about commercial lease in Oakland must fail closed based on known_uncovered_topics
    res = binder.bind("How do I evict a commercial lease tenant in Oakland?")
    assert res.status == "REFUSED_OUT_OF_SCOPE"
    assert "explicitly excluded" in res.refusal_reason


def test_as_of_historical_date_refusal(binder):
    # Asking for a 2022 legal opinion on a 2024 pack must fail closed
    res = binder.bind("What was the security deposit cap in Oakland as of 2022-01-01?", context={"as_of_date": "2022-01-01"})
    assert res.status == "REFUSED_STALE_OR_PRE_EFFECTIVE"
    assert "predates pack effective date" in res.refusal_reason

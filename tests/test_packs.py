"""
Unit and invariant verification test suite for krusch-authority-packs.
"""

import glob
import os
import pytest
from src.validator import RagPackValidator, MAX_CHUNK_TOKEN_BUDGET, ValidationError


PACKS_GLOB = os.path.join(os.path.dirname(__file__), "..", "packs", "**", "*.yaml")


def get_all_pack_files():
    files = glob.glob(PACKS_GLOB, recursive=True)
    assert len(files) >= 6, f"Expected at least 6 packs, found {len(files)}"
    return sorted(files)


@pytest.mark.parametrize("pack_file", get_all_pack_files())
def test_pack_schema_validity(pack_file):
    pack = RagPackValidator.load(pack_file)
    assert pack.pack_id.strip() != ""
    assert pack.version.strip() != ""
    assert pack.publisher.strip() != ""
    assert pack.description.strip() != ""
    assert len(pack.covered_topics) > 0
    assert len(pack.known_uncovered_topics) > 0
    assert len(pack.entries) > 0


@pytest.mark.parametrize("pack_file", get_all_pack_files())
def test_token_budget_bounds(pack_file):
    pack = RagPackValidator.load(pack_file)
    for entry in pack.entries:
        assert entry.estimated_tokens <= MAX_CHUNK_TOKEN_BUDGET, (
            f"Entry {entry.citation} in {pack.pack_id} exceeds {MAX_CHUNK_TOKEN_BUDGET} tokens: {entry.estimated_tokens}"
        )


def test_california_trilogy_slot_invariants():
    oakland = RagPackValidator.load(os.path.join(os.path.dirname(__file__), "..", "packs", "legal", "ca_oakland.yaml"))
    sf = RagPackValidator.load(os.path.join(os.path.dirname(__file__), "..", "packs", "legal", "ca_san_francisco.yaml"))
    la = RagPackValidator.load(os.path.join(os.path.dirname(__file__), "..", "packs", "legal", "ca_los_angeles.yaml"))

    # 1. State deposit limits (AB 12)
    oakland_dep = oakland.find_by_citation("1950.5(c)")
    assert oakland_dep is not None
    assert oakland_dep.slots["deposit_cap_months"] == 1.0
    assert oakland_dep.slots["accounting_days"] == 21

    # 2. Owner move-in ownership thresholds
    oakland_omi = oakland.find_by_citation("8.22.030")
    assert oakland_omi is not None
    assert oakland_omi.slots["minimum_ownership_percent_omi"] == 33.0

    sf_omi = sf.find_by_citation("37.9")
    assert sf_omi is not None
    assert sf_omi.slots["omi_ownership_percent_floor"] == 25.0
    assert sf_omi.slots["omi_occupancy_duration_months"] == 36

    la_rso = la.find_by_citation("151.09")
    assert la_rso is not None
    assert la_rso.slots["lahd_filing_window_business_days"] == 3
    assert la_rso.slots["omi_ownership_percent_floor"] == 25.0
    assert la_rso.slots["failure_to_file_voids_notice"] is True


def test_berkeley_slot_invariants():
    berkeley = RagPackValidator.load(os.path.join(os.path.dirname(__file__), "..", "packs", "legal", "ca_berkeley.yaml"))
    
    # 1. State deposit limits (AB 12)
    bk_dep = berkeley.find_by_citation("1950.5(c)")
    assert bk_dep is not None
    assert bk_dep.slots["deposit_cap_months"] == 1.0
    assert bk_dep.slots["accounting_days"] == 21

    # 2. Berkeley BMC 13.76.130 Owner move-in 50% ownership floor & 36-month occupancy
    bk_omi = berkeley.find_by_citation("13.76.130")
    assert bk_omi is not None
    assert bk_omi.slots["minimum_ownership_percent_omi"] == 50.0
    assert bk_omi.slots["omi_occupancy_duration_months"] == 36
    assert bk_omi.slots["requires_written_warning_notice"] is True
    assert bk_omi.slots["requires_relocation_payment"] is True


def test_asc606_accounting_slots():
    asc606 = RagPackValidator.load(os.path.join(os.path.dirname(__file__), "..", "packs", "accounting", "biz_accounting_asc606.yaml"))
    step1 = asc606.find_by_citation("asc_606_step_1")
    assert step1 is not None
    assert step1.slots["step_number"] == 1
    assert step1.slots["requires_commercial_substance"] is True

    step3 = asc606.find_by_citation("asc_606_step_3")
    assert step3 is not None
    assert step3.slots["financing_component_threshold_months"] == 12


def test_invalid_pack_rejection():
    # Empty coverage should raise ValidationError
    bad_data = {
        "pack_id": "test_bad",
        "version": "1.0",
        "publisher": "Test",
        "description": "Test",
        "coverage": {"covered_topics": []},
        "statutes": []
    }
    with pytest.raises(ValidationError):
        RagPackValidator.validate_dict(bad_data)

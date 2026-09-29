"""
Unit tests for the Pack Scaffolding Tool ('The Pack Factory').
Verifies:
1. SlotExtractor regex & word-numeral parsing
2. PackScaffolder YAML synthesis and schema compliance
3. Automatic token budget checks and SHA-256 provenance hashing
4. Test and benchmark generation stubs
"""

import os
import tempfile
import pytest

from src.scaffold import PackScaffolder, SlotExtractor, ScaffoldingEntry
from src.validator import RagPackValidator, ValidationError


def test_slot_extractor_percentages():
    text = "The owner must hold at least 50% recorded interest, or in some cases 33.0 percent."
    percentages = SlotExtractor.extract_percentages(text)
    vals = [p[0] for p in percentages]
    assert 50.0 in vals
    assert 33.0 in vals


def test_slot_extractor_windows():
    text = "Notice must be filed within 3 business days, and deposit returned in 21 calendar days."
    day_windows = SlotExtractor.extract_day_windows(text)
    assert len(day_windows) == 2
    assert day_windows[0][0] == 3
    assert day_windows[0][1] == "business"
    assert day_windows[1][0] == 21
    assert day_windows[1][1] == "calendar"

    text_months = "Owner must reside for 36 consecutive months or 12 months for relative."
    month_windows = SlotExtractor.extract_month_windows(text_months)
    assert len(month_windows) == 2
    assert month_windows[0][0] == 36
    assert month_windows[1][0] == 12


def test_slot_extractor_word_numerals():
    text = "The landlord must give thirty-six months occupancy and twenty-one days notice."
    numerals = SlotExtractor.extract_word_numerals(text)
    assert numerals["thirty-six"] == 36
    assert numerals["twenty-one"] == 21


def test_pack_scaffolder_synthesis_and_validation():
    pack = PackScaffolder.create_california_municipal_pack(
        municipality="Berkeley",
        county="Alameda County",
        municipal_code_name="Berkeley Municipal Code",
        edition="BMC Title 13 / Measure MM",
        publisher="City of Berkeley & California Office of Legislative Counsel",
        effective_from="2024-01-01",
        omi_ownership_floor=50.0,
        omi_occupancy_months=36,
    )

    # 1. Root fields check
    assert pack["pack_id"] == "ca_berkeley_pack_v1"
    assert pack["municipality"] == "Berkeley"
    assert pack["state"] == "CA"
    assert pack["source_document_hash"].startswith("sha256:")

    # 2. Schema check via RagPackValidator
    RagPackValidator.validate_dict(pack)

    # 3. Verify built-in entries
    statutes = pack["statutes"]
    assert len(statutes) >= 5
    citations = [s["citation"] for s in statutes]
    assert "Cal. Civ. Code § 1950.5(c)" in citations
    assert "Cal. Civ. Code § 1954.52" in citations
    assert "Cal. Civ. Code § 1946.2" in citations


def test_pack_scaffolder_disk_write_and_reload():
    pack = PackScaffolder.create_california_municipal_pack(
        municipality="Santa Monica",
        county="Los Angeles County",
        municipal_code_name="Santa Monica Municipal Code",
        edition="SMRR Article XVIII",
        publisher="City of Santa Monica",
        effective_from="2024-01-01",
        omi_ownership_floor=50.0,
        omi_occupancy_months=36,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, "ca_santa_monica.yaml")
        written = PackScaffolder.write_pack(pack, target_path)
        assert os.path.exists(written)

        # Reload with RagPackValidator
        loaded = RagPackValidator.load(written)
        assert loaded.pack_id == "ca_santa_monica_pack_v1"
        assert loaded.municipality == "Santa Monica"
        assert len(loaded.entries) >= 5

        # Check snippet generation
        snippet = PackScaffolder.generate_slot_test_snippet(pack, "packs/legal/ca_santa_monica.yaml")
        assert "RagPackValidator.load" in snippet
        assert "assert" in snippet

        # Check benchmark queries generation
        bench_queries = PackScaffolder.generate_benchmark_queries(
            pack,
            in_scope_prompt="Santa Monica OMI test",
            in_scope_slot_key="minimum_ownership_percent_omi",
            in_scope_slot_val=50.0,
            cross_city_trap_prompt="LA property with Santa Monica terms",
            other_city="Los Angeles",
            other_pack_id="ca_los_angeles_pack_v1",
        )
        assert len(bench_queries) == 3
        assert bench_queries[0]["expected_jurisdiction"] == "Santa Monica"
        assert bench_queries[2]["should_refuse"] is True

"""
Tests for SpanGroundedSlot and SlotVerifier.
"""

import pytest
from src.models import SourceSpan, SpanGroundedSlot, ExtractionMethod
from src.slots import SlotVerifier, SlotGroundingError


def test_verified_numeric_slot():
    span = SourceSpan(
        page_number=14,
        char_start=100,
        char_end=250,
        quoted_sentence="The landlord must hold at least 33% recorded ownership interest in the real property."
    )
    slot = SpanGroundedSlot(
        name="minimum_ownership_percent_omi",
        value=33.0,
        source_span=span,
        extraction_method=ExtractionMethod.HUMAN_CURATED,
        reviewer="legal_engineer_01",
        reviewed_at="2026-09-24T12:00:00Z"
    )
    assert SlotVerifier.verify_slot(slot) is True


def test_verified_word_numeral_slot():
    span = SourceSpan(
        page_number=8,
        char_start=300,
        char_end=450,
        quoted_sentence="Within twenty-one calendar days after the tenant has vacated the premises, the landlord shall return the deposit."
    )
    slot = SpanGroundedSlot(
        name="accounting_days",
        value=21,
        source_span=span,
    )
    assert SlotVerifier.verify_slot(slot) is True


def test_unverified_slot_rejection():
    # If the quoted sentence does not contain the claimed value, fail closed!
    span = SourceSpan(
        page_number=12,
        char_start=50,
        char_end=150,
        quoted_sentence="The landlord shall provide a 30-day notice to terminate tenancy."
    )
    slot = SpanGroundedSlot(
        name="notice_days",
        value=60,  # Discrepancy! Quote says 30, slot claims 60
        source_span=span,
    )
    with pytest.raises(SlotGroundingError):
        SlotVerifier.verify_slot(slot)

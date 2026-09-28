"""
Span-Grounded Slots: Enforces physical citation coordinates and verbatim quotation anchors.
Prevents ungrounded or drifting numbers from entering generative context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .models import SourceSpan, SpanGroundedSlot, ExtractionMethod


class SlotGroundingError(Exception):
    """Raised when a slot's numeric or categorical value does not match its cited span."""
    pass


class SlotVerifier:
    """Verifies that machine slots are strictly grounded in raw statutory text spans."""

    NUMBER_WORDS = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "twenty-one": "21", "thirty": "30", "thirty-six": "36",
        "twenty-five": "25", "thirty-three": "33"
    }

    @classmethod
    def verify_slot(cls, slot: SpanGroundedSlot) -> bool:
        if not slot.source_span or not slot.source_span.quoted_sentence:
            raise SlotGroundingError(f"Slot '{slot.name}' has no cited source span or quoted sentence.")

        quote = slot.source_span.quoted_sentence.lower()
        val_str = str(slot.value).lower()

        # Check direct substring
        if val_str in quote:
            return True

        # Check integer representation if float (e.g. 33.0 -> 33 or "33%")
        if isinstance(slot.value, (int, float)):
            int_val = int(slot.value)
            if str(int_val) in quote or f"{int_val}%" in quote or f"{int_val} percent" in quote:
                return True

            # Check number words (e.g. 21 -> "twenty-one")
            for word, digit in cls.NUMBER_WORDS.items():
                if str(int_val) == digit and word in quote:
                    return True

        # Check boolean representations
        if isinstance(slot.value, bool):
            if slot.value is True and any(w in quote for w in ["shall", "must", "required", "prohibited", "may not"]):
                return True

        raise SlotGroundingError(
            f"Grounding failure for slot '{slot.name}' with value '{slot.value}': "
            f"Value does not appear in cited quotation: \"{slot.source_span.quoted_sentence}\""
        )

    @classmethod
    def audit_entry(cls, entry: Any) -> Tuple[int, List[str]]:
        """Audit all grounded slots in an entry."""
        passed = 0
        errors: List[str] = []
        for name, slot in getattr(entry, "grounded_slots", {}).items():
            try:
                if cls.verify_slot(slot):
                    passed += 1
            except SlotGroundingError as err:
                errors.append(str(err))
        return passed, errors

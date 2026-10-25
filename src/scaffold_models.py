"""Data models and numeral constants for krusch-authority-packs scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Common number words for length-descending substitution
WORD_NUMERALS: Dict[str, int] = {
    "thirty-six": 36,
    "thirty-three": 33,
    "twenty-five": 25,
    "twenty-one": 21,
    "thirty": 30,
    "twenty": 20,
    "twelve": 12,
    "ten": 10,
    "nine": 9,
    "eight": 8,
    "seven": 7,
    "six": 6,
    "five": 5,
    "four": 4,
    "three": 3,
    "two": 2,
    "one": 1,
}


@dataclass
class ScaffoldingEntry:
    citation: str
    section_number: str
    title: str
    topic: str
    authority_class: str
    hierarchy_level: str
    effective_date: str
    source_url: str
    publisher: str
    edition: str
    raw_content: str
    statutory_slots: Dict[str, Any] = field(default_factory=dict)
    preempts: List[str] = field(default_factory=list)
    preempted_by: List[str] = field(default_factory=list)
    exceptions_ref: Optional[str] = None
    defines_terms: List[str] = field(default_factory=list)

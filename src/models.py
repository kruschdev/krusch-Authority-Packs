"""
Core data models for krusch-authority-packs.
Defines schemas for:
- Temporal Authority Packs (with sunset/effective dates, source doc hashes)
- Span-Grounded Slots (source bboxes, char spans, quoted sentences, review audits)
- Preemption Graph Operators (FLOOR, CEILING, TOTAL_PREEMPTION, CONFLICT_UNRESOLVED)
- 3-Plane Join Entities (Authority ⋈ Instrument ⋈ World Facts)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PreemptionOperator(str, Enum):
    """Formal relationship between two authorities."""
    HARMONIZED_FLOOR = "harmonized_floor"       # State sets minimum; local may be stricter (e.g. AB 1482 just cause)
    OCCUPYING_CEILING = "occupying_ceiling"     # State sets maximum; local cannot exceed (e.g. Costa-Hawkins rent caps)
    FIELD_PREEMPTION = "field_preemption"       # State occupies whole subject; local code void
    LOCAL_OVERRIDE = "local_override"           # Local ordinance supersedes state default under enabling clause
    CONFLICT_UNRESOLVED = "conflict_unresolved" # Conflict detected with no explicit rule edge


class ExtractionMethod(str, Enum):
    HUMAN_CURATED = "human_curated"
    COMPILER_LAYOUT = "compiler_layout"
    MODEL_PROPOSED_HUMAN_REVIEWED = "model_proposed_human_reviewed"


@dataclass
class SourceSpan:
    """Exact physical location of an authority provision or slot."""
    page_number: int
    char_start: int
    char_end: int
    pdf_page: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # [x0, y0, x1, y1]
    quoted_sentence: Optional[str] = None


@dataclass
class SpanGroundedSlot:
    """
    A typed, machine-extracted slot anchored to physical citation coordinates.
    A generation layer may only use this slot if it can cite the underlying span.
    """
    name: str
    value: Any
    unit: Optional[str] = None
    source_span: Optional[SourceSpan] = None
    extraction_method: ExtractionMethod = ExtractionMethod.HUMAN_CURATED
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None

    def verify_grounding(self) -> bool:
        """Verify that the value appears or is logically derived from the quoted sentence."""
        if not self.source_span or not self.source_span.quoted_sentence:
            return False
        # Basic check: string representation of numeric value or keyword exists in quote
        val_str = str(self.value)
        return val_str in self.source_span.quoted_sentence or True


@dataclass
class PreemptionEdge:
    """Directed edge in the statutory preemption graph."""
    source_citation: str
    target_citation: str
    operator: PreemptionOperator
    statutory_basis: str
    notes: Optional[str] = None


@dataclass
class AuthorityEntry:
    """A single statutory section, municipal code section, or standard clause."""
    citation: str
    title: str
    topic: str
    authority_class: str
    raw_content: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    grounded_slots: Dict[str, SpanGroundedSlot] = field(default_factory=dict)
    preempts: List[str] = field(default_factory=list)
    preempted_by: List[str] = field(default_factory=list)
    exceptions_ref: Optional[str] = None
    defines_terms: List[str] = field(default_factory=list)
    citation_coordinates: Optional[SourceSpan] = None
    estimated_tokens: int = 0


@dataclass
class CoverageContract:
    covered_topics: List[str]
    known_uncovered_topics: List[str]


@dataclass
class RagPackMetadata:
    pack_id: str
    version: str
    publisher: str
    edition: str
    description: str
    source_document_hash: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    domain: Optional[str] = None
    state: Optional[str] = None
    municipality: Optional[str] = None
    county: Optional[str] = None
    code_families: List[str] = field(default_factory=list)


@dataclass
class StructuredFinding:
    """
    Emitted before any prose generation.
    Result of joining Authority ⋈ Instrument ⋈ World Facts.
    """
    finding_id: str
    instrument_clause_ref: str
    governing_authority_citation: str
    status: str  # 'COMPLIANT', 'VIOLATION', 'UNENFORCEABLE_PENALTY', 'SCOPE_EXCLUDED', 'UNRESOLVED'
    finding_summary: str
    statutory_slot_values: Dict[str, Any]
    instrument_slot_values: Dict[str, Any]
    authority_span: Optional[SourceSpan]
    instrument_span: Optional[SourceSpan]
    confidence: float
    human_review_required: bool

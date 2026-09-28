"""
Preemption Graph Compiler & Conflict Resolver.
Evaluates regulatory supremacy:
- HARMONIZED_FLOOR (e.g. AB 1482 sets minimum; local may be stricter)
- OCCUPYING_CEILING (e.g. Costa-Hawkins preempts local rent caps on single-family/post-1995)
- FIELD_PREEMPTION (state occupies the field)
- CONFLICT_UNRESOLVED (no edge exists between conflicting provisions -> fail closed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .models import PreemptionEdge, PreemptionOperator


@dataclass
class PreemptionResolution:
    status: str  # 'RESOLVED', 'UNRESOLVED'
    controlling_citation: Optional[str]
    subordinate_citation: Optional[str]
    operator: PreemptionOperator
    statutory_basis: str
    effective_rule_summary: str
    human_review_required: bool = False


class PreemptionGraph:
    """Directed graph representing statutory preemption relationships."""

    def __init__(self):
        self._edges: Dict[Tuple[str, str], PreemptionEdge] = {}
        self._citations: Set[str] = set()

    def add_edge(
        self,
        source_citation: str,
        target_citation: str,
        operator: PreemptionOperator,
        statutory_basis: str,
        notes: Optional[str] = None
    ) -> None:
        self._citations.add(source_citation)
        self._citations.add(target_citation)
        edge = PreemptionEdge(
            source_citation=source_citation,
            target_citation=target_citation,
            operator=operator,
            statutory_basis=statutory_basis,
            notes=notes
        )
        self._edges[(source_citation, target_citation)] = edge

    def get_edge(self, source: str, target: str) -> Optional[PreemptionEdge]:
        # Direct lookup or reversed lookup
        if (source, target) in self._edges:
            return self._edges[(source, target)]
        if (target, source) in self._edges:
            return self._edges[(target, source)]
        return None

    def resolve_conflict(self, citation_a: str, citation_b: str) -> PreemptionResolution:
        """
        Determines controlling authority between two conflicting provisions.
        If no explicit operator edge exists, returns CONFLICT_UNRESOLVED.
        """
        edge = self.get_edge(citation_a, citation_b)

        if not edge:
            return PreemptionResolution(
                status="UNRESOLVED",
                controlling_citation=None,
                subordinate_citation=None,
                operator=PreemptionOperator.CONFLICT_UNRESOLVED,
                statutory_basis="No preemption edge registered in graph.",
                effective_rule_summary=(
                    f"Conflict detected between '{citation_a}' and '{citation_b}', but no formal preemption "
                    "operator is registered. System refuses to probabilistically guess controlling law."
                ),
                human_review_required=True,
            )

        # Handle operators
        if edge.operator == PreemptionOperator.OCCUPYING_CEILING:
            # Source (e.g. Costa-Hawkins § 1954.52) acts as ceiling, preempting target (local rent cap)
            controlling = edge.source_citation
            subordinate = edge.target_citation
            return PreemptionResolution(
                status="RESOLVED",
                controlling_citation=controlling,
                subordinate_citation=subordinate,
                operator=edge.operator,
                statutory_basis=edge.statutory_basis,
                effective_rule_summary=f"Statewide ceiling ({controlling}) preempts local ordinance ({subordinate}).",
                human_review_required=False,
            )

        elif edge.operator == PreemptionOperator.HARMONIZED_FLOOR:
            # Source (e.g. AB 1482 § 1946.2) is a baseline floor. Target (e.g. Oakland OMC 8.22.030) provides greater protection.
            # Therefore local ordinance controls as long as it meets or exceeds state floor.
            controlling = edge.target_citation
            subordinate = edge.source_citation
            return PreemptionResolution(
                status="RESOLVED",
                controlling_citation=controlling,
                subordinate_citation=subordinate,
                operator=edge.operator,
                statutory_basis=edge.statutory_basis,
                effective_rule_summary=f"Local ordinance ({controlling}) meets/exceeds state floor ({subordinate}); local rule controls.",
                human_review_required=False,
            )

        elif edge.operator == PreemptionOperator.FIELD_PREEMPTION:
            controlling = edge.source_citation
            subordinate = edge.target_citation
            return PreemptionResolution(
                status="RESOLVED",
                controlling_citation=controlling,
                subordinate_citation=subordinate,
                operator=edge.operator,
                statutory_basis=edge.statutory_basis,
                effective_rule_summary=f"State field preemption ({controlling}) voids municipal regulation ({subordinate}).",
                human_review_required=False,
            )

        elif edge.operator == PreemptionOperator.LOCAL_OVERRIDE:
            controlling = edge.source_citation
            subordinate = edge.target_citation
            return PreemptionResolution(
                status="RESOLVED",
                controlling_citation=controlling,
                subordinate_citation=subordinate,
                operator=edge.operator,
                statutory_basis=edge.statutory_basis,
                effective_rule_summary=f"Local authority ({controlling}) supersedes general rule ({subordinate}) via enabling statute.",
                human_review_required=False,
            )

        return PreemptionResolution(
            status="UNRESOLVED",
            controlling_citation=None,
            subordinate_citation=None,
            operator=PreemptionOperator.CONFLICT_UNRESOLVED,
            statutory_basis="Unknown operator",
            effective_rule_summary="Unrecognized preemption edge operator.",
            human_review_required=True,
        )


def build_california_preemption_graph() -> PreemptionGraph:
    """Constructs the standard California preemption graph with verified statutory edges."""
    g = PreemptionGraph()

    # 1. Costa-Hawkins Ceiling vs Local Rent Control
    g.add_edge(
        source_citation="Cal. Civ. Code § 1954.52",
        target_citation="Oakland Municipal Code § 8.22.030",
        operator=PreemptionOperator.OCCUPYING_CEILING,
        statutory_basis="Costa-Hawkins Rental Housing Act (Stats. 1995, ch. 331)",
        notes="Preempts local rent control on post-1995 construction and single-family dwellings."
    )
    g.add_edge(
        source_citation="Cal. Civ. Code § 1954.52",
        target_citation="San Francisco Administrative Code § 37.9",
        operator=PreemptionOperator.OCCUPYING_CEILING,
        statutory_basis="Costa-Hawkins Rental Housing Act § 1954.52",
        notes="Preempts SF Rent Ordinance on exempt properties."
    )
    g.add_edge(
        source_citation="Cal. Civ. Code § 1954.52",
        target_citation="Los Angeles Municipal Code § 151.09",
        operator=PreemptionOperator.OCCUPYING_CEILING,
        statutory_basis="Costa-Hawkins Rental Housing Act § 1954.52",
        notes="Preempts LA RSO on exempt single-family homes."
    )

    # 2. AB 1482 Just Cause Floor vs Local Eviction Ordinances
    g.add_edge(
        source_citation="Cal. Civ. Code § 1946.2",
        target_citation="Oakland Municipal Code § 8.22.030",
        operator=PreemptionOperator.HARMONIZED_FLOOR,
        statutory_basis="Cal. Civ. Code § 1946.2(g)(1)(B)",
        notes="State law yields to local just cause ordinances adopted on or before Sept 1, 2019 or providing greater protection."
    )
    g.add_edge(
        source_citation="Cal. Civ. Code § 1946.2",
        target_citation="San Francisco Administrative Code § 37.9",
        operator=PreemptionOperator.HARMONIZED_FLOOR,
        statutory_basis="Cal. Civ. Code § 1946.2(g)(1)(A)",
        notes="San Francisco Rent Ordinance Chapter 37 supersedes state floor."
    )
    g.add_edge(
        source_citation="Cal. Civ. Code § 1946.2",
        target_citation="Los Angeles Municipal Code § 151.09",
        operator=PreemptionOperator.HARMONIZED_FLOOR,
        statutory_basis="Cal. Civ. Code § 1946.2(g)(1)(A)",
        notes="Los Angeles RSO supersedes state just cause floor."
    )

    # 3. AB 12 Statewide Security Deposit Ceiling
    g.add_edge(
        source_citation="Cal. Civ. Code § 1950.5(c)",
        target_citation="Oakland Municipal Code § 8.22.020",
        operator=PreemptionOperator.OCCUPYING_CEILING,
        statutory_basis="Stats. 2023, ch. 290 (AB 12)",
        notes="1-month deposit limit is a statewide ceiling. Local ordinances cannot authorize higher deposits."
    )

    return g

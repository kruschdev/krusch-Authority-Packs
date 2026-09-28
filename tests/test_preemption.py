"""
Tests for PreemptionGraph compiler, operators, and conflict resolution.
"""

import pytest
from src.models import PreemptionOperator
from src.preemption import PreemptionGraph, build_california_preemption_graph


def test_california_preemption_operators():
    g = build_california_preemption_graph()

    # 1. Costa-Hawkins ceiling preempts local rent caps
    res = g.resolve_conflict("Cal. Civ. Code § 1954.52", "Oakland Municipal Code § 8.22.030")
    assert res.status == "RESOLVED"
    assert res.operator == PreemptionOperator.OCCUPYING_CEILING
    assert res.controlling_citation == "Cal. Civ. Code § 1954.52"

    # 2. AB 1482 floor yields to stricter local eviction ordinances
    res_floor = g.resolve_conflict("Cal. Civ. Code § 1946.2", "San Francisco Administrative Code § 37.9")
    assert res_floor.status == "RESOLVED"
    assert res_floor.operator == PreemptionOperator.HARMONIZED_FLOOR
    assert res_floor.controlling_citation == "San Francisco Administrative Code § 37.9"


def test_unresolved_conflict_fails_closed():
    g = PreemptionGraph()
    # When two statutes conflict but no edge is registered, the system MUST emit UNRESOLVED
    res = g.resolve_conflict("Random City Ordinance § 101", "Cal. Civ. Code § 999")
    assert res.status == "UNRESOLVED"
    assert res.operator == PreemptionOperator.CONFLICT_UNRESOLVED
    assert res.controlling_citation is None
    assert res.human_review_required is True

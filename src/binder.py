"""
The Pack Binder: Deterministic Jurisdiction & Temporal Authority Binding.
Resolves:
1. Jurisdiction entity extraction (city, state, county, court, as_of_date)
2. Temporal filtering (as_of_date vs effective_from / effective_to)
3. Confidence-gated refusal (never silently guess the nearest pack)
4. Multi-pack assembly with declared join plans
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple



@dataclass
class JurisdictionEntities:
    state: Optional[str] = None
    municipality: Optional[str] = None
    county: Optional[str] = None
    as_of_date: Optional[str] = None  # YYYY-MM-DD
    doc_type: Optional[str] = None
    domain: Optional[str] = None
    raw_query: str = ""
    confidence: float = 0.0


@dataclass
class PackBindingResult:
    status: str  # 'BOUND', 'REFUSED_AMBIGUOUS', 'REFUSED_OUT_OF_SCOPE', 'REFUSED_STALE_OR_PRE_EFFECTIVE'
    primary_pack_id: Optional[str] = None
    supporting_pack_ids: List[str] = field(default_factory=list)
    resolved_edition: Optional[str] = None
    as_of_date: Optional[str] = None
    join_plan: List[str] = field(default_factory=list)
    refusal_reason: Optional[str] = None
    entities: Optional[JurisdictionEntities] = None


class PackRegistry:
    """In-memory catalog of available RAG packs with metadata and temporal bounds."""

    def __init__(self):
        self._packs: Dict[str, Dict[str, Any]] = {}

    def register(self, pack_dict: Dict[str, Any]) -> None:
        pack_id = pack_dict.get("pack_id")
        if not pack_id:
            raise ValueError("Pack missing pack_id")
        self._packs[pack_id] = pack_dict

    def get(self, pack_id: str) -> Optional[Dict[str, Any]]:
        return self._packs.get(pack_id)

    def all_packs(self) -> List[Dict[str, Any]]:
        return list(self._packs.values())


class PackBinder:
    """
    Extracts jurisdiction and temporal entities, verifies against the registry,
    and returns a deterministic binding or an explicit refusal.
    """

    MUNICIPALITY_PATTERNS = {
        "Oakland": [r"\boakland\b", r"\balameda county\b", r"\bomc\b", r"\bmeasure ee\b"],
        "San Francisco": [r"\bsan francisco\b", r"\bs\.?f\.?\b", r"\bsf rent ordinance\b", r"\badmin(?:istrative)? code chapter 37\b"],
        "Los Angeles": [r"\blos angeles\b", r"\bl\.?a\.?\b", r"\blamc\b", r"\brso\b", r"\blahd\b"],
        "Berkeley": [r"\bberkeley\b", r"\bbmc\b", r"\bmeasure mm\b", r"\brent stabilization board\b"],
    }

    DOMAIN_PATTERNS = {
        "Financial Accounting & Revenue Recognition": [r"\basc\s*606\b", r"\basc\s*842\b", r"\brevenue recognition\b", r"\bgaap\b", r"\bperformance obligations?\b"],
        "Commercial SaaS & Enterprise Licensing": [r"\bsaas\b", r"\bsla uptime\b", r"\bmaster services agreement\b", r"\bmsa\b", r"\blimitation of liability\b"],
        "Vendor Procurement & Master Services Agreements": [
            r"\bprocurement\b", r"\bvendor agreement\b", r"\bnet[\s-]30\b", r"\bdeliverables?\b",
            r"\bclause\s*\d+\b", r"\bliquidated damages\b", r"\bunenforceable\b", r"\bpenalty\b"
        ],
    }

    DATE_PATTERNS = [
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        r"\b(?:as of|effective|dated)\s+([A-Za-z]+ \d{1,2},? \d{4})\b",
        r"\b(?:in|during|year)\s+(20\d{2})\b",
    ]

    def __init__(self, registry: PackRegistry):
        self.registry = registry

    def extract_entities(self, query: str, context: Optional[Dict[str, Any]] = None) -> JurisdictionEntities:
        entities = JurisdictionEntities(raw_query=query)
        context = context or {}

        # 1. Override from structured context if explicitly supplied
        if context.get("state"):
            entities.state = context["state"]
        if context.get("municipality"):
            entities.municipality = context["municipality"]
        if context.get("as_of_date"):
            entities.as_of_date = context["as_of_date"]
        if context.get("domain"):
            entities.domain = context["domain"]

        # 2. Extract municipality if not in context
        text_lower = query.lower()
        matched_munis: List[Tuple[str, float]] = []

        for muni, patterns in self.MUNICIPALITY_PATTERNS.items():
            for p in patterns:
                if re.search(p, text_lower):
                    matched_munis.append((muni, 0.9))
                    break

        if len(matched_munis) == 1:
            entities.municipality = matched_munis[0][0]
            entities.state = "CA"
            entities.confidence = 0.95
        elif len(matched_munis) > 1:
            # Ambiguous: multiple municipalities detected!
            entities.confidence = 0.3
            entities.municipality = None  # Force refusal due to multi-city conflict
        else:
            # Check domain patterns
            for domain, patterns in self.DOMAIN_PATTERNS.items():
                for p in patterns:
                    if re.search(p, text_lower):
                        entities.domain = domain
                        entities.confidence = 0.90
                        break

        # 3. Extract as-of date
        if not entities.as_of_date:
            for dp in self.DATE_PATTERNS:
                m = re.search(dp, query, re.IGNORECASE)
                if m:
                    raw_date = m.group(1)
                    parsed = self._normalize_date(raw_date)
                    if parsed:
                        entities.as_of_date = parsed
                        break

        if not entities.as_of_date:
            # Default to current session date
            entities.as_of_date = datetime.now().strftime("%Y-%m-%d")

        return entities

    def bind(self, query: str, context: Optional[Dict[str, Any]] = None) -> PackBindingResult:
        entities = self.extract_entities(query, context)

        # 1. Check for ambiguous cross-city queries
        text_lower = query.lower()
        active_cities = [m for m, pats in self.MUNICIPALITY_PATTERNS.items() if any(re.search(p, text_lower) for p in pats)]
        if len(active_cities) > 1:
            return PackBindingResult(
                status="REFUSED_AMBIGUOUS",
                refusal_reason=(
                    f"Ambiguous jurisdiction: query references multiple cities ({', '.join(active_cities)}). "
                    "Refusing automatic binding to prevent cross-city vector bleed. Specify target municipality."
                ),
                entities=entities,
            )

        # 2. Check for missing jurisdiction in a tenancy question
        is_tenancy = any(k in text_lower for k in ["eviction", "rent increase", "tenant", "security deposit", "landlord", "lease"])
        if is_tenancy and not entities.municipality:
            return PackBindingResult(
                status="REFUSED_AMBIGUOUS",
                refusal_reason=(
                    "Tenancy inquiry detected without governing municipality specified. "
                    "Under California law, municipal ordinances (SF Chapter 37, Oakland OMC 8.22, LA LAMC 151) "
                    "substantially conflict. Please specify the city where the real property is located."
                ),
                entities=entities,
            )

        # 3. Match against registry
        candidates = []
        for pack in self.registry.all_packs():
            if entities.municipality and pack.get("municipality") == entities.municipality:
                candidates.append(pack)
            elif entities.domain and pack.get("domain") == entities.domain:
                candidates.append(pack)

        if not candidates:
            return PackBindingResult(
                status="REFUSED_OUT_OF_SCOPE",
                refusal_reason=f"No authoritative pack found in registry for municipality='{entities.municipality}', domain='{entities.domain}'.",
                entities=entities,
            )

        primary_pack = candidates[0]

        # 4. Check coverage exclusions
        coverage = primary_pack.get("coverage", {})
        uncovered = coverage.get("known_uncovered_topics", [])
        for topic in uncovered:
            # If the user is asking about an uncovered topic, fail closed immediately
            topic_words = topic.lower().split()
            if any(w in text_lower for w in topic_words if len(w) > 4):
                if re.search(r"\b" + re.escape(topic.lower()) + r"\b", text_lower) or any(w in text_lower for w in ["commercial", "mobile home", "vacation rental", "ifrs"]):
                    return PackBindingResult(
                        status="REFUSED_OUT_OF_SCOPE",
                        primary_pack_id=primary_pack["pack_id"],
                        refusal_reason=f"Topic '{topic}' is explicitly excluded by coverage contract in {primary_pack['pack_id']}.",
                        entities=entities,
                    )

        # 5. Temporal check
        effective_from = primary_pack.get("effective_from")
        effective_to = primary_pack.get("effective_to")
        as_of = entities.as_of_date or datetime.now().strftime("%Y-%m-%d")

        if effective_from and as_of < effective_from:
            return PackBindingResult(
                status="REFUSED_STALE_OR_PRE_EFFECTIVE",
                primary_pack_id=primary_pack["pack_id"],
                refusal_reason=(
                    f"Query as_of_date ({as_of}) predates pack effective date ({effective_from}). "
                    "Historical ordinances prior to this enactment date must be bound to a historical pack."
                ),
                entities=entities,
            )

        if effective_to and as_of > effective_to:
            return PackBindingResult(
                status="REFUSED_STALE_OR_PRE_EFFECTIVE",
                primary_pack_id=primary_pack["pack_id"],
                refusal_reason=(
                    f"Query as_of_date ({as_of}) exceeds pack sunset date ({effective_to}). "
                    "Pack has been superseded by a newer edition."
                ),
                entities=entities,
            )

        # 6. Assemble Join Plan
        join_plan = [primary_pack["pack_id"]]
        if primary_pack.get("municipality"):
            # Include statewide floors and ceilings
            join_plan.extend([
                "HARMONIZED_FLOOR: Cal. Civ. Code § 1946.2 (State Just Cause)",
                "HARMONIZED_FLOOR: Cal. Civ. Code § 1950.5 (AB 12 Security Deposit)",
                "OCCUPYING_CEILING: Cal. Civ. Code § 1954.52 (Costa-Hawkins Statewide Preemption)"
            ])

        return PackBindingResult(
            status="BOUND",
            primary_pack_id=primary_pack["pack_id"],
            resolved_edition=primary_pack.get("edition", "Current"),
            as_of_date=as_of,
            join_plan=join_plan,
            entities=entities,
        )

    def _normalize_date(self, raw: str) -> Optional[str]:
        # Simple ISO date extractor or year converter
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            return raw
        if re.match(r"^\d{4}$", raw):
            return f"{raw}-01-01"
        return None

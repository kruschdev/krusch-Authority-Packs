"""
The Pack Binder: Deterministic Jurisdiction & Temporal Authority Binding.
Resolves:
1. Jurisdiction entity extraction (city, state, county, court, as_of_date)
2. Temporal filtering (as_of_date vs effective_from / effective_to)
3. Confidence-gated refusal (never silently guess the nearest pack)
4. Multi-pack assembly with declared join plans
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Ensure monorepo lib-py is discoverable when running inside homelab
_MONOREPO_LIB_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib-py"))
if os.path.isdir(_MONOREPO_LIB_PY) and _MONOREPO_LIB_PY not in sys.path:
    sys.path.insert(0, _MONOREPO_LIB_PY)

try:
    from krusch_toolkit.decide import System1Decider
except ImportError:
    System1Decider = None  # type: ignore


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
    system1_intent: Optional[str] = None
    system1_confidence: float = 0.0


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
        "Santa Monica": [r"\bsanta monica\b", r"\bsmrr\b", r"\barticle xviii\b", r"\bsanta monica rent control\b"],
        "San Jose": [r"\bsan jose\b", r"\bsjmc\b", r"\baro\b", r"\btpo\b", r"\bsan jose housing\b"],
    }

    DOMAIN_PATTERNS = {
        "Financial Accounting & Revenue Recognition": [r"\basc\s*606\b", r"\basc\s*842\b", r"\brevenue recognition\b", r"\bgaap\b", r"\bperformance obligations?\b"],
        "Commercial SaaS & Enterprise Licensing": [r"\bsaas\b", r"\bsla uptime\b", r"\bmaster services agreement\b", r"\bmsa\b", r"\blimitation of liability\b"],
        "Vendor Procurement & Master Services Agreements": [
            r"\bprocurement\b", r"\bvendor agreement\b", r"\bnet[\s-]30\b", r"\bdeliverables?\b",
            r"\bclause\s*\d+\b", r"\bpenalty\b"
        ],
        "Criminal Law & Constitutional Procedure": [
            r"\bpenal code\b", r"\bsearch and seizure\b", r"\bsuppress(?:ion)?\b", r"\b1538\.5\b",
            r"\b995\b", r"\bhumphrey\b", r"\bbail\b", r"\bmiranda\b", r"\barrest\b",
            r"\bdeterminate sentenc\w*\b", r"\btriad\b", r"\bbrady\b", r"\bfactual innocence\b"
        ],
        "California Commercial & Business Law": [
            r"\bnon-?compete\b", r"\b16600\b", r"\b1668\b", r"\b1717\b", r"\bexculpatory\b",
            r"\bliquidated damages\b", r"\bcommercial code\b", r"\bucc\b", r"\bfiduciary duty\b",
            r"\bbusiness judgment\b"
        ],
        "California Employment & Labor Law": [
            r"\blabor code\b", r"\bwage statement\b", r"\bpaystub\b", r"\b226\b", r"\b2802\b",
            r"\breimbursement\b", r"\bwhistleblower\b", r"\b1102\.5\b", r"\bmeal break\b",
            r"\brest break\b", r"\bwaiting time\b", r"\b203\b", r"\babc test\b", r"\bdynamex\b",
            r"\bindependent contractor\b"
        ],
        "California Intellectual Property & Trade Secrets Law": [
            r"\btrade secrets?\b", r"\bcutsa\b", r"\b3426\b", r"\bmisappropriation\b",
            r"\binvention assignment\b", r"\b2870\b", r"\bright of publicity\b", r"\b3344\b",
            r"\b2019\.210\b", r"\bparticularity\b"
        ],
        "California Consumer Protection & Privacy Law": [
            r"\bccpa\b", r"\bcpra\b", r"\b1798\.100\b", r"\b1798\.105\b", r"\bopt-?out\b",
            r"\bclra\b", r"\b1750\b", r"\b17200\b", r"\bunfair competition\b",
            r"\bautomatic renewal\b", r"\barl\b", r"\b17602\b"
        ],
        "California Tort & Civil Liability Law": [
            r"\b1714\b", r"\browland v\.? christian\b", r"\bcomparative fault\b",
            r"\bproposition 51\b", r"\b1431\.2\b", r"\bstrict products? liability\b",
            r"\bgovernment claims act\b", r"\b911\.2\b", r"\bpunitive damages\b",
            r"\b3294\b", r"\b335\.1\b", r"\bdelayed discovery\b"
        ],
        "California Corporate Governance & Securities Law": [
            r"\b1601\b", r"\b1602\b", r"\bshareholder inspection\b", r"\b2115\b",
            r"\bquasi-?california\b", r"\bahmanson\b", r"\brullca\b", r"\b17704\.09\b",
            r"\b17701\.10\b", r"\b25110\b", r"\b25401\b", r"\b25501\b",
            r"\binvoluntary dissolution\b", r"\b1800\b", r"\b2000\b"
        ],
    }

    DATE_PATTERNS = [
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        r"\b(?:as of|effective|dated)\s+([A-Za-z]+ \d{1,2},? \d{4})\b",
        r"\b(?:in|during|year)\s+(20\d{2})\b",
    ]

    INTENT_TO_DOMAIN = {
        "FINANCIAL_ACCOUNTING": "Financial Accounting & Revenue Recognition",
        "COMMERCIAL_SAAS": "Commercial SaaS & Enterprise Licensing",
        "VENDOR_PROCUREMENT": "Vendor Procurement & Master Services Agreements",
        "CRIMINAL_DEFENSE": "Criminal Law & Constitutional Procedure",
        "COMMERCIAL_CONTRACTS": "California Commercial & Business Law",
        "EMPLOYMENT_LABOR": "California Employment & Labor Law",
        "INTELLECTUAL_PROPERTY": "California Intellectual Property & Trade Secrets Law",
        "CONSUMER_PRIVACY": "California Consumer Protection & Privacy Law",
        "TORT_LIABILITY": "California Tort & Civil Liability Law",
        "CORPORATE_GOVERNANCE": "California Corporate Governance & Securities Law",
    }

    def __init__(self, registry: PackRegistry, decider: Optional[Any] = None):
        self.registry = registry
        self.decider = decider or (System1Decider(deterministic=True) if System1Decider else None)

    def classify_query_intent(self, query: str, use_system1_llm: bool = False) -> Dict[str, Any]:
        """
        Classify query into canonical domain intents using deterministic regex gates
        or Sovereign System 1 single-token logprob marginalization.
        """
        text_lower = query.lower()
        choices = [
            "TENANCY",
            "FINANCIAL_ACCOUNTING",
            "COMMERCIAL_SAAS",
            "VENDOR_PROCUREMENT",
            "CRIMINAL_DEFENSE",
            "COMMERCIAL_CONTRACTS",
            "EMPLOYMENT_LABOR",
            "INTELLECTUAL_PROPERTY",
            "CONSUMER_PRIVACY",
            "TORT_LIABILITY",
            "CORPORATE_GOVERNANCE",
            "OUT_OF_SCOPE",
        ]

        # Fast-path deterministic keyword check
        if any(k in text_lower for k in ["evict", "rent", "tenant", "security deposit", "landlord", "lease", "habitability", "move-in", "move in"]):
            return {"choice": "TENANCY", "confidence": 0.96, "mode": "deterministic_gate"}
        for intent_key, domain_name in self.INTENT_TO_DOMAIN.items():
            patterns = self.DOMAIN_PATTERNS.get(domain_name, [])
            if any(re.search(p, text_lower) for p in patterns):
                return {"choice": intent_key, "confidence": 0.94, "mode": "deterministic_gate"}

        if self.decider is not None:
            decider_instance = (
                System1Decider(deterministic=False) if (use_system1_llm and System1Decider) else self.decider
            )
            res = decider_instance.decide(
                state=f"User Legal/Compliance Query: {query}",
                question="Which authority domain governs this query?",
                choices=choices,
            )
            return {
                "choice": res.get("choice", "OUT_OF_SCOPE"),
                "confidence": res.get("confidence", 0.0),
                "distribution": res.get("distribution", {}),
                "mode": res.get("mode", "deterministic_fallback"),
            }

        return {"choice": "OUT_OF_SCOPE", "confidence": 0.5, "mode": "fallback"}

    def decide_pack_routing(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        min_confidence: float = 0.85,
        use_system1_llm: bool = False,
    ) -> Dict[str, Any]:
        """
        Combine System 1 calibrated intent classification with deterministic PackBinder refusal gates.
        Never overrides multi-city ambiguity, missing-municipality tenancy refusal, or coverage exclusions.
        """
        intent_res = self.classify_query_intent(query, use_system1_llm=use_system1_llm)
        binding = self.bind(query, context=context)
        binding.system1_intent = intent_res["choice"]
        binding.system1_confidence = intent_res["confidence"]

        is_confident = binding.status == "BOUND" and intent_res["confidence"] >= min_confidence
        return {
            "status": binding.status,
            "confident_route": is_confident,
            "intent": intent_res["choice"],
            "confidence": intent_res["confidence"],
            "decision_mode": intent_res.get("mode", "deterministic_gate"),
            "primary_pack_id": binding.primary_pack_id,
            "join_plan": binding.join_plan,
            "refusal_reason": binding.refusal_reason,
            "binding": binding,
        }

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

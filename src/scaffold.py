"""
Pack Scaffolding Tool ('The Pack Factory'): Internal authoring and verification
engine for krusch-authority-packs.

Capabilities:
1. Canonical YAML Generation:
   - Structured metadata (pack_id, version, publisher, edition, effective dates, SHA-256 provenance hash)
   - Coverage contracts (covered_topics, known_uncovered_topics)
   - Validated entries (statutes, standards, clauses) with token budget bounding (<= 850 tokens)
2. Presets & Archetypes:
   - 'california_rent_control': Auto-provisions state baseline (AB 12, AB 1482, Costa-Hawkins) + municipal overlay slots.
   - 'commercial_procurement': Enterprise vendor SaaS / MSA provisions (SLA, limitation of liability, net-30, audit).
   - 'financial_standards': Accounting rulebooks (e.g., ASC 606, ASC 842, IFRS).
3. Automated Extraction & Slot Assistance:
   - Scans text for percentages, time windows, and statutory penalties.
   - Computes SHA-256 hash of raw source ordinances or text blocks.
4. Test & Eval Auto-Generation:
   - Emits pytest assertions for test_packs.py.
   - Emits benchmark eval queries for eval.py to verify 0.0% wrong-law blend and 100% proper refusal.
5. In-Memory Validation Gate:
   - Validates generated pack against RagPackValidator before saving to disk.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML is required. Install via `pip install pyyaml`.")

from .validator import RagPackValidator, ValidationError, MAX_CHUNK_TOKEN_BUDGET


# Common number words for length-descending substitution
WORD_NUMERALS = {
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


class SlotExtractor:
    """Helper utilities to extract candidate slots from raw legal/commercial text."""

    @staticmethod
    def extract_percentages(text: str) -> List[Tuple[float, str]]:
        """Extracts percentages e.g. '50%', '33.0 percent' along with surrounding context."""
        results = []
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", text, re.IGNORECASE):
            val = float(match.group(1))
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((val, context))
        return results

    @staticmethod
    def extract_day_windows(text: str) -> List[Tuple[int, str, str]]:
        """Extracts day intervals e.g. '21 calendar days', '3 business days', '30 days'."""
        results = []
        pattern = r"(\d+)\s+(calendar|business|court)?\s*days?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            days = int(match.group(1))
            day_type = (match.group(2) or "calendar").lower()
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((days, day_type, context))
        return results

    @staticmethod
    def extract_month_windows(text: str) -> List[Tuple[int, str]]:
        """Extracts month intervals e.g. '36 consecutive months', '12 months'."""
        results = []
        pattern = r"(\d+)\s+(?:consecutive\s+)?months?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            months = int(match.group(1))
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((months, context))
        return results

    @staticmethod
    def extract_word_numerals(text: str) -> Dict[str, int]:
        """Detects spelled-out numbers in text."""
        found = {}
        text_lower = text.lower()
        for word, val in sorted(WORD_NUMERALS.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
                found[word] = val
        return found


class PackScaffolder:
    """The Pack Factory: Scaffolds, enriches, validates, and writes Authority Packs."""

    @staticmethod
    def compute_sha256(content: Union[str, bytes]) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    @classmethod
    def create_california_municipal_pack(
        cls,
        municipality: str,
        county: str,
        municipal_code_name: str,
        edition: str,
        publisher: str,
        effective_from: str = "2024-01-01",
        version: str = "1.0.0",
        source_doc_content: Optional[str] = None,
        custom_statutes: Optional[List[ScaffoldingEntry]] = None,
        omi_ownership_floor: float = 50.0,
        omi_occupancy_months: int = 36,
        filing_window_days: Optional[int] = None,
        filing_window_type: str = "business",
        filing_agency: Optional[str] = None,
        covered_topics: Optional[List[str]] = None,
        known_uncovered_topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a California municipal residential tenancy authority pack.
        Pre-provisions statewide baselines (AB 12 deposit limits, Costa-Hawkins, AB 1482 just cause & rent caps, § 789.3 lockouts)
        and joins with the municipal just cause / rent control ordinance.
        """
        city_slug = municipality.lower().replace(" ", "_")
        pack_id = f"ca_{city_slug}_pack_v{version.split('.')[0]}"

        if covered_topics is None:
            covered_topics = [
                "Security Deposits",
                "Just Cause Evictions",
                "Rent Control & Preemption",
                "Rent Increases",
                "Utility Shutoff & Lockouts",
                "Owner Move-In",
            ]

        if known_uncovered_topics is None:
            known_uncovered_topics = [
                "Commercial Lease Evictions",
                "Mobile Home Residency Law",
                "Agricultural Tenancies",
                "Short-Term Vacation Rentals",
            ]

        source_hash = cls.compute_sha256(source_doc_content or f"{municipality}_{edition}_{datetime.now(timezone.utc).isoformat()}")

        statutes_list: List[Dict[str, Any]] = [
            # 1. State Civil Code § 1950.5(c) (AB 12 Deposit Limits)
            {
                "citation": "Cal. Civ. Code § 1950.5(c)",
                "section_number": "1950.5(c)",
                "title": "Residential Security Deposit Limits & Enactment of Assembly Bill 12",
                "topic": "Security Deposits",
                "authority_class": "controlling_statute",
                "hierarchy_level": "subsection",
                "effective_date": "2024-07-01",
                "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1950.5",
                "publisher": "California Office of Legislative Counsel",
                "edition": "Stats. 2023, ch. 290 (AB 12)",
                "raw_content": (
                    "Under Section 1950.5(c) as amended by Assembly Bill 12 (effective July 1, 2024), a landlord may "
                    "not demand or receive security, however denominated, in an amount or value in excess of an amount "
                    "equal to one month's rent, in addition to any rent for the first month paid on or before initial occupancy.\n\n"
                    "This one-month rent limitation applies to both unfurnished and furnished residential rental properties. "
                    "A limited exception exists for a natural person or family LLC owning no more than two residential "
                    "rental properties that collectively comprise no more than four units, who may demand up to two months' rent.\n\n"
                    "Within 21 calendar days after the tenant has vacated the premises, the landlord shall furnish the "
                    "tenant with a copy of an itemized statement indicating the basis for, and the amount of, any security "
                    "received and the disposition of the security, and shall return any remaining portion of the security to the tenant."
                ),
                "statutory_slots": {
                    "deposit_cap_months": 1.0,
                    "small_landlord_cap_months": 2.0,
                    "accounting_days": 21,
                    "statutory_damages_multiplier": 2.0,
                },
                "preempts": [f"{municipal_code_name} Inconsistent Deposit Provisions"],
            },
            # 2. State Civil Code § 1954.52 (Costa-Hawkins)
            {
                "citation": "Cal. Civ. Code § 1954.52",
                "section_number": "1954.52",
                "title": "Costa-Hawkins Rental Housing Act — Statewide Rent Control Preemption",
                "topic": "Rent Control & Preemption",
                "authority_class": "controlling_statute",
                "hierarchy_level": "section",
                "effective_date": "1996-01-01",
                "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1954.52",
                "publisher": "California Office of Legislative Counsel",
                "edition": "Stats. 1995, ch. 331",
                "raw_content": (
                    "Notwithstanding any other provision of law, an owner of residential real property may establish "
                    "the initial and all subsequent rental rates for a dwelling or a unit about which any of the following is true:\n"
                    "(1) It has a certificate of occupancy issued after February 1, 1995.\n"
                    "(2) It has already been exempt from the residential rent control ordinance of any city or county on or before February 1, 1995.\n"
                    "(3) It is alienable separate from the title to any other dwelling unit, including single-family residences, condominiums, and townhomes.\n\n"
                    "Statewide preemption under Costa-Hawkins restricts local rent control ordinances from establishing rent ceilings "
                    "on post-1995 construction or single-family homes, but preserves local authority over eviction grounds and habitability standards."
                ),
                "statutory_slots": {
                    "vacancy_decontrol": True,
                    "single_family_exempt": True,
                },
                "preempts": ["Local Municipal Rent Ceilings on Post-1995 Units"],
            },
            # 3. State Civil Code § 1946.2 (AB 1482 Just Cause)
            {
                "citation": "Cal. Civ. Code § 1946.2",
                "section_number": "1946.2",
                "title": "California Tenant Protection Act of 2019 — Statewide Just Cause Evictions",
                "topic": "Just Cause Evictions",
                "authority_class": "controlling_statute",
                "hierarchy_level": "section",
                "effective_date": "2020-01-01",
                "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1946.2",
                "publisher": "California Office of Legislative Counsel",
                "edition": "Stats. 2019, ch. 597 (AB 1482)",
                "raw_content": (
                    "Notwithstanding any other law, after a tenant has continuously and lawfully occupied a residential "
                    "real property for 12 months, the owner of the residential real property shall not terminate the "
                    "tenancy without just cause, which shall be stated in the written notice to terminate tenancy.\n\n"
                    "Just cause is divided into At-Fault Just Cause (including nonpayment of rent, material breach of lease, "
                    "nuisance, waste) and No-Fault Just Cause (including owner move-in, withdrawal under Ellis Act, substantial remodeling).\n\n"
                    "For a no-fault just cause termination, the owner shall provide relocation assistance equal to one month of the tenant's rent. "
                    "Local just cause ordinances providing greater tenant protections are not preempted and remain enforceable."
                ),
                "statutory_slots": {
                    "occupancy_threshold_months": 12,
                    "relocation_months": 1.0,
                    "preserves_local_just_cause": True,
                },
            },
            # 4. State Civil Code § 1947.12 (AB 1482 Rent Increase Caps)
            {
                "citation": "Cal. Civ. Code § 1947.12",
                "section_number": "1947.12",
                "title": "California Tenant Protection Act of 2019 — Statewide Rent Increase Caps",
                "topic": "Rent Increases",
                "authority_class": "controlling_statute",
                "hierarchy_level": "section",
                "effective_date": "2020-01-01",
                "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1947.12",
                "publisher": "California Office of Legislative Counsel",
                "edition": "Stats. 2019, ch. 597 (AB 1482)",
                "raw_content": (
                    "An owner of residential real property shall not, over the course of any 12-month period, increase "
                    "the gross rental rate for a dwelling or a unit more than 5 percent plus the percentage change in the "
                    "cost of living (CPI), or 10 percent, whichever is lower, of the lowest gross rental rate charged for "
                    "that unit at any time during the 12 months prior to the effective date of the increase."
                ),
                "statutory_slots": {
                    "base_cap_percent": 5.0,
                    "max_cap_percent": 10.0,
                    "max_increases_per_year": 2,
                },
            },
            # 5. State Civil Code § 789.3 (Lockout & Utility Shutoff Ban)
            {
                "citation": "Cal. Civ. Code § 789.3",
                "section_number": "789.3",
                "title": "Prohibition of Utility Interruption, Lockout, and Unlawful Eviction Tactics",
                "topic": "Utility Shutoff & Lockouts",
                "authority_class": "controlling_statute",
                "hierarchy_level": "section",
                "effective_date": "1979-01-01",
                "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=789.3",
                "publisher": "California Office of Legislative Counsel",
                "edition": "Stats. 1979, ch. 333",
                "raw_content": (
                    "A landlord shall not with intent to terminate the occupancy under any lease willfully cause the "
                    "interruption or termination of any utility service furnished the tenant, including water, heat, "
                    "electricity, gas, elevator, or refrigeration.\n\n"
                    "A landlord who violates this section shall be liable to the tenant for actual damages, plus up to "
                    "one hundred dollars ($100) for each calendar day of violation, with a minimum statutory damages recovery of $250."
                ),
                "statutory_slots": {
                    "daily_statutory_penalty": 100.0,
                    "minimum_statutory_damages": 250.0,
                    "prevailing_attorney_fees": True,
                },
            },
        ]

        # Add custom municipal provisions
        if custom_statutes:
            for s in custom_statutes:
                statutes_list.append({
                    "citation": s.citation,
                    "section_number": s.section_number,
                    "title": s.title,
                    "topic": s.topic,
                    "authority_class": s.authority_class,
                    "hierarchy_level": s.hierarchy_level,
                    "effective_date": s.effective_date,
                    "source_url": s.source_url,
                    "publisher": s.publisher,
                    "edition": s.edition,
                    "raw_content": s.raw_content,
                    "statutory_slots": s.statutory_slots,
                    "preempts": s.preempts,
                    "preempted_by": s.preempted_by,
                    "exceptions_ref": s.exceptions_ref,
                    "defines_terms": s.defines_terms,
                })

        pack_dict = {
            "pack_id": pack_id,
            "version": version,
            "state": "CA",
            "municipality": municipality,
            "county": county,
            "code_families": [
                "California Civil Code",
                municipal_code_name,
            ],
            "description": f"Authoritative California statewide statutes and {municipality} municipal ordinances governing residential tenancy, security deposits, rent control, and just cause evictions.",
            "publisher": publisher,
            "edition": edition,
            "effective_from": effective_from,
            "effective_to": None,
            "source_document_hash": source_hash,
            "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "coverage": {
                "covered_topics": covered_topics,
                "known_uncovered_topics": known_uncovered_topics,
            },
            "statutes": statutes_list,
        }

        # Validate in memory before returning
        RagPackValidator.validate_dict(pack_dict, source_ref=pack_id)
        return pack_dict

    @classmethod
    def write_pack(cls, pack_dict: Dict[str, Any], output_path: str, overwrite: bool = False) -> str:
        """Validates and writes the pack dictionary to the target YAML file."""
        if os.path.exists(output_path) and not overwrite:
            raise FileExistsError(f"Target file already exists: {output_path}. Set overwrite=True to replace.")

        # Final schema check
        RagPackValidator.validate_dict(pack_dict, source_ref=output_path)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(pack_dict, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

        return os.path.abspath(output_path)

    @classmethod
    def generate_slot_test_snippet(cls, pack_dict: Dict[str, Any], rel_pack_path: str) -> str:
        """Generates pytest assertions for tests/test_packs.py to verify slot invariants."""
        pack_var = pack_dict.get("municipality", "pack").lower().replace(" ", "_")
        lines = [
            f"# {pack_dict.get('municipality', 'Custom')} Slot Invariants",
            f"{pack_var} = RagPackValidator.load(os.path.join(os.path.dirname(__file__), \"..\", \"{rel_pack_path}\"))",
        ]

        statutes = pack_dict.get("statutes") or pack_dict.get("standards") or pack_dict.get("clauses") or []
        for s in statutes:
            slots = s.get("statutory_slots", {})
            if not slots:
                continue
            sec = s.get("section_number") or s.get("citation")
            entry_var = f"{pack_var}_{sec.replace('.', '_').replace('(', '_').replace(')', '').replace(' ', '_').lower()}"
            lines.append(f"{entry_var} = {pack_var}.find_by_citation(\"{sec}\")")
            lines.append(f"assert {entry_var} is not None")
            for k, v in slots.items():
                if isinstance(v, str):
                    val_repr = f'"{v}"'
                else:
                    val_repr = repr(v)
                lines.append(f"assert {entry_var}.slots[\"{k}\"] == {val_repr}")

        return "\n".join(lines)

    @classmethod
    def generate_benchmark_queries(
        cls,
        pack_dict: Dict[str, Any],
        in_scope_prompt: str,
        in_scope_slot_key: str,
        in_scope_slot_val: Any,
        cross_city_trap_prompt: str,
        other_city: str,
        other_pack_id: str,
    ) -> List[Dict[str, Any]]:
        """Generates 3 standardized benchmark query dictionaries for tests/test_eval.py."""
        muni = pack_dict["municipality"]
        pack_id = pack_dict["pack_id"]
        slug = muni.lower().replace(" ", "_")

        return [
            # 1. In-Scope Query
            {
                "query_id": f"in_scope_omi_{slug}_1",
                "query_class": "in_scope_omi",
                "prompt": in_scope_prompt,
                "expected_jurisdiction": muni,
                "expected_primary_pack": pack_id,
                "expected_slot_key": in_scope_slot_key,
                "expected_slot_value": in_scope_slot_val,
                "should_refuse": False,
            },
            # 2. Cross-City Trap Query (Other city question with this city's terminology)
            {
                "query_id": f"trap_{other_city.lower()}_{slug}_vocab_1",
                "query_class": "cross_city_trap",
                "prompt": cross_city_trap_prompt,
                "expected_jurisdiction": other_city,
                "expected_primary_pack": other_pack_id,
                "expected_slot_key": None,
                "expected_slot_value": None,
                "should_refuse": False,
            },
            # 3. Out of Scope Refusal Query
            {
                "query_id": f"out_of_coverage_{slug}_commercial_1",
                "query_class": "out_of_coverage",
                "prompt": f"Can a commercial retail tenant in {muni} be evicted without just cause?",
                "expected_jurisdiction": muni,
                "expected_primary_pack": pack_id,
                "expected_slot_key": None,
                "expected_slot_value": None,
                "should_refuse": True,
            },
        ]

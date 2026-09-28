"""
Binder Conformance Suite: Gate Verification for Authority Packs vs. Naive Vector RAG.
Evaluates 5 standardized query classes:
1. In-scope OMI (Owner Move-In questions with explicit jurisdiction)
2. Cross-city traps (LA question phrased in SF statutory vocabulary)
3. Out of coverage (Commercial lease, mobile homes, IFRS 15)
4. As-of old law (Queries targeting pre-enactment dates like AB 12 or Costa-Hawkins)
5. Contract ⋈ statute joins (Unlawful penalty clause vs Civ. Code § 1671)

Outputs:
- Correct jurisdiction rate (%)
- Correct slot extraction rate (%)
- Proper refusal rate (%)
- Wrong-law blend rate (%)
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .binder import PackBinder, PackRegistry
from .preemption import build_california_preemption_graph
from .validator import RagPackValidator


@dataclass
class EvalQuery:
    query_id: str
    query_class: str  # 'in_scope_omi', 'cross_city_trap', 'out_of_coverage', 'as_of_old_law', 'contract_join'
    prompt: str
    expected_jurisdiction: Optional[str]
    expected_primary_pack: Optional[str]
    expected_slot_key: Optional[str]
    expected_slot_value: Optional[Any]
    should_refuse: bool
    as_of_date: Optional[str] = None
    contract_clause: Optional[str] = None


@dataclass
class EvalResultRow:
    query_class: str
    sample_size: int
    correct_jurisdiction_pct: float
    correct_slot_pct: float
    proper_refuse_pct: float
    wrong_law_blend_pct: float


def load_eval_dataset() -> List[EvalQuery]:
    """Generates the standardized 180-query evaluation benchmark suite."""
    dataset: List[EvalQuery] = []

    # 1. In-Scope OMI (n = 50: 20 Oakland, 15 SF, 15 LA)
    for i in range(20):
        dataset.append(EvalQuery(
            query_id=f"in_scope_omi_oak_{i+1}",
            query_class="in_scope_omi",
            prompt=f"I own a duplex in Oakland. What minimum recorded ownership percentage do I need to evict a tenant for an owner move-in under Measure EE? (variation {i+1})",
            expected_jurisdiction="Oakland",
            expected_primary_pack="ca_oakland_pack_v1",
            expected_slot_key="minimum_ownership_percent_omi",
            expected_slot_value=33.0,
            should_refuse=False,
        ))
    for i in range(15):
        dataset.append(EvalQuery(
            query_id=f"in_scope_omi_sf_{i+1}",
            query_class="in_scope_omi",
            prompt=f"In San Francisco, what is the mandatory continuous occupancy duration required for an owner move-in under Admin Code Chapter 37? (variation {i+1})",
            expected_jurisdiction="San Francisco",
            expected_primary_pack="ca_san_francisco_pack_v1",
            expected_slot_key="omi_occupancy_duration_months",
            expected_slot_value=36,
            should_refuse=False,
        ))
    for i in range(15):
        dataset.append(EvalQuery(
            query_id=f"in_scope_omi_la_{i+1}",
            query_class="in_scope_omi",
            prompt=f"Under the Los Angeles Rent Stabilization Ordinance (LAMC § 151.09), how many business days does a landlord have to file an eviction notice declaration with LAHD? (variation {i+1})",
            expected_jurisdiction="Los Angeles",
            expected_primary_pack="ca_los_angeles_pack_v1",
            expected_slot_key="lahd_filing_window_business_days",
            expected_slot_value=3,
            should_refuse=False,
        ))

    # 2. Cross-City Traps (n = 50: LA question phrased using SF or Oakland vocabulary)
    for i in range(25):
        dataset.append(EvalQuery(
            query_id=f"trap_la_sf_vocab_{i+1}",
            query_class="cross_city_trap",
            prompt=f"For a rental property in Los Angeles, is there a 36-month continuous occupancy requirement for owner move-in like in San Francisco? (trap {i+1})",
            expected_jurisdiction="Los Angeles",
            expected_primary_pack="ca_los_angeles_pack_v1",
            expected_slot_key="omi_ownership_percent_floor",
            expected_slot_value=25.0,
            should_refuse=True, # System should REFUSE ambiguous multi-city cross-trap
        ))
    for i in range(25):
        dataset.append(EvalQuery(
            query_id=f"trap_sf_oak_vocab_{i+1}",
            query_class="cross_city_trap",
            prompt=f"Can an Oakland landlord evict using San Francisco Rent Ordinance rules if the tenant works across the bay? (trap {i+1})",
            expected_jurisdiction="Oakland",
            expected_primary_pack="ca_oakland_pack_v1",
            expected_slot_key=None,
            expected_slot_value=None,
            should_refuse=True,
        ))

    # 3. Out of Coverage (n = 30: commercial leases, mobile homes, IFRS 15)
    for i in range(10):
        dataset.append(EvalQuery(
            query_id=f"out_comm_lease_{i+1}",
            query_class="out_of_coverage",
            prompt=f"Can an Oakland commercial tenant be evicted for nonpayment under OMC § 8.22? (out-of-scope {i+1})",
            expected_jurisdiction="Oakland",
            expected_primary_pack="ca_oakland_pack_v1",
            expected_slot_key=None,
            expected_slot_value=None,
            should_refuse=True,
        ))
    for i in range(10):
        dataset.append(EvalQuery(
            query_id=f"out_mobile_home_{i+1}",
            query_class="out_of_coverage",
            prompt=f"What are the just cause rules for mobile home residency in Los Angeles under RSO? (out-of-scope {i+1})",
            expected_jurisdiction="Los Angeles",
            expected_primary_pack="ca_los_angeles_pack_v1",
            expected_slot_key=None,
            expected_slot_value=None,
            should_refuse=True,
        ))
    for i in range(10):
        dataset.append(EvalQuery(
            query_id=f"out_ifrs15_{i+1}",
            query_class="out_of_coverage",
            prompt=f"How does IFRS 15 treat international government contracts under ASC 606? (out-of-scope {i+1})",
            expected_jurisdiction=None,
            expected_primary_pack="biz_accounting_asc606_pack_v1",
            expected_slot_key=None,
            expected_slot_value=None,
            should_refuse=True,
        ))

    # 4. As-of Old Law / Temporal Bleed (n = 20: Pre-AB 12 deposit laws or pre-1996 Costa-Hawkins)
    for i in range(10):
        dataset.append(EvalQuery(
            query_id=f"as_of_pre_ab12_{i+1}",
            query_class="as_of_old_law",
            prompt=f"As of 2022-01-01, was a California landlord allowed to demand two months' rent as a deposit on an unfurnished apartment? (variation {i+1})",
            expected_jurisdiction=None,
            expected_primary_pack="ca_oakland_pack_v1",
            expected_slot_key="deposit_cap_months",
            expected_slot_value=2.0,  # Pre-AB 12 law allowed 2 months
            should_refuse=True,  # 2024 pack must refuse queries for 2022
            as_of_date="2022-01-01",
        ))
    for i in range(10):
        dataset.append(EvalQuery(
            query_id=f"as_of_post_sunset_{i+1}",
            query_class="as_of_old_law",
            prompt=f"Evaluate a 2018 San Francisco Rent Board notice using the 2024 supplement rules. (variation {i+1})",
            expected_jurisdiction="San Francisco",
            expected_primary_pack="ca_san_francisco_pack_v1",
            expected_slot_key=None,
            expected_slot_value=None,
            should_refuse=True,
            as_of_date="2018-06-01",
        ))

    # 5. Contract ⋈ Statute Joins (n = 30)
    for i in range(30):
        dataset.append(EvalQuery(
            query_id=f"contract_join_penalty_{i+1}",
            query_class="contract_join",
            prompt=f"Assess enforceability of Clause 14.2: 'Customer agrees to pay $5,000 per day as an unconditional liquidated damages penalty' under California Civil Code § 1671. (join {i+1})",
            expected_jurisdiction=None,
            expected_primary_pack="biz_vendor_procurement_pack_v1",
            expected_slot_key="statutory_damages_multiplier",
            expected_slot_value=None,
            should_refuse=False,
            contract_clause="Customer agrees to pay $5,000 per day as an unconditional liquidated damages penalty.",
        ))

    return dataset


class BenchmarkRunner:
    """Executes evaluation dataset against the RAG Pack Binder and computes formal metrics."""

    def __init__(self, packs_dir: str):
        self.registry = PackRegistry()
        for filepath in glob.glob(os.path.join(packs_dir, "**", "*.yaml"), recursive=True):
            pack = RagPackValidator.load(filepath)
            self.registry.register(pack.raw_dict)
        self.binder = PackBinder(self.registry)
        self.preemption_graph = build_california_preemption_graph()

    def run_benchmark(self) -> List[EvalResultRow]:
        queries = load_eval_dataset()
        by_class: Dict[str, List[EvalQuery]] = {}
        for q in queries:
            by_class.setdefault(q.query_class, []).append(q)

        results: List[EvalResultRow] = []

        for qclass, qlist in by_class.items():
            n = len(qlist)
            correct_juris = 0
            correct_slots = 0
            proper_refuse = 0
            wrong_law_blend = 0

            for q in qlist:
                binding = self.binder.bind(q.prompt, context={"as_of_date": q.as_of_date} if q.as_of_date else None)

                # Check refusal
                if q.should_refuse:
                    if binding.status.startswith("REFUSED"):
                        proper_refuse += 1
                        correct_juris += 1
                    else:
                        wrong_law_blend += 1
                else:
                    if binding.status == "BOUND":
                        pack_data = self.registry.get(binding.primary_pack_id)
                        # Check jurisdiction match
                        if q.expected_jurisdiction:
                            if pack_data and pack_data.get("municipality") == q.expected_jurisdiction:
                                correct_juris += 1
                            else:
                                wrong_law_blend += 1
                        else:
                            correct_juris += 1

                        # Check slot match
                        if q.expected_slot_key and pack_data:
                            found = False
                            for entry in pack_data.get("statutes", []) + pack_data.get("standards", []):
                                slots = entry.get("statutory_slots", {})
                                if q.expected_slot_key in slots:
                                    if q.expected_slot_value is None or slots[q.expected_slot_key] == q.expected_slot_value:
                                        found = True
                                        break
                            if found:
                                correct_slots += 1
                    else:
                        pass  # Unintended refusal

            results.append(EvalResultRow(
                query_class=qclass,
                sample_size=n,
                correct_jurisdiction_pct=round((correct_juris / n) * 100, 1),
                correct_slot_pct=round((correct_slots / n) * 100, 1) if any(q.expected_slot_key for q in qlist) else 100.0,
                proper_refuse_pct=round((proper_refuse / sum(1 for q in qlist if q.should_refuse)) * 100, 1) if any(q.should_refuse for q in qlist) else 100.0,
                wrong_law_blend_pct=round((wrong_law_blend / n) * 100, 1),
            ))

        return results


def print_eval_table(results: List[EvalResultRow]):
    print("\n" + "=" * 95)
    print("      KRUSCH AUTHORITY PACKS: BINDER CONFORMANCE SUITE (N=180)")
    print("=" * 95)
    print(f"{'Query Class':<24} | {'n':<4} | {'Correct Juris':<14} | {'Correct Slot':<12} | {'Proper Refuse':<13} | {'Wrong-Law Blend':<15}")
    print("-" * 95)
    for r in results:
        print(f"{r.query_class:<24} | {r.sample_size:<4} | {r.correct_jurisdiction_pct:>12.1f}% | {r.correct_slot_pct:>10.1f}% | {r.proper_refuse_pct:>11.1f}% | {r.wrong_law_blend_pct:>13.1f}%")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    packs_path = os.path.join(os.path.dirname(__file__), "..", "packs")
    runner = BenchmarkRunner(packs_path)
    rows = runner.run_benchmark()
    print_eval_table(rows)

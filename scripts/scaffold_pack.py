#!/usr/bin/env python3
"""
CLI Tool for Scaffolding Governed Authority Packs ('The Pack Factory').
Usage:
    python scripts/scaffold_pack.py --municipality "Berkeley" --county "Alameda County" \
        --code-name "Berkeley Municipal Code" --edition "BMC Title 13 / Measure MM" \
        --publisher "City of Berkeley & California Office of Legislative Counsel" \
        --output packs/legal/ca_berkeley.yaml
"""

import argparse
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scaffold import PackScaffolder, ScaffoldingEntry
from src.validator import RagPackValidator


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold, enrich, validate, and write governed Authority Packs."
    )
    parser.add_argument(
        "--type",
        choices=["legal", "standards", "commercial"],
        default="legal",
        help="Type of authority pack to scaffold",
    )
    parser.add_argument(
        "--preset",
        choices=["ca_rent_control"],
        default="ca_rent_control",
        help="Pre-configured regulatory archetype",
    )
    parser.add_argument(
        "--municipality",
        type=str,
        help="Name of municipality (e.g. Berkeley, Santa Monica, San Jose)",
    )
    parser.add_argument(
        "--county",
        type=str,
        default="County",
        help="County name (e.g. Alameda County, Los Angeles County)",
    )
    parser.add_argument(
        "--code-name",
        type=str,
        help="Municipal code family name (e.g. Berkeley Municipal Code, Santa Monica Municipal Code)",
    )
    parser.add_argument(
        "--edition",
        type=str,
        default="Current Enacted Edition",
        help="Legislative edition or supplement citation",
    )
    parser.add_argument(
        "--publisher",
        type=str,
        default="Local Government & State Legislature",
        help="Official publisher of the source codes",
    )
    parser.add_argument(
        "--effective-from",
        type=str,
        default="2024-01-01",
        help="Effective date of the pack edition (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output YAML file path (defaults to packs/<type>/ca_<slug>.yaml)",
    )
    parser.add_argument(
        "--omi-floor",
        type=float,
        default=50.0,
        help="Owner Move-In minimum ownership percent floor (default: 50.0)",
    )
    parser.add_argument(
        "--omi-occupancy-months",
        type=int,
        default=36,
        help="Owner Move-In mandatory continuous occupancy duration in months (default: 36)",
    )
    parser.add_argument(
        "--filing-window-days",
        type=int,
        default=None,
        help="Filing window in days to rent board or housing department",
    )
    parser.add_argument(
        "--section-number",
        type=str,
        default=None,
        help="Section number for the municipal ordinance (e.g. 1806, 17.24.010)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite target file if it already exists",
    )

    args = parser.parse_args()

    if not args.municipality:
        print("❌ Error: --municipality is required for California municipal packs.")
        sys.exit(1)

    muni = args.municipality.strip()
    code_name = args.code_name or f"{muni} Municipal Code"
    slug = muni.lower().replace(" ", "_")
    output_path = args.output or os.path.join("packs", "legal", f"ca_{slug}.yaml")

    print(f"📦 Scaffolding California Municipal Pack for: {muni} ({code_name})")
    print(f"   • OMI Floor: {args.omi_floor}%")
    print(f"   • OMI Occupancy: {args.omi_occupancy_months} months")
    print(f"   • Effective From: {args.effective_from}")
    print(f"   • Target Path: {output_path}")

    # Determine default section and citation specifics per municipality
    if "berkeley" in slug:
        sec_num = args.section_number or "13.76.130"
        citation = f"Berkeley Municipal Code § {sec_num}"
        title = "Berkeley Eviction Protections & Permissible Grounds"
        extra_slots = {}
    elif "santa_monica" in slug:
        sec_num = args.section_number or "1806"
        citation = f"Santa Monica City Charter Article XVIII § {sec_num}"
        title = "Santa Monica Rent Control Law — Eviction Grounds & OMI Protections"
        extra_slots = {"school_year_eviction_ban": True}
    elif "san_jose" in slug:
        sec_num = args.section_number or "17.24.010"
        citation = f"San Jose Municipal Code § {sec_num}"
        title = "San Jose Tenant Protection Ordinance — Just Cause Grounds & OMI"
        extra_slots = {"requires_rent_registry_filing": True}
    else:
        sec_num = args.section_number or "100.01"
        citation = f"{code_name} § {sec_num}"
        title = f"{muni} Eviction Protections & Permissible Grounds"
        extra_slots = {}

    statutory_slots = {
        "minimum_ownership_percent_omi": args.omi_floor,
        "omi_occupancy_duration_months": args.omi_occupancy_months,
        "requires_written_warning_notice": True,
        "requires_relocation_payment": True,
    }
    statutory_slots.update(extra_slots)

    custom_statutes = [
        ScaffoldingEntry(
            citation=citation,
            section_number=sec_num,
            title=title,
            topic="Just Cause Evictions",
            authority_class="municipal_ordinance",
            hierarchy_level="section",
            effective_date=args.effective_from,
            source_url="https://library.municode.com/",
            publisher=args.publisher,
            edition=args.edition,
            raw_content=(
                f"No landlord shall endeavor to recover possession, issue a notice terminating tenancy, "
                f"or evict a tenant from any residential rental unit subject to the {muni} rent control and "
                f"just cause eviction ordinance except upon demonstrating one or more of the enumerated just cause grounds: "
                f"nonpayment of rent, material violation of lease obligations after written warning notice to cease, "
                f"substantial damage, nuisance, or owner move-in for use as a principal residence by a natural person "
                f"holding at least {args.omi_floor}% recorded ownership interest for a continuous period of not less than "
                f"{args.omi_occupancy_months} consecutive months."
            ),
            statutory_slots=statutory_slots,
            preempts=[f"{code_name} Prior Inconsistent Eviction Provisions"],
            exceptions_ref=f"{code_name} Section Exemptions",
            defines_terms=["Covered Unit", "Disabled", "Catastrophically Ill", "Senior Citizen"],
        )
    ]

    pack_dict = PackScaffolder.create_california_municipal_pack(
        municipality=muni,
        county=args.county,
        municipal_code_name=code_name,
        edition=args.edition,
        publisher=args.publisher,
        effective_from=args.effective_from,
        omi_ownership_floor=args.omi_floor,
        omi_occupancy_months=args.omi_occupancy_months,
        filing_window_days=args.filing_window_days,
        custom_statutes=custom_statutes,
    )

    written_path = PackScaffolder.write_pack(pack_dict, output_path, overwrite=args.overwrite)
    print(f"✅ Successfully created and validated Authority Pack at: {written_path}")

    # Generate and print pytest snippet
    test_snippet = PackScaffolder.generate_slot_test_snippet(pack_dict, os.path.relpath(output_path))
    print("\n🧪 Generated Test Invariant Snippet (for tests/test_packs.py):")
    print("-" * 60)
    print(test_snippet)
    print("-" * 60)


if __name__ == "__main__":
    main()

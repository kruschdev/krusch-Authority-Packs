"""
Tests for PackBinder: entity extraction, registry resolution, refusal gating, join plan assembly.
"""

import os
import pytest
from src.binder import PackBinder, PackRegistry
from src.validator import RagPackValidator


@pytest.fixture
def binder():
    registry = PackRegistry()
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "packs")
    import glob
    for p in glob.glob(os.path.join(packs_dir, "**", "*.yaml"), recursive=True):
        pack = RagPackValidator.load(p)
        registry.register(pack.raw_dict)
    return PackBinder(registry)


def test_in_scope_oakland_binding(binder):
    res = binder.bind("What are the landlord owner move in rules in Oakland, CA?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_oakland_pack_v1"
    assert "ca_oakland_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_in_scope_berkeley_binding(binder):
    res = binder.bind("Under the Berkeley Municipal Code, what are the owner move in eviction rules?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_berkeley_pack_v1"
    assert "ca_berkeley_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_in_scope_santa_monica_binding(binder):
    res = binder.bind("Under Santa Monica Rent Control, what is the owner move in ownership floor?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_santa_monica_pack_v1"
    assert "ca_santa_monica_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_in_scope_san_jose_binding(binder):
    res = binder.bind("What are the San Jose Tenant Protection Ordinance just cause eviction rules?")
    assert res.status == "BOUND"
    assert res.primary_pack_id == "ca_san_jose_pack_v1"
    assert "ca_san_jose_pack_v1" in res.join_plan[0]
    assert any("HARMONIZED_FLOOR" in j for j in res.join_plan)


def test_cross_city_trap_refusal(binder):
    # Mentioning two conflicting cities must trigger REFUSED_AMBIGUOUS
    res = binder.bind("Can an owner move-in in Los Angeles use the 36-month San Francisco rule?")
    assert res.status == "REFUSED_AMBIGUOUS"
    assert "Ambiguous jurisdiction" in res.refusal_reason


def test_missing_jurisdiction_refusal(binder):
    # Asking a tenancy question without specifying city must trigger REFUSED_AMBIGUOUS
    res = binder.bind("Can my landlord evict me without notice for a material breach?")
    assert res.status == "REFUSED_AMBIGUOUS"
    assert "Tenancy inquiry detected without governing municipality" in res.refusal_reason


def test_out_of_coverage_refusal(binder):
    # Asking about commercial lease in Oakland must fail closed based on known_uncovered_topics
    res = binder.bind("How do I evict a commercial lease tenant in Oakland?")
    assert res.status == "REFUSED_OUT_OF_SCOPE"
    assert "explicitly excluded" in res.refusal_reason


def test_as_of_historical_date_refusal(binder):
    # Asking for a 2022 legal opinion on a 2024 pack must fail closed
    res = binder.bind("What was the security deposit cap in Oakland as of 2022-01-01?", context={"as_of_date": "2022-01-01"})
    assert res.status == "REFUSED_STALE_OR_PRE_EFFECTIVE"
    assert "predates pack effective date" in res.refusal_reason


def test_system1_intent_and_routing_preserves_refusals(binder):
    # 1. Valid Oakland tenancy query routes with high confidence
    route_ok = binder.decide_pack_routing("What are the landlord owner move in rules in Oakland, CA?")
    assert route_ok["status"] == "BOUND"
    assert route_ok["confident_route"] is True
    assert route_ok["intent"] == "TENANCY"
    assert route_ok["confidence"] >= 0.85
    assert route_ok["primary_pack_id"] == "ca_oakland_pack_v1"

    # 2. Cross-city query is still strictly refused even with TENANCY intent
    route_ambig = binder.decide_pack_routing("Can an owner move-in in Los Angeles use the 36-month San Francisco rule?")
    assert route_ambig["status"] == "REFUSED_AMBIGUOUS"
    assert route_ambig["confident_route"] is False
    assert route_ambig["intent"] == "TENANCY"

    # 3. Financial accounting query classifies as FINANCIAL_ACCOUNTING
    intent_fin = binder.classify_query_intent("How are performance obligations recognized under ASC 606?")
    assert intent_fin["choice"] == "FINANCIAL_ACCOUNTING"
    assert intent_fin["confidence"] >= 0.85


def test_cross_domain_binding_and_intent(binder):
    # 1. Criminal defense query binds to ca_criminal_defense_pack_v1
    bind_crim = binder.bind("Can evidence from a warrantless search be suppressed under Penal Code 1538.5?")
    assert bind_crim.status == "BOUND"
    assert bind_crim.primary_pack_id == "ca_criminal_defense_pack_v1"
    intent_crim = binder.classify_query_intent("Penal Code 1538.5 suppression motion")
    assert intent_crim["choice"] == "CRIMINAL_DEFENSE"

    # 2. Commercial contracts query binds to ca_commercial_contracts_pack_v1
    bind_comm = binder.bind("Are non-compete agreements void under California Business and Professions Code 16600?")
    assert bind_comm.status == "BOUND"
    assert bind_comm.primary_pack_id == "ca_commercial_contracts_pack_v1"
    intent_comm = binder.classify_query_intent("Non-compete clause in business sale agreement under 16600")
    assert intent_comm["choice"] == "COMMERCIAL_CONTRACTS"

    # 3. Employment law query binds to ca_employment_labor_pack_v1
    bind_emp = binder.bind("What are the statutory penalties under Labor Code 226 for inaccurate paystub wage statements?")
    assert bind_emp.status == "BOUND"
    assert bind_emp.primary_pack_id == "ca_employment_labor_pack_v1"
    intent_emp = binder.classify_query_intent("Labor Code 226 itemized wage statement violation")
    assert intent_emp["choice"] == "EMPLOYMENT_LABOR"

    # 4. Intellectual property query binds to ca_intellectual_property_pack_v1
    bind_ip = binder.bind("What are the pre-discovery trade secret identification rules under CCP 2019.210 and CUTSA 3426?")
    assert bind_ip.status == "BOUND"
    assert bind_ip.primary_pack_id == "ca_intellectual_property_pack_v1"
    intent_ip = binder.classify_query_intent("CUTSA trade secret misappropriation under 3426 and invention assignment 2870")
    assert intent_ip["choice"] == "INTELLECTUAL_PROPERTY"

    # 5. Consumer privacy query binds to ca_consumer_privacy_pack_v1
    bind_priv = binder.bind("Can a consumer request personal information deletion under CCPA CPRA 1798.100 and CLRA 1750?")
    assert bind_priv.status == "BOUND"
    assert bind_priv.primary_pack_id == "ca_consumer_privacy_pack_v1"
    intent_priv = binder.classify_query_intent("CCPA opt-out of sale or sharing under 1798.120 and ARL 17602")
    assert intent_priv["choice"] == "CONSUMER_PRIVACY"

    # 6. Tort & civil liability query binds to ca_tort_liability_pack_v1
    bind_tort = binder.bind("What is the Proposition 51 several liability rule for non-economic damages under 1431.2 and Rowland v. Christian?")
    assert bind_tort.status == "BOUND"
    assert bind_tort.primary_pack_id == "ca_tort_liability_pack_v1"
    intent_tort = binder.classify_query_intent("Government Claims Act 911.2 presentation and punitive damages 3294")
    assert intent_tort["choice"] == "TORT_LIABILITY"

    # 7. Corporate governance & securities query binds to ca_corporate_governance_pack_v1
    bind_corp = binder.bind("Does Corporations Code 2115 apply to quasi-California corporations and shareholder inspection under 1601?")
    assert bind_corp.status == "BOUND"
    assert bind_corp.primary_pack_id == "ca_corporate_governance_pack_v1"
    intent_corp = binder.classify_query_intent("RULLCA LLC fiduciary duties 17704.09 and securities rescission 25501")
    assert intent_corp["choice"] == "CORPORATE_GOVERNANCE"





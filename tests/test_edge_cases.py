"""Comprehensive edge cases and boundary condition test suite for CRE Underwriting Swarm."""

from datetime import date, datetime, timezone

import pytest

from autonomous_cre_underwriting.agents.base import BaseAgent
from autonomous_cre_underwriting.agents.specialized import DCFValuationEngineerAgent
from autonomous_cre_underwriting.engine.dcf import (
    DCFEngine,
    compute_irr,
    compute_npv,
    compute_remaining_loan_balance,
    generate_loan_amortization_schedule,
)
from autonomous_cre_underwriting.engine.event_bus import InMemoryEventBus
from autonomous_cre_underwriting.engine.graph import KnowledgeGraphEngine
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.engine.rag import HybridRAGEngine, chunk_text
from autonomous_cre_underwriting.engine.risk import RiskSynthesisEngine
from autonomous_cre_underwriting.mcp.municipal_deed import DeedIngestor, MunicipalDeedMCPServer
from autonomous_cre_underwriting.mcp.protocol import MCPRequest
from autonomous_cre_underwriting.mcp.sec_edgar import SECEdgarMCPServer, SECIngestor
from autonomous_cre_underwriting.portfolio.engine import PortfolioUnderwriter
from autonomous_cre_underwriting.reporting.audit import AuditTrailVerifier
from autonomous_cre_underwriting.storage.repository import DealRepository
from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)
from autonomous_cre_underwriting.types.events import (
    EventPriority,
    EventType,
    SwarmEvent,
)
from autonomous_cre_underwriting.types.financial import (
    DCFParameters,
    FinancingAssumptions,
)
from autonomous_cre_underwriting.types.ingestion import (
    SECFiling,
    SECFilingType,
    SECRiskMention,
    SECRiskTopic,
)
from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
)
from autonomous_cre_underwriting.types.property import (
    PropertyPhysical,
    UnitMix,
)
from autonomous_cre_underwriting.types.risk import (
    ChecklistStatus,
    MemoRecommendation,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)

# =========================================================================
# 1. DCF Engine Boundary & Mathematical Edge Cases
# =========================================================================


def test_dcf_irr_edge_cases_and_solver_divergence():
    """Verify IRR solver robustness against extreme, degenerate, or divergent cash flows."""
    # Degenerate cash flows: all negative
    assert compute_irr([-1000.0, -200.0, -100.0]) == 0.0

    # All zero cash flows
    assert compute_irr([0.0, 0.0, 0.0, 0.0]) == 0.0

    # Extremely high return
    high_irr = compute_irr([-100.0, 1000.0])
    assert high_irr > 5.0

    # Alternating erratic signs leading to polynomial root fallback
    erratic_cfs = [-1000000.0, 200000.0, -50000.0, 300000.0, -40000.0, 1500000.0]
    irr_val = compute_irr(erratic_cfs)
    assert -0.99 <= irr_val <= 10.0

    # Compute NPV with zero and high discount rate
    assert compute_npv(0.0, [-100.0, 50.0, 60.0]) == 10.0
    assert compute_npv(1.0, [-100.0, 200.0]) == 0.0


def test_loan_amortization_boundary_conditions():
    """Test debt schedule behavior with 0% interest, 0 loan amount, and accelerated payoff."""
    # Zero loan amount returns empty schedule
    zero_loan = FinancingAssumptions(loan_amount=0.0, interest_rate=0.05)
    assert generate_loan_amortization_schedule(zero_loan) == []
    assert compute_remaining_loan_balance(zero_loan, year=5) == 0.0
    assert compute_remaining_loan_balance(zero_loan, year=0) == 0.0

    # Zero interest rate (pure principal amortization)
    zero_rate_loan = FinancingAssumptions(
        loan_amount=120000.0,
        interest_rate=0.0,
        term_years=10,
        amortization_years=10,
        interest_only_years=0,
    )
    sched = generate_loan_amortization_schedule(zero_rate_loan)
    assert len(sched) == 120
    assert sched[0].interest == 0.0
    assert sched[0].principal == 1000.0
    assert sched[-1].ending_balance == 0.0

    # Remaining balance at 0% rate
    rem_bal_5y = compute_remaining_loan_balance(zero_rate_loan, year=5)
    assert rem_bal_5y == 60000.0

    # Remaining balance at year <= 0
    rem_bal_0y = compute_remaining_loan_balance(zero_rate_loan, year=0)
    assert rem_bal_0y == 120000.0

    # Remaining balance when elapsed time exceeds amortization period
    rem_bal_past = compute_remaining_loan_balance(zero_rate_loan, year=15)
    assert rem_bal_past == 0.0

    # Balloon payment scenario: short term loan with longer amortization
    balloon_loan = FinancingAssumptions(
        loan_amount=1000000.0,
        interest_rate=0.06,
        term_years=3,
        amortization_years=30,
        interest_only_years=0,
    )
    b_sched = generate_loan_amortization_schedule(balloon_loan)
    assert len(b_sched) == 36
    assert b_sched[-1].ending_balance > 900000.0


def test_dcf_valuation_without_financial_statements(sample_deal):
    """Verify DCFEngine falls back to unit mix rents when no T12 or historicals exist."""
    bare_deal = sample_deal.model_copy(
        update={
            "t12_financials": None,
            "historical_financials": [],
        }
    )
    engine = DCFEngine()
    params = DCFParameters(holding_period_years=5, exit_cap_rate=0.055)
    financing = FinancingAssumptions(loan_amount=10000000.0, interest_rate=0.06)

    val_res = engine.compute_valuation(bare_deal, parameters=params, financing=financing)
    assert val_res.metrics.unlevered_irr > 0.0
    assert len(val_res.annual_cash_flows) == 5
    assert val_res.annual_cash_flows[0].potential_gross_revenue > 0.0


def test_dcf_valuation_with_empty_unit_mix(sample_deal):
    """Verify DCFEngine handles deal with 0 unit mix using asking price heuristic."""
    empty_mix_deal = sample_deal.model_copy(
        update={
            "unit_mix": UnitMix.model_construct(items=[]),
            "t12_financials": None,
            "historical_financials": [],
        }
    )
    engine = DCFEngine()
    params = DCFParameters(holding_period_years=3, exit_cap_rate=0.06)
    financing = FinancingAssumptions(loan_amount=2000000.0, interest_rate=0.065)

    res = engine.compute_valuation(empty_mix_deal, parameters=params, financing=financing)
    assert len(res.annual_cash_flows) == 3
    assert res.metrics.net_present_value != 0.0


# =========================================================================
# 2. Domain Models Zero-Division & Boundary Protections
# =========================================================================


def test_property_model_zero_division_guards(sample_deal):
    """Test all defensive division-by-zero guards on PropertyDeal and UnitMix."""
    zero_mix = UnitMix.model_construct(items=[])
    assert zero_mix.total_units == 0
    assert zero_mix.total_vacant_units == 0
    assert zero_mix.physical_occupancy_rate == 0.0
    assert zero_mix.total_rentable_sqft == 0.0
    assert zero_mix.total_in_place_monthly_rent == 0.0
    assert zero_mix.weighted_average_rent_psf == 0.0

    # Zero-priced and zero sqft deal
    zero_deal = sample_deal.model_copy(
        update={
            "unit_mix": zero_mix,
            "asking_price": 0.0,
            "target_purchase_price": 0.0,
            "physical": PropertyPhysical.model_construct(
                gross_square_feet=0.0,
                rentable_square_feet=0.0,
                year_built=2020,
                site_area_acres=0.0,
            ),
        }
    )

    assert zero_deal.asking_cap_rate == 0.0
    assert zero_deal.target_cap_rate == 0.0
    assert zero_deal.in_place_cap_rate == 0.0
    assert zero_deal.price_per_unit == 0.0
    assert zero_deal.price_per_sqft == 0.0


# =========================================================================
# 3. Knowledge Graph Engine Edge Cases
# =========================================================================


def test_knowledge_graph_missing_nodes_and_disjoint_paths():
    """Verify graph query defenses when querying non-existent entities or disconnected paths."""
    kg_engine = KnowledgeGraphEngine()

    # Querying nonexistent deal
    chain, continuous = kg_engine.trace_chain_of_title("NONEXISTENT-DEAL")
    assert chain == []
    assert continuous is False

    encs, total_enc = kg_engine.detect_encumbrances_and_liens("NONEXISTENT-DEAL")
    assert encs == []
    assert total_enc == 0.0

    # Sponsor portfolio for unknown sponsor
    sponsor_deals = kg_engine.find_sponsor_portfolio("Ghost Sponsor LLC")
    assert sponsor_deals == []

    # Shortest path between non-existent nodes
    assert kg_engine.find_shortest_path("E-NONE-1", "E-NONE-2") is None

    # Disconnected components
    e1 = GraphEntity(entity_id="E-DISC-1", label="Isolated Parcel", entity_type=EntityType.PARCEL)
    e2 = GraphEntity(
        entity_id="E-DISC-2", label="Distant Guarantor", entity_type=EntityType.GUARANTOR
    )
    kg_engine.upsert_entity(e1)
    kg_engine.upsert_entity(e2)

    path = kg_engine.find_shortest_path("E-DISC-1", "E-DISC-2")
    assert path is None

    # Subgraph for unknown deal returns empty graph
    empty_subgraph = kg_engine.get_graph_for_deal("UNKNOWN-DEAL")
    assert len(empty_subgraph.entities) == 0


# =========================================================================
# 4. Hybrid RAG Engine Edge Cases
# =========================================================================


def test_hybrid_rag_empty_and_unmatched_queries(sample_offering_memorandum):
    """Verify RAG engine handles empty indices, stopword-only queries, and zero matches gracefully."""
    rag = HybridRAGEngine()

    # Querying empty RAG index
    empty_results = rag.hybrid_search(
        "commercial real estate cap rate", deal_id="empty-deal", top_k=5
    )
    assert empty_results == []

    # Text chunking with empty text
    empty_chunks = chunk_text("", document_id="doc-empty")
    assert empty_chunks == []

    # Add offering memorandum fixture
    indexed_count = rag.index_document(sample_offering_memorandum)
    assert indexed_count >= 1

    # Query with completely unrelated required keyword
    filtered_out = rag.hybrid_search(
        "Austin multifamily",
        deal_id=sample_offering_memorandum.deal_id,
        required_keywords=["spacecraft"],
    )
    assert len(filtered_out) >= 1  # Fallback to all candidates when required keywords match nothing

    # Query with matching terms
    matched = rag.hybrid_search(
        "Austin multifamily units", deal_id=sample_offering_memorandum.deal_id, top_k=3
    )
    assert len(matched) >= 1


# =========================================================================
# 5. Event Bus Edge Cases
# =========================================================================


def test_event_bus_isolated_exceptions_and_unsubscribing():
    """Verify event bus survives subscriber exceptions and allows cleanly removing listeners."""
    bus = InMemoryEventBus()
    handled_events = []

    def faulty_listener(event: SwarmEvent) -> None:
        raise RuntimeError("Subscriber explosion!")

    def reliable_listener(event: SwarmEvent) -> None:
        handled_events.append(event.event_id)

    bus.subscribe(EventType.MUNICIPAL_DEED_INGESTED.value, faulty_listener)
    bus.subscribe(EventType.MUNICIPAL_DEED_INGESTED.value, reliable_listener)

    event = SwarmEvent(
        event_type=EventType.MUNICIPAL_DEED_INGESTED,
        deal_id="DEAL-BUS",
        source_role="test",
        priority=EventPriority.NORMAL,
    )

    # Publishing does not raise RuntimeError; reliable_listener still runs
    bus.publish(event)
    assert len(handled_events) == 1
    assert len(bus.get_dead_letters()) == 1
    assert "Subscriber explosion!" in bus.get_dead_letters()[0].error_message

    # Unsubscribe listener
    bus.unsubscribe(EventType.MUNICIPAL_DEED_INGESTED.value, reliable_listener)
    event_2 = SwarmEvent(
        event_type=EventType.MUNICIPAL_DEED_INGESTED,
        deal_id="DEAL-BUS",
        source_role="test",
        priority=EventPriority.NORMAL,
    )
    bus.publish(event_2)
    assert len(handled_events) == 1  # Not called again

    # Unsubscribe non-existent listener does not crash
    bus.unsubscribe(EventType.MUNICIPAL_DEED_INGESTED.value, reliable_listener)

    # History filtering
    for _ in range(10):
        bus.publish(
            SwarmEvent(
                event_type=EventType.SEC_FILING_INGESTED,
                deal_id="DEAL-BUS",
                source_role="test",
                priority=EventPriority.LOW,
            )
        )
    assert len(bus.get_history(limit=5)) == 5
    assert len(bus.get_history(event_type=EventType.SEC_FILING_INGESTED.value)) == 10

    bus.clear()
    assert len(bus.get_history()) == 0
    assert len(bus.get_dead_letters()) == 0


# =========================================================================
# 6. Risk Engine & Audit Trail Verifier Edge Cases
# =========================================================================


def test_risk_synthesis_debt_yield_and_compliance_thresholds(sample_deal, sample_dcf_result):
    """Test boundary checks for debt yield (fail <6.5%, review 6.5-8.0%) and title defects."""
    risk_engine = RiskSynthesisEngine()

    # Modify year 1 cash flow to produce debt yield between 6.5% and 8.0%
    mid_dy_dcf = sample_dcf_result.model_copy(deep=True)
    mid_dy_dcf.annual_cash_flows[0].debt_yield = 0.073

    checklist = risk_engine.evaluate_covenant_compliance(
        sample_deal, mid_dy_dcf.financing, mid_dy_dcf
    )
    dy_item = next(c for c in checklist if "Debt Yield" in c.requirement)
    assert dy_item.status == ChecklistStatus.REQUIRES_REVIEW

    # Low debt yield (< 6.5%)
    low_dy_dcf = sample_dcf_result.model_copy(deep=True)
    low_dy_dcf.annual_cash_flows[0].debt_yield = 0.050
    low_checklist = risk_engine.evaluate_covenant_compliance(
        sample_deal, low_dy_dcf.financing, low_dy_dcf
    )
    low_dy_item = next(c for c in low_checklist if "Debt Yield" in c.requirement)
    assert low_dy_item.status == ChecklistStatus.FAIL

    # Standard checklist with gap in chain of title
    title_fail_checklist = risk_engine.build_standard_checklist(
        sample_deal, title_continuous=False, active_liens=0.0
    )
    title_item = next(c for c in title_fail_checklist if "chain of title" in c.requirement.lower())
    assert title_item.status == ChecklistStatus.FAIL

    # Standard checklist with active liens
    liens_checklist = risk_engine.build_standard_checklist(
        sample_deal, title_continuous=True, active_liens=150000.0
    )
    liens_item = next(c for c in liens_checklist if "chain of title" in c.requirement.lower())
    assert liens_item.status == ChecklistStatus.REQUIRES_REVIEW

    # Build memo with failed checklist -> REJECT recommendation
    memo_rej = risk_engine.build_memo(
        deal=sample_deal,
        dcf_result=sample_dcf_result,
        risk_findings=[],
        diligence_checklist=title_fail_checklist,
        stress_scenarios=[],
    )
    assert memo_rej.recommendation == MemoRecommendation.REJECT

    # Build memo with high risks with and without proposed mitigation
    high_findings = [
        RiskFinding(
            finding_id="RISK-MIT-1",
            category=RiskCategory.PHYSICAL_ENVIRONMENTAL,
            severity=RiskSeverity.HIGH,
            title="Underground Storage Tank Phase II",
            description="Phase I ESA revealed suspected historical underground fuel storage tank on adjacent parcel.",
            evidence_citation="Phase I Environmental Site Assessment p. 42",
            impact_summary="Historical tank suspected on adjacent parcel.",
            proposed_mitigation="Obtain baseline Phase II soil vapor study before closing.",
            confirmed_by_role=AgentRole.CREDIT_RISK_UNDERWRITER,
        ),
        RiskFinding(
            finding_id="RISK-MIT-2",
            category=RiskCategory.TITLE_AND_LEGAL,
            severity=RiskSeverity.HIGH,
            title="Parking Ratio Non-Conformity",
            description="Municipal zoning code requires 1.5 stalls per unit but property has 1.3 stalls.",
            evidence_citation="City Land Development Code Sec 25-6",
            impact_summary="Parking spaces below current code by 8 stalls.",
            proposed_mitigation=None,
            confirmed_by_role=AgentRole.CREDIT_RISK_UNDERWRITER,
        ),
    ]
    memo_cond = risk_engine.build_memo(
        deal=sample_deal,
        dcf_result=sample_dcf_result,
        risk_findings=high_findings,
        diligence_checklist=[],
        stress_scenarios=[],
    )
    # Check that conditions precedent contain both formatted mitigations
    cp_text = " ".join(memo_cond.conditions_precedent)
    assert "Mitigate Underground Storage Tank Phase II" in cp_text
    assert "Satisfactory resolution of Parking Ratio Non-Conformity" in cp_text


def test_audit_trail_verifier_corruptions_and_ordering():
    """Verify AuditTrailVerifier detects hash tampering, invalid format, and chronological inversions."""
    verifier = AuditTrailVerifier()

    # Valid audit entry
    task = AgentTask(
        id="task-001",
        deal_id="DEAL-AUDIT",
        role=AgentRole.DCF_VALUATION_ENGINEER,
        description="Run valuation",
    )
    valid_hash = verifier.compute_input_hash(
        task_id=task.id, deal_id=task.deal_id, role=task.role.value, inputs=task.input_artifacts
    )
    valid_entry = AgentAuditEntry(
        entry_id="entry-001",
        task_id=task.id,
        role=task.role,
        action_taken="DCF_RUN",
        justification="Executed DCF pro-forma",
        input_hash=valid_hash,
        output_summary="DCF pro-forma completed successfully",
        timestamp=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    assert verifier.verify_entry(valid_entry, expected_task=task) is True

    # Bad prefix in hash
    bad_prefix_entry = valid_entry.model_copy(update={"input_hash": "md5:123456"})
    assert verifier.verify_entry(bad_prefix_entry) is False

    # Bad length in sha256
    short_hash_entry = valid_entry.model_copy(update={"input_hash": "sha256:abc"})
    assert verifier.verify_entry(short_hash_entry) is False

    # Missing action
    no_action_entry = valid_entry.model_copy(update={"action_taken": ""})
    assert verifier.verify_entry(no_action_entry) is False

    # Missing justification
    no_just_entry = valid_entry.model_copy(update={"justification": ""})
    assert verifier.verify_entry(no_just_entry) is False

    # Workflow with reversed chronological timestamps and invalid entry
    entry_early = valid_entry.model_copy(
        update={
            "entry_id": "e-1",
            "timestamp": datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        }
    )
    entry_late = valid_entry.model_copy(
        update={
            "entry_id": "e-2",
            "timestamp": datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        }
    )
    wf_inverted = SwarmWorkflowState(
        id="wf-inverted",
        deal_id="DEAL-AUDIT",
        tasks=[task],
        audit_trail=[entry_early, entry_late, bad_prefix_entry],
        is_terminal=True,
    )
    report = verifier.verify_workflow(wf_inverted)
    assert report["chronological"] is False
    assert report["audit_valid"] is False
    assert bad_prefix_entry.entry_id in report["invalid_entry_ids"]


# =========================================================================
# 7. MCP Servers Protocol & Ingestor Edge Cases
# =========================================================================


def test_sec_edgar_ingestor_and_server_edge_cases():
    """Test SEC ingestor credit assessment across severity tiers and MCP tool invocation."""
    critical_mention = SECRiskMention(
        topic=SECRiskTopic.REFINANCING_RISK,
        excerpt="Substantial debt default impending on floating debt notes.",
        item_section="Item 1A. Risk Factors",
        severity_score=0.90,
        relevance_score=0.95,
    )
    moderate_mention = SECRiskMention(
        topic=SECRiskTopic.TENANT_CONCENTRATION,
        excerpt="Tenant concentration moderate in commercial assets.",
        item_section="Item 1A. Risk Factors",
        severity_score=0.50,
        relevance_score=0.80,
    )
    filing_crit = SECFiling(
        accession_number="0001000-26-0001",
        cik="0001000",
        company_name="Distressed REIT",
        form_type=SECFilingType.FORM_10K,
        filing_date=date(2026, 1, 1),
        report_url="https://sec.gov/1",
        risk_mentions=[critical_mention],
    )
    filing_mod = SECFiling(
        accession_number="0002000-26-0001",
        cik="0002000",
        company_name="Stable REIT",
        form_type=SECFilingType.FORM_10Q,
        filing_date=date(2026, 2, 1),
        report_url="https://sec.gov/2",
        risk_mentions=[moderate_mention],
    )
    filing_clean = SECFiling(
        accession_number="0003000-26-0001",
        cik="0003000",
        company_name="Clean REIT",
        form_type=SECFilingType.FORM_8K,
        filing_date=date(2026, 3, 1),
        report_url="https://sec.gov/3",
        risk_mentions=[],
    )

    ingestor = SECIngestor(seed_filings=[filing_crit, filing_mod, filing_clean])

    # Assess CRITICAL level (severity >= 0.85)
    crit_assess = ingestor.assess_sponsor_credit("0001000")
    assert crit_assess["credit_risk_level"] == "CRITICAL"

    # Assess MODERATE level
    mod_assess = ingestor.assess_sponsor_credit("0002000")
    assert mod_assess["credit_risk_level"] == "MODERATE"

    # Assess LOW level (no mentions)
    low_assess = ingestor.assess_sponsor_credit("0003000")
    assert low_assess["credit_risk_level"] == "LOW"

    # Assess non-existent sponsor
    none_assess = ingestor.assess_sponsor_credit("9999999")
    assert none_assess["credit_risk_level"] == "UNKNOWN"
    assert none_assess["found_filings"] == 0

    # Extract risk factors with partial accession match vs not found
    factors_found = ingestor.extract_risk_factors("0001000")
    assert len(factors_found) == 1
    factors_none = ingestor.extract_risk_factors("NONEXISTENT-ACCESSION")
    assert factors_none == []

    # MCP Server tool invocations
    server = SECEdgarMCPServer(ingestor=ingestor)
    search_res = server.call_tool("sec_edgar_search", {"cik_or_ticker": "0001000"})
    assert len(search_res["filings"]) == 1

    rf_res = server.call_tool("sec_edgar_risk_factors", {"accession_number": "0001000-26-0001"})
    assert len(rf_res["risk_factors"]) == 1

    assess_tool_res = server.call_tool("sec_edgar_assess_sponsor", {"cik_or_ticker": "0001000"})
    assert assess_tool_res["credit_risk_level"] == "CRITICAL"

    # JSON-RPC handle_request ping and invalid tool
    ping_resp = server.handle_request(MCPRequest(method="ping", params={}))
    assert ping_resp.result["status"] == "ok"

    bad_resp = server.handle_request(
        MCPRequest(method="tools/call", params={"name": "nonexistent_tool"})
    )
    assert bad_resp.error is not None


def test_municipal_deed_server_edge_cases():
    """Test MunicipalDeedMCPServer error handling and tool calls."""
    ingestor = DeedIngestor()
    server = MunicipalDeedMCPServer(ingestor=ingestor)

    # Empty recorder query
    fetch_res = server.call_tool(
        "municipal_deed_fetch", {"apn": "99-9999", "county": "Travis", "state": "TX"}
    )
    assert len(fetch_res["records"]) == 0

    # Tool execution via handle_request
    req = MCPRequest(
        method="tools/call",
        params={
            "name": "municipal_deed_verify_chain",
            "arguments": {"apn": "99-9999", "reported_seller": "Acme"},
        },
    )
    resp = server.handle_request(req)
    assert resp.result["verified"] is False


# =========================================================================
# 8. Portfolio Underwriter Edge Cases
# =========================================================================


def test_portfolio_underwriter_empty_and_zero_debt(sample_deal, sample_dcf_result):
    """Verify PortfolioUnderwriter handles empty sets, zero debt, and missing deals cleanly."""
    portfolio = PortfolioUnderwriter()

    # Empty summary
    summary = portfolio.compute_portfolio_summary()
    assert summary.property_count == 0
    assert summary.total_purchase_price == 0.0
    assert summary.portfolio_ltv == 0.0
    assert summary.weighted_avg_dscr == 0.0

    # Empty concentration
    conc = portfolio.compute_concentration()
    assert conc.top_asset_concentration_pct == 0.0
    assert conc.by_property_type == {}

    # Empty stress test
    stress_res = portfolio.stress_portfolio("Global Recession")
    assert stress_res.base_noi == 0.0
    assert stress_res.covenant_breaches_count == 0

    # Removing non-existent deal
    assert portfolio.remove_deal("NON-EXISTENT") is False

    # Add all-cash deal (zero debt via DCF result with loan_amount = 0)
    zero_debt_dcf = sample_dcf_result.model_copy(deep=True)
    zero_debt_dcf.financing.loan_amount = 0.0
    zero_debt_dcf.metrics.average_dscr = 0.0
    zero_debt_dcf.metrics.equity_invested = sample_deal.target_purchase_price

    portfolio.add_deal(sample_deal, dcf_result=zero_debt_dcf)
    summary_cash = portfolio.compute_portfolio_summary()
    assert summary_cash.total_debt == 0.0
    assert summary_cash.portfolio_debt_yield == 0.0
    assert summary_cash.weighted_avg_dscr == 0.0
    assert summary_cash.portfolio_ltv == 0.0


# =========================================================================
# 9. Storage Repository Filtering & Fault Tolerance
# =========================================================================


def test_repository_advanced_filtering_and_faulty_files(tmp_path, sample_deal):
    """Test DealRepository query filters, export validation, and resilient import over corrupt JSON."""
    repo = DealRepository()
    repo.save_deal(sample_deal)

    # Filter matching status and property type
    matches = repo.query_deals(
        status=sample_deal.status,
        property_type=sample_deal.property_type,
        min_price=10000000.0,
        max_price=30000000.0,
        sponsor="Apex",
    )
    assert len(matches) == 1

    # Filter with non-matching sponsor
    no_matches = repo.query_deals(sponsor="NonExistentSponsor")
    assert len(no_matches) == 0

    # Filter with out-of-range price
    price_no_match = repo.query_deals(min_price=50000000.0)
    assert len(price_no_match) == 0

    # Export to None raises ValueError
    with pytest.raises(ValueError, match="Target directory must be provided"):
        repo.export_to_directory(None)

    # Import from non-existent directory returns 0
    assert repo.import_from_directory(str(tmp_path / "does_not_exist")) == 0

    # Create directory with invalid/corrupt JSON files in all subdirectories
    export_dir = tmp_path / "persistence_test"
    repo.export_to_directory(str(export_dir))

    # Plant corrupt JSON files
    (export_dir / "deals" / "corrupt_deal.json").write_text("{corrupt json", encoding="utf-8")
    (export_dir / "memos" / "corrupt_memo.json").write_text("not json at all", encoding="utf-8")
    (export_dir / "workflows" / "corrupt_wf.json").write_text("{}", encoding="utf-8")
    (export_dir / "valuations" / "corrupt_val.json").write_text("{broken", encoding="utf-8")

    new_repo = DealRepository(persistence_dir=str(export_dir))
    imported_count = new_repo.import_from_directory()
    assert (
        imported_count >= 1
    )  # Valid deal imported, corrupt files skipped without throwing exception

    # Workflow retrieval
    assert new_repo.get_workflow("unknown-wf") is None
    assert new_repo.get_workflow_for_deal("unknown-deal") is None


# =========================================================================
# 10. Specialized Agents & Swarm Orchestrator Edge Scenarios
# =========================================================================


def test_specialized_agent_missing_deal_artifact():
    """Verify DCFValuationEngineerAgent creates fallback deal if 'deal' missing from artifacts."""
    agent = DCFValuationEngineerAgent()
    task = AgentTask(
        id="task-no-deal",
        deal_id="DEAL-STANDALONE",
        role=AgentRole.DCF_VALUATION_ENGINEER,
        description="Valuation with no deal artifact",
        input_artifacts={"purchase_price": 12000000.0, "in_place_noi": 750000.0},
    )
    workflow_state = SwarmWorkflowState(
        id="wf-standalone",
        deal_id="DEAL-STANDALONE",
        tasks=[task],
    )
    completed_task = agent.execute_task(task, workflow_state)
    assert completed_task.status == TaskStatus.COMPLETED
    assert "valuation_result" in completed_task.output_artifacts


def test_orchestrator_edge_and_error_handling(sample_deal):
    """Verify SwarmOrchestrator error resilience on invalid IDs, failed tasks, and direct memo generation."""
    orch = SwarmOrchestrator()

    # Invalid workflow advance
    with pytest.raises(KeyError, match="Workflow unknown-wf not found"):
        orch.advance_workflow("unknown-wf")

    # Invalid deal memo generation
    with pytest.raises(KeyError, match="not found in orchestrator registry"):
        orch.generate_underwriting_memo("unknown-deal")

    # Direct memo generation passing deal directly
    direct_memo = orch.generate_underwriting_memo("direct-deal-id", deal=sample_deal)
    assert direct_memo.deal_id == sample_deal.id
    assert direct_memo.valuation_summary.unlevered_irr > 0.0

    # Advance workflow with empty tasks list immediately marks terminal
    state_empty = orch.initialize_workflow(sample_deal)
    state_empty.tasks = []
    assert orch.advance_workflow(state_empty.id).is_terminal is True

    # Advance already-terminal workflow returns state immediately
    state = orch.initialize_workflow(sample_deal)
    state.is_terminal = True
    assert orch.advance_workflow(state.id).is_terminal is True

    # Workflow where memo is already cached before reaching terminal
    orch_cached = SwarmOrchestrator()
    st_cached = orch_cached.initialize_workflow(sample_deal)
    pre_memo = orch_cached.generate_underwriting_memo(sample_deal.id, deal=sample_deal)
    while not st_cached.is_terminal:
        st_cached = orch_cached.advance_workflow(st_cached.id)
    assert st_cached.final_memo_id == pre_memo.id

    # Workflow with a custom agent that raises an Exception
    class FailingAgent(BaseAgent):
        def __init__(self):
            super().__init__(AgentRole.INGESTION_COORDINATOR)

        def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
            raise RuntimeError("Synthetic ingestion pipeline failure")

    orch_fail = SwarmOrchestrator()
    orch_fail.register_agent(FailingAgent())

    failing_state = orch_fail.initialize_workflow(sample_deal)
    # Advance first task (INGESTION_COORDINATOR)
    updated_state = orch_fail.advance_workflow(failing_state.id)
    failed_task = updated_state.tasks[0]
    assert failed_task.status == TaskStatus.FAILED
    assert "Synthetic ingestion pipeline failure" in (failed_task.error_message or "")


def test_orchestrator_built_in_roles_execution(sample_deal):
    """Verify SwarmOrchestrator runs full DAG using built-in roles when no external agents registered."""
    orch = SwarmOrchestrator()

    state = orch.initialize_workflow(sample_deal)
    while not state.is_terminal:
        state = orch.advance_workflow(state.id)

    assert state.is_terminal is True
    assert all(t.status == TaskStatus.COMPLETED for t in state.tasks)
    assert state.deal_id in orch.memos
    assert orch.memos[state.deal_id].id == state.final_memo_id

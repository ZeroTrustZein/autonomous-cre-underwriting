"""Comprehensive test suite for Stage 4 subsystems: MCP, Agents, Portfolio, Reporting, and Storage."""

import json
from datetime import date

import pytest

from autonomous_cre_underwriting.agents import (
    BaseAgent,
    CreditRiskUnderwriterAgent,
    DCFValuationEngineerAgent,
    IngestionCoordinatorAgent,
    InvestmentCommitteeChairAgent,
    MunicipalDeedAuditorAgent,
    SECDiligenceAnalystAgent,
    create_agent_swarm,
)
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.mcp import (
    DeedIngestor,
    MCPRequest,
    MunicipalDeedMCPServer,
    SECEdgarMCPServer,
    SECIngestor,
)
from autonomous_cre_underwriting.portfolio import (
    PortfolioUnderwriter,
    UnderwritingRulesEngine,
)
from autonomous_cre_underwriting.reporting import (
    AuditTrailVerifier,
    DCFScheduleExporter,
    MemoExporter,
)
from autonomous_cre_underwriting.storage import DealRepository
from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)
from autonomous_cre_underwriting.types.ingestion import (
    DeedRecord,
    DeedType,
    SECRiskTopic,
)
from autonomous_cre_underwriting.types.property import DealStatus, PropertyDeal, PropertyType

# =========================================================================
# 1. MCP Subsystem Tests
# =========================================================================

def test_deed_ingestor_crud_and_query(sample_deed):
    """DeedIngestor records, sorts, and queries conveyance instruments."""
    ingestor = DeedIngestor()
    ingestor.add_record(sample_deed)

    # Fetch by APN and county
    records = ingestor.fetch_deed_records(
        apn="01-0203-0405-0000", county="Travis", state="tx"
    )
    assert len(records) == 1
    assert records[0].document_number == sample_deed.document_number

    # Non-existent APN returns empty list
    assert len(ingestor.fetch_deed_records("99-9999", "Travis", "tx")) == 0


def test_deed_ingestor_chain_verification_and_audit(sample_deed):
    """Chain of title verification with corporate suffix normalization and gap detection."""
    ingestor = DeedIngestor([sample_deed])

    # Seller verification with entity suffix matching (Apex Capital Partners LLC vs Apex Capital Partners)
    assert ingestor.verify_chain_of_title("01-0203-0405-0000", "Apex Capital Partners") is True
    assert ingestor.verify_chain_of_title("01-0203-0405-0000", "Apex Capital Partners LLC") is True
    assert ingestor.verify_chain_of_title("01-0203-0405-0000", "Unrelated Stranger LLC") is False
    assert ingestor.verify_chain_of_title("unknown-apn", "Apex Capital Partners") is False

    # Audit single deed chain
    audit = ingestor.audit_chain_of_title("01-0203-0405-0000")
    assert audit["chain_valid"] is True
    assert audit["records_count"] == 1
    assert audit["latest_owner"] == "Apex Capital Partners LLC"

    # Add second deed creating a break in title
    broken_deed = DeedRecord(
        parcel_number="01-0203-0405-0000",
        document_number="DOC-2024-0001",
        recording_date=date(2024, 1, 1),
        deed_type=DeedType.QUITCLAIM_DEED,
        grantor="Random Third Party Corp",  # does not match prior grantee Apex Capital
        grantee="Next Buyer LP",
        consideration_amount=25000000.0,
        legal_description="Lot 4, Block B",
        county_name="Travis",
    )
    ingestor.add_record(broken_deed)

    audit_broken = ingestor.audit_chain_of_title("01-0203-0405-0000")
    assert audit_broken["chain_valid"] is False
    assert len(audit_broken["issues"]) >= 2  # Gap issue + quitclaim issue


def test_municipal_deed_mcp_server(sample_deed):
    """MunicipalDeedMCPServer JSON-RPC dispatching."""
    ingestor = DeedIngestor([sample_deed])
    server = MunicipalDeedMCPServer(ingestor=ingestor)

    # 1. tools/list
    list_req = MCPRequest(method="tools/list")
    list_resp = server.handle_request(list_req)
    assert list_resp.error is None
    assert len(list_resp.result["tools"]) == 3

    # 2. tools/call: municipal_deed_fetch
    fetch_req = MCPRequest(
        method="tools/call",
        params={"name": "municipal_deed_fetch", "arguments": {"apn": "01-0203-0405-0000", "county": "Travis", "state": "tx"}},
    )
    fetch_resp = server.handle_request(fetch_req)
    assert fetch_resp.error is None
    assert len(fetch_resp.result["records"]) == 1

    # 3. tools/call: municipal_deed_verify_chain
    verify_req = MCPRequest(
        method="tools/call",
        params={"name": "municipal_deed_verify_chain", "arguments": {"apn": "01-0203-0405-0000", "reported_seller": "Apex Capital Partners"}},
    )
    verify_resp = server.handle_request(verify_req)
    assert verify_resp.error is None
    assert verify_resp.result["verified"] is True

    # 4. tools/call: municipal_deed_audit_chain
    audit_req = MCPRequest(
        method="tools/call",
        params={"name": "municipal_deed_audit_chain", "arguments": {"apn": "01-0203-0405-0000"}},
    )
    audit_resp = server.handle_request(audit_req)
    assert audit_resp.error is None
    assert audit_resp.result["chain_valid"] is True
    assert "issues" in audit_resp.result

    # 5. Unknown method
    err_req = MCPRequest(method="unsupported/method")
    err_resp = server.handle_request(err_req)
    assert err_resp.error is not None
    assert err_resp.error["code"] == -32601

    # 6. Ping
    ping_resp = server.handle_request(MCPRequest(method="ping"))
    assert ping_resp.result["status"] == "ok"


def test_sec_ingestor_and_server(sample_sec_filing):
    """SECIngestor normalization, search, credit risk evaluation, and MCP server dispatch."""
    ingestor = SECIngestor()
    ingestor.add_filing(sample_sec_filing)

    # CIK normalization
    assert SECIngestor.normalize_cik("1234567") == "0001234567"
    assert SECIngestor.normalize_cik("AAPL") == "AAPL"

    # Search filings
    results = ingestor.search_filings("0001234567")
    assert len(results) == 1
    assert results[0].accession_number == sample_sec_filing.accession_number

    # Search with form type filter
    assert len(ingestor.search_filings("0001234567", form_types=["10-K"])) == 1
    assert len(ingestor.search_filings("0001234567", form_types=["8-K"])) == 0

    # Risk factor extraction
    rf = ingestor.extract_risk_factors(sample_sec_filing.accession_number)
    assert len(rf) == 1
    assert rf[0]["topic"] == SECRiskTopic.REFINANCING_RISK.value

    # Assess sponsor credit
    credit = ingestor.assess_sponsor_credit("0001234567")
    assert credit["found_filings"] == 1
    assert credit["refinancing_risk_flag"] is True
    assert credit["credit_risk_level"] in ("ELEVATED", "CRITICAL")

    # MCP server calls
    server = SECEdgarMCPServer(ingestor=ingestor)
    mcp_call = server.handle_request(
        MCPRequest(
            method="tools/call",
            params={"name": "sec_edgar_assess_sponsor", "arguments": {"cik_or_ticker": "0001234567"}},
        )
    )
    assert mcp_call.error is None
    assert mcp_call.result["refinancing_risk_flag"] is True


# =========================================================================
# 2. Agents Subsystem Tests
# =========================================================================

def test_base_agent_audit_entry_generation(sample_deal):
    """BaseAgent computes SHA256 input hash and generates valid audit entry."""
    class TestAgent(BaseAgent):
        def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
            task.output_artifacts = {"result": "success"}
            task.status = TaskStatus.COMPLETED
            return task

    agent = TestAgent(role=AgentRole.INGESTION_COORDINATOR)
    task = AgentTask(
        role=agent.role,
        deal_id=sample_deal.id,
        description="Ingest deal data",
        input_artifacts={"param": 42},
    )
    state = SwarmWorkflowState(deal_id=sample_deal.id)
    completed = agent.execute_task(task, state)
    entry = agent.produce_audit_entry(completed, action="TEST_ACTION", rationale="Test rationale")

    assert entry.role == AgentRole.INGESTION_COORDINATOR
    assert entry.action_taken == "TEST_ACTION"
    assert entry.input_hash.startswith("sha256:")
    assert len(entry.input_hash.split(":")[1]) == 64


def test_specialized_agents_execution(
    sample_deal, sample_deed, sample_sec_filing, sample_offering_memorandum
):
    """Execute each specialized agent on task directives."""
    deed_ing = DeedIngestor([sample_deed])
    sec_ing = SECIngestor([sample_sec_filing])
    state = SwarmWorkflowState(deal_id=sample_deal.id)

    # 1. IngestionCoordinatorAgent
    ing_agent = IngestionCoordinatorAgent(deed_ingestor=deed_ing, sec_ingestor=sec_ing)
    t1 = AgentTask(
        role=AgentRole.INGESTION_COORDINATOR,
        deal_id=sample_deal.id,
        description="Ingest",
        input_artifacts={"offering_memorandum": sample_offering_memorandum},
    )
    res_t1 = ing_agent.execute_task(t1, state)
    assert res_t1.status == TaskStatus.COMPLETED
    assert res_t1.output_artifacts["chunks_indexed"] >= 1
    state.tasks.append(res_t1)

    # 2. MunicipalDeedAuditorAgent
    deed_agent = MunicipalDeedAuditorAgent(deed_ingestor=deed_ing)
    t2 = AgentTask(
        role=AgentRole.MUNICIPAL_DEED_AUDITOR,
        deal_id=sample_deal.id,
        description="Audit deeds",
        input_artifacts={
            "apn": sample_deal.address.apn,
            "county": sample_deal.address.county,
            "state": sample_deal.address.state,
            "reported_seller": sample_deal.sponsor_name,
        },
    )
    res_t2 = deed_agent.execute_task(t2, state)
    assert res_t2.status == TaskStatus.COMPLETED
    assert res_t2.output_artifacts["deeds_found"] == 1
    state.tasks.append(res_t2)

    # 3. SECDiligenceAnalystAgent
    sec_agent = SECDiligenceAnalystAgent(sec_ingestor=sec_ing)
    t3 = AgentTask(
        role=AgentRole.SEC_DILIGENCE_ANALYST,
        deal_id=sample_deal.id,
        description="Analyze SEC",
        input_artifacts={"sponsor_name": sample_deal.sponsor_name, "cik": sample_sec_filing.cik},
    )
    res_t3 = sec_agent.execute_task(t3, state)
    assert res_t3.status == TaskStatus.COMPLETED
    assert res_t3.output_artifacts["refinancing_risk_flag"] is True
    state.tasks.append(res_t3)

    # 4. DCFValuationEngineerAgent
    dcf_agent = DCFValuationEngineerAgent()
    t4 = AgentTask(
        role=AgentRole.DCF_VALUATION_ENGINEER,
        deal_id=sample_deal.id,
        description="Run DCF pro-forma valuation",
        input_artifacts={"deal": sample_deal},
    )
    res_t4 = dcf_agent.execute_task(t4, state)
    assert res_t4.status == TaskStatus.COMPLETED
    assert res_t4.output_artifacts["levered_irr"] > 0.0
    dcf_result = res_t4.output_artifacts["valuation_result"]
    state.tasks.append(res_t4)

    # 5. CreditRiskUnderwriterAgent
    risk_agent = CreditRiskUnderwriterAgent()
    t5 = AgentTask(
        role=AgentRole.CREDIT_RISK_UNDERWRITER,
        deal_id=sample_deal.id,
        description="Underwrite risk",
        input_artifacts={"deal": sample_deal, "valuation_result": dcf_result},
    )
    res_t5 = risk_agent.execute_task(t5, state)
    assert res_t5.status == TaskStatus.COMPLETED
    assert res_t5.output_artifacts["checklist_count"] > 0
    state.tasks.append(res_t5)

    # 6. InvestmentCommitteeChairAgent
    ic_agent = InvestmentCommitteeChairAgent()
    t6 = AgentTask(
        role=AgentRole.INVESTMENT_COMMITTEE_CHAIR,
        deal_id=sample_deal.id,
        description="Sign-off",
        input_artifacts={
            "deal": sample_deal,
            "valuation_result": dcf_result,
            "checklist_items": res_t5.output_artifacts["checklist_items"],
            "stress_scenarios": res_t5.output_artifacts["stress_scenarios"],
        },
    )
    res_t6 = ic_agent.execute_task(t6, state)
    assert res_t6.status == TaskStatus.COMPLETED
    assert res_t6.output_artifacts["decision_ready"] is True
    assert res_t6.output_artifacts["sign_off"] is not None


def test_swarm_factory_and_orchestrator_integration(sample_deal, sample_deed, sample_sec_filing):
    """create_agent_swarm binds all specialized agents to the orchestrator for complete DAG execution."""
    orchestrator = SwarmOrchestrator()
    deed_ing = DeedIngestor([sample_deed])
    sec_ing = SECIngestor([sample_sec_filing])

    swarm_agents = create_agent_swarm(
        orchestrator=orchestrator,
        deed_ingestor=deed_ing,
        sec_ingestor=sec_ing,
    )
    assert len(swarm_agents) == 6
    assert len(orchestrator.agents) == 6

    # Run workflow
    state = orchestrator.initialize_workflow(sample_deal)
    for _ in range(len(state.tasks)):
        state = orchestrator.advance_workflow(state.id)

    assert state.is_terminal is True
    assert len(state.completed_roles) == 6
    assert len(state.audit_trail) == 6
    assert state.final_memo_id is not None

    # Generated memo check
    memo = orchestrator.generate_underwriting_memo(sample_deal.id)
    assert memo.deal_id == sample_deal.id
    assert memo.valuation_summary.levered_irr > 0.0


# =========================================================================
# 3. Portfolio & Underwriting Rules Subsystem Tests
# =========================================================================

def test_portfolio_underwriter_aggregation_and_stress(
    sample_deal, sample_dcf_result
):
    """PortfolioUnderwriter roll-up, concentration, and macro stress."""
    underwriter = PortfolioUnderwriter()

    # Deal 1: Austin Multifamily
    underwriter.add_deal(sample_deal, sample_dcf_result)

    # Deal 2: Dallas Industrial
    from autonomous_cre_underwriting.types.property import (
        PropertyAddress,
        PropertyPhysical,
        UnitMix,
        UnitSpec,
    )
    deal_2 = PropertyDeal(
        id="deal-dfw-002",
        title="DFW Logistics Center",
        property_type=PropertyType.INDUSTRIAL,
        status=DealStatus.UNDERWRITING,
        address=PropertyAddress(
            street="500 Airport Fwy", city="Irving", state="tx", postal_code="75038", county="Dallas", apn="99-8877"
        ),
        physical=PropertyPhysical(
            gross_square_feet=250000, rentable_square_feet=250000, year_built=2021, site_area_acres=15.0
        ),
        unit_mix=UnitMix(
            items=[
                UnitSpec(
                    unit_type="Warehouse Bay",
                    count=1,
                    square_feet=250000.0,
                    in_place_rent=175000.0,
                    market_rent=180000.0,
                )
            ]
        ),
        asking_price=36500000.0,
        target_purchase_price=35000000.0,
        in_place_noi=2100000.0,
        sponsor_name="Prologis REIT",
    )
    underwriter.add_deal(deal_2)

    assert len(underwriter.get_deals()) == 2

    # Portfolio Summary
    summary = underwriter.compute_portfolio_summary()
    assert summary.property_count == 2
    assert summary.total_purchase_price == 59500000.0
    assert summary.total_noi > 3000000.0
    assert summary.weighted_avg_cap_rate > 0.05
    assert summary.portfolio_ltv > 0.50

    # Concentration
    conc = underwriter.compute_concentration()
    assert conc.by_geography["TX"] == 1.0
    assert "multifamily" in conc.by_property_type
    assert "industrial" in conc.by_property_type
    assert conc.top_asset_concentration_pct == pytest.approx(35000000.0 / 59500000.0, rel=1e-3)

    # Stress test
    impact = underwriter.stress_portfolio(
        name="Stagflation Crisis",
        rent_shock_pct=-0.08,
        opex_shock_pct=0.06,
        exit_cap_expansion_bps=75,
    )
    assert impact.base_noi == summary.total_noi
    assert impact.stressed_noi < impact.base_noi
    assert impact.noi_drop_pct > 0.0
    assert impact.stressed_dscr > 0.0

    # Remove deal
    assert underwriter.remove_deal("deal-dfw-002") is True
    assert len(underwriter.get_deals()) == 1


def test_underwriting_rules_engine(sample_deal, sample_dcf_result):
    """UnderwritingRulesEngine evaluates institutional investment hurdles."""
    rules = UnderwritingRulesEngine()

    deal_results = rules.evaluate_deal(sample_deal, sample_dcf_result)
    assert len(deal_results) == 5

    # Check individual rules
    ltv_rule = next(r for r in deal_results if r.rule_name == "Max LTV Policy")
    assert ltv_rule.passed is True
    assert ltv_rule.actual_value <= 0.75

    irr_rule = next(r for r in deal_results if r.rule_name == "Levered IRR Hurdle")
    assert irr_rule.passed is True
    assert irr_rule.actual_value >= 0.14

    assert UnderwritingRulesEngine.is_approved(deal_results) is True

    # Portfolio evaluation
    underwriter = PortfolioUnderwriter()
    underwriter.add_deal(sample_deal, sample_dcf_result)
    summary = underwriter.compute_portfolio_summary()
    conc = underwriter.compute_concentration()

    port_results = rules.evaluate_portfolio(summary, conc)
    assert len(port_results) == 3
    # Top asset concentration is 1.0 for single asset so exceeds 0.35 limit
    top_rule = next(r for r in port_results if r.rule_name == "Max Single Asset Exposure")
    assert top_rule.passed is False


# =========================================================================
# 4. Reporting Subsystem Tests
# =========================================================================

def test_dcf_schedule_exporter(sample_dcf_result):
    """DCFScheduleExporter exports pro-forma cash flows to CSV, Markdown, and JSON."""
    csv_text = DCFScheduleExporter.to_csv(sample_dcf_result)
    assert "Potential Gross Revenue" in csv_text
    assert "Net Operating Income" in csv_text
    assert len(csv_text.strip().split("\n")) == 2  # Header + 1 year

    md_table = DCFScheduleExporter.to_markdown_table(sample_dcf_result)
    assert "| Year | PGR |" in md_table
    assert "1.32x" in md_table

    d = DCFScheduleExporter.to_dict(sample_dcf_result)
    assert d["deal_id"] == sample_dcf_result.deal_id
    assert len(d["annual_cash_flows"]) == 1


def test_memo_exporter(sample_memo):
    """MemoExporter formats complete UnderwritingMemo to Markdown, Summary text, and JSON."""
    md = MemoExporter.to_markdown(sample_memo)
    assert "# INVESTMENT COMMITTEE MEMORANDUM" in md
    assert "1. Executive Summary" in md
    assert "2. Key Valuation & Return Metrics" in md
    assert "3. Diligence Risk Findings" in md
    assert "Utility Easement Encroachment" in md
    assert "4. Covenant & Diligence Checklist" in md
    assert "5. Downside Stress Scenarios" in md
    assert "6. Conditions Precedent to Closing" in md
    assert "7. Swarm Agent Committee Sign-Offs" in md

    summary = MemoExporter.to_summary_text(sample_memo)
    assert sample_memo.deal_title in summary
    assert "Risks: 2 flagged" in summary

    raw_json = MemoExporter.to_json(sample_memo)
    parsed = json.loads(raw_json)
    assert parsed["deal_id"] == sample_memo.deal_id


def test_audit_trail_verifier(sample_deal):
    """AuditTrailVerifier validates cryptographic hashes and unbroken audit log."""
    verifier = AuditTrailVerifier()

    # Valid entry
    entry = AgentAuditEntry(
        task_id="task-001",
        role=AgentRole.DCF_VALUATION_ENGINEER,
        action_taken="CALCULATE_IRR",
        justification="Discounted cash flow model using Newton-Raphson",
        input_hash="sha256:" + "a" * 64,
        output_summary="IRR 16.8%",
    )
    assert verifier.verify_entry(entry) is True

    # Invalid hash format
    bad_entry = AgentAuditEntry(
        task_id="task-002",
        role=AgentRole.DCF_VALUATION_ENGINEER,
        action_taken="CALCULATE_IRR",
        justification="Discounted cash flow model",
        input_hash="invalid-hash",
        output_summary="Failed",
    )
    assert verifier.verify_entry(bad_entry) is False

    # Workflow state verification
    state = SwarmWorkflowState(deal_id=sample_deal.id)
    task = AgentTask(
        id="task-001",
        role=AgentRole.DCF_VALUATION_ENGINEER,
        deal_id=sample_deal.id,
        description="Run DCF",
        input_artifacts={"price": 24500000.0},
    )
    state.tasks.append(task)
    state.audit_trail.append(entry)

    audit_report = verifier.verify_workflow(state)
    assert audit_report["total_entries"] == 1
    assert audit_report["valid_entries"] == 1
    assert audit_report["audit_valid"] is True


# =========================================================================
# 5. Storage Subsystem Tests
# =========================================================================

def test_deal_repository_crud_and_query(sample_deal, sample_memo, sample_dcf_result, tmp_path):
    """DealRepository stores, queries, persists, and restores deals and memos."""
    repo = DealRepository(persistence_dir=str(tmp_path))

    # Save and get deal
    repo.save_deal(sample_deal)
    assert repo.get_deal(sample_deal.id) is not None
    assert len(repo.list_deals()) == 1

    # Save memo & valuation
    repo.save_memo(sample_memo)
    assert repo.get_memo(sample_deal.id) is not None
    repo.save_valuation(sample_dcf_result)
    assert repo.get_valuation(sample_deal.id) is not None

    # Query deals
    q1 = repo.query_deals(property_type=PropertyType.MULTIFAMILY)
    assert len(q1) == 1
    q2 = repo.query_deals(min_price=30000000.0)
    assert len(q2) == 0
    q3 = repo.query_deals(sponsor="Apex")
    assert len(q3) == 1

    # File export and import
    exported_count = repo.export_to_directory()
    assert exported_count == 2  # 1 deal + 1 memo

    # Fresh repository importing from disk
    new_repo = DealRepository()
    imported_count = new_repo.import_from_directory(str(tmp_path))
    assert imported_count == 2
    assert new_repo.get_deal(sample_deal.id) is not None
    assert new_repo.get_memo(sample_deal.id) is not None

    # Delete deal
    assert repo.delete_deal(sample_deal.id) is True
    assert repo.get_deal(sample_deal.id) is None
    assert repo.get_memo(sample_deal.id) is None

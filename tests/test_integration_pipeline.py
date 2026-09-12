"""End-to-end integration pipeline test suite for Autonomous CRE Underwriting Swarm."""

from datetime import date
from pathlib import Path

import pytest

from autonomous_cre_underwriting.agents import create_agent_swarm
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
    UnderwritingCriteria,
    UnderwritingRulesEngine,
)
from autonomous_cre_underwriting.reporting import (
    AuditTrailVerifier,
    DCFScheduleExporter,
    MemoExporter,
)
from autonomous_cre_underwriting.storage import DealRepository
from autonomous_cre_underwriting.types.agents import TaskStatus
from autonomous_cre_underwriting.types.events import EventType
from autonomous_cre_underwriting.types.ingestion import (
    DeedRecord,
    DeedType,
    SECFiling,
    SECFilingType,
    SECRiskMention,
    SECRiskTopic,
)
from autonomous_cre_underwriting.types.property import (
    DealStatus,
    PropertyAddress,
    PropertyDeal,
    PropertyPhysical,
    PropertyType,
    UnitMix,
    UnitSpec,
)
from autonomous_cre_underwriting.types.risk import MemoRecommendation


def test_full_diligence_lifecycle_pipeline(sample_deal, sample_offering_memorandum):
    """Test full multi-agent swarm diligence from MCP ingestion to investment committee memo."""
    # 1. Setup deed records and municipal MCP server
    deed = DeedRecord(
        parcel_number=sample_deal.address.apn,
        document_number="DOC-2022-88190",
        recording_date=date(2022, 5, 20),
        deed_type=DeedType.SPECIAL_WARRANTY_DEED,
        grantor="Previous Property Owner LLC",
        grantee="Apex Capital Partners",
        consideration_amount=19500000.0,
        county_name="Travis",
        legal_description="Lot 3, Block 7, Congress Ave Commercial Addition",
        verified=True,
    )
    deed_ingestor = DeedIngestor(seed_records=[deed])
    deed_server = MunicipalDeedMCPServer(ingestor=deed_ingestor)

    # 2. Setup SEC filings and SEC MCP server
    risk_mention = SECRiskMention(
        topic=SECRiskTopic.REFINANCING_RISK,
        excerpt="The sponsor maintains floating senior debt maturing in Q3 2027.",
        item_section="Item 1A. Risk Factors",
        severity_score=0.60,
        relevance_score=0.85,
    )
    sec_filing = SECFiling(
        accession_number="0001850000-26-000100",
        cik="0001850000",
        company_name="Apex Capital Partners",
        form_type=SECFilingType.FORM_10K,
        filing_date=date(2026, 2, 15),
        report_url="https://sec.gov/filing/0001850000",
        risk_mentions=[risk_mention],
    )
    sec_ingestor = SECIngestor(seed_filings=[sec_filing])
    sec_server = SECEdgarMCPServer(ingestor=sec_ingestor)

    # 3. Verify MCP servers respond via protocol
    deed_req = MCPRequest(
        method="tools/call",
        params={
            "name": "municipal_deed_verify_chain",
            "arguments": {
                "apn": sample_deal.address.apn,
                "reported_seller": "Apex Capital Partners",
            },
        },
    )
    deed_resp = deed_server.handle_request(deed_req)
    assert deed_resp.result["verified"] is True

    sec_req = MCPRequest(
        method="tools/call",
        params={
            "name": "sec_edgar_assess_sponsor",
            "arguments": {"cik_or_ticker": "0001850000"},
        },
    )
    sec_resp = sec_server.handle_request(sec_req)
    assert sec_resp.result["credit_risk_level"] in ("MODERATE", "LOW", "ELEVATED")

    # 4. Bootstrap Swarm Orchestrator with full agent swarm
    orchestrator = SwarmOrchestrator()
    create_agent_swarm(
        orchestrator=orchestrator,
        deed_ingestor=deed_ingestor,
        sec_ingestor=sec_ingestor,
    )

    # Index offering memorandum
    orchestrator.rag_engine.index_document(sample_offering_memorandum)

    # 5. Execute DAG sequence to terminal state
    workflow_state = orchestrator.initialize_workflow(sample_deal)
    assert len(workflow_state.tasks) == 6

    step_count = 0
    while not workflow_state.is_terminal and step_count < 10:
        workflow_state = orchestrator.advance_workflow(workflow_state.id)
        step_count += 1

    assert workflow_state.is_terminal is True
    assert all(t.status == TaskStatus.COMPLETED for t in workflow_state.tasks)

    # 6. Verify event journal
    events = orchestrator.event_bus.get_history()
    event_types = [e.event_type for e in events]
    assert EventType.DEAL_CREATED in event_types
    assert EventType.UNDERWRITING_MEMO_GENERATED in event_types

    # 7. Verify audit trail cryptographic integrity
    verifier = AuditTrailVerifier()
    audit_report = verifier.verify_workflow(workflow_state)
    assert audit_report["audit_valid"] is True
    assert audit_report["chronological"] is True
    assert audit_report["valid_entries"] == len(workflow_state.audit_trail)
    assert len(audit_report["invalid_entry_ids"]) == 0

    # 8. Verify generated Investment Committee Underwriting Memo and DCF outputs
    memo = orchestrator.memos.get(sample_deal.id)
    assert memo is not None
    assert memo.deal_id == sample_deal.id
    assert memo.recommendation in (
        MemoRecommendation.STRONGLY_RECOMMEND,
        MemoRecommendation.APPROVE_WITH_CONDITIONS,
        MemoRecommendation.REVISE_TERMS,
    )
    assert memo.valuation_summary.levered_irr > 0.0
    assert memo.valuation_summary.equity_multiple > 1.0
    assert len(memo.stress_scenarios) > 0
    assert len(memo.sign_offs) >= 1

    dcf_res = orchestrator.dcf_results.get(sample_deal.id)
    assert dcf_res is not None
    assert len(dcf_res.sensitivity.scenarios) > 0


def test_persistence_export_and_import_pipeline(tmp_path, sample_deal):
    """Verify complete deal, memo, valuation, and workflow persistence round-trip."""
    # Run full workflow on deal
    orch = SwarmOrchestrator()
    create_agent_swarm(orchestrator=orch)

    state = orch.initialize_workflow(sample_deal)
    while not state.is_terminal:
        state = orch.advance_workflow(state.id)

    memo = orch.memos[sample_deal.id]
    val = orch.dcf_results[sample_deal.id]

    # Save to DealRepository
    export_dir = tmp_path / "cre_data_store"
    repo1 = DealRepository(persistence_dir=str(export_dir))
    repo1.save_deal(sample_deal)
    repo1.save_memo(memo)
    repo1.save_valuation(val)
    repo1.save_workflow(state)

    # Export to disk
    exported_count = repo1.export_to_directory()
    assert exported_count >= 2

    # Verify JSON files exist on disk
    assert (export_dir / "deals" / f"{sample_deal.id}.json").exists()
    assert (export_dir / "memos" / f"{sample_deal.id}_memo.json").exists()
    assert (export_dir / "valuations" / f"{sample_deal.id}.json").exists()
    assert (export_dir / "workflows" / f"{sample_deal.id}_{state.id}.json").exists()

    # Import into fresh repository
    repo2 = DealRepository(persistence_dir=str(export_dir))
    imported_count = repo2.import_from_directory()
    assert imported_count >= 2

    # Verify entities restored
    restored_deal = repo2.get_deal(sample_deal.id)
    assert restored_deal is not None
    assert restored_deal.title == sample_deal.title
    assert restored_deal.target_purchase_price == sample_deal.target_purchase_price

    restored_memo = repo2.get_memo(sample_deal.id)
    assert restored_memo is not None
    assert restored_memo.valuation_summary.levered_irr == memo.valuation_summary.levered_irr

    restored_val = repo2.get_valuation(sample_deal.id)
    assert restored_val is not None
    assert restored_val.metrics.levered_irr == val.metrics.levered_irr

    restored_wf = repo2.get_workflow_for_deal(sample_deal.id)
    assert restored_wf is not None
    assert restored_wf.is_terminal is True


def test_reporting_exporters_pipeline(sample_deal, sample_dcf_result, sample_memo):
    """Test generation and structure of Markdown memos, JSON exports, and DCF CSV schedules."""
    # 1. Underwriting Memo Markdown Export
    md_content = MemoExporter.to_markdown(sample_memo)
    assert "# INVESTMENT COMMITTEE MEMORANDUM:" in md_content
    assert "## 1. Executive Summary" in md_content
    assert "## 2. Key Valuation & Return Metrics" in md_content
    assert "## 3. Diligence Risk Findings" in md_content
    assert "## 4. Covenant & Diligence Checklist" in md_content
    assert "## 5. Downside Stress Scenarios" in md_content
    assert "## 6. Conditions Precedent to Closing" in md_content
    assert "## 7. Swarm Agent Committee Sign-Offs" in md_content

    # 2. Underwriting Memo JSON Export
    json_str = MemoExporter.to_json(sample_memo)
    assert sample_memo.id in json_str
    assert sample_memo.deal_id in json_str

    # 3. DCF Pro-Forma Cash Flow CSV Export
    csv_content = DCFScheduleExporter.to_csv(sample_dcf_result)
    lines = [line for line in csv_content.strip().split("\n") if line]
    assert len(lines) >= 2  # Header + cash flow rows
    assert "Year,Potential Gross Revenue,Vacancy & Credit Loss" in lines[0]


def test_multi_deal_portfolio_aggregation_and_policy_checks(sample_deal):
    """Test aggregating multiple underwritten deals into a unified portfolio and evaluating against policy."""
    deal_mf = sample_deal

    deal_office = PropertyDeal(
        id="DEAL-OFFICE-002",
        title="Domain Tech Plaza",
        property_type=PropertyType.OFFICE,
        status=DealStatus.UNDERWRITING,
        address=PropertyAddress(
            street="11000 Domain Dr",
            city="Austin",
            state="tx",
            postal_code="78758",
            county="Travis",
            apn="01-9988-7766-0000",
        ),
        physical=PropertyPhysical(
            gross_square_feet=120000.0,
            rentable_square_feet=110000.0,
            year_built=2019,
            site_area_acres=3.8,
        ),
        unit_mix=UnitMix(
            items=[
                UnitSpec(
                    unit_type="Tech Office Suite",
                    count=10,
                    square_feet=11000.0,
                    in_place_rent=35000.0,
                    market_rent=38000.0,
                    vacant_units=1,
                )
            ]
        ),
        asking_price=35000000.0,
        target_purchase_price=32000000.0,
        in_place_noi=2200000.0,
        sponsor_name="Apex Capital Partners",
    )

    deal_ind = PropertyDeal(
        id="DEAL-IND-003",
        title="Park 130 Logistics Center",
        property_type=PropertyType.INDUSTRIAL,
        status=DealStatus.UNDERWRITING,
        address=PropertyAddress(
            street="15000 E Parmer Ln",
            city="Pflugerville",
            state="tx",
            postal_code="78660",
            county="Travis",
            apn="01-5544-3322-0000",
        ),
        physical=PropertyPhysical(
            gross_square_feet=200000.0,
            rentable_square_feet=195000.0,
            year_built=2022,
            site_area_acres=12.0,
        ),
        unit_mix=UnitMix(
            items=[
                UnitSpec(
                    unit_type="Distribution Bay",
                    count=4,
                    square_feet=48750.0,
                    in_place_rent=40000.0,
                    market_rent=42000.0,
                    vacant_units=0,
                )
            ]
        ),
        asking_price=28000000.0,
        target_purchase_price=26000000.0,
        in_place_noi=1850000.0,
        sponsor_name="Lone Star Logistics LP",
    )

    # Underwrite all 3 deals
    orch = SwarmOrchestrator()
    portfolio = PortfolioUnderwriter()

    for d in [deal_mf, deal_office, deal_ind]:
        orch.deals[d.id] = d
        memo = orch.generate_underwriting_memo(d.id)
        dcf_val = orch.dcf_results[d.id]
        portfolio.add_deal(d, dcf_result=dcf_val)

    # Compute consolidated summary
    summary = portfolio.compute_portfolio_summary()
    assert summary.property_count == 3
    assert summary.total_purchase_price == deal_mf.target_purchase_price + 32000000.0 + 26000000.0
    assert summary.total_debt > 0.0
    assert summary.weighted_avg_dscr > 1.20
    assert summary.portfolio_ltv > 0.50

    # Concentration check
    concentration = portfolio.compute_concentration()
    assert "multifamily" in concentration.by_property_type
    assert "office" in concentration.by_property_type
    assert "industrial" in concentration.by_property_type
    assert concentration.top_asset_concentration_pct < 1.0

    # Underwriting policy evaluation
    criteria = UnderwritingCriteria(
        min_levered_irr=0.12,
        min_dscr=1.20,
        max_ltv=0.75,
    )
    rules_engine = UnderwritingRulesEngine(criteria=criteria)
    for d in [deal_mf, deal_office, deal_ind]:
        val = orch.dcf_results[d.id]
        policy_results = rules_engine.evaluate_deal(d, val)
        assert len(policy_results) == 5
        # Each rule evaluated has threshold and actual
        for r in policy_results:
            assert isinstance(r.passed, bool)
            assert r.rule_name is not None

    # Macro stress simulation
    stress_result = portfolio.stress_portfolio(
        name="Severe Stagflation",
        rent_shock_pct=-0.08,
        opex_shock_pct=0.08,
        min_dscr_hurdle=1.20,
    )
    assert stress_result.scenario_name == "Severe Stagflation"
    assert stress_result.noi_drop_pct > 0.0
    assert stress_result.stressed_noi < stress_result.base_noi

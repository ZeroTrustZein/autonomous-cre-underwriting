"""Comprehensive unit and integration test suite for Stage 3 core engines."""

from datetime import date
import pytest

from autonomous_cre_underwriting.engine import (
    DCFEngine,
    DeadLetterEntry,
    HybridRAGEngine,
    InMemoryEventBus,
    KnowledgeGraphEngine,
    RiskSynthesisEngine,
    SwarmOrchestrator,
    chunk_text,
    compute_dense_embedding,
    compute_irr,
    compute_npv,
    compute_remaining_loan_balance,
    cosine_similarity,
    generate_loan_amortization_schedule,
)
from autonomous_cre_underwriting.protocols import AgentProtocol
from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)
from autonomous_cre_underwriting.types.events import EventPriority, EventType, SwarmEvent
from autonomous_cre_underwriting.types.financial import (
    DCFParameters,
    FinancingAssumptions,
    LoanType,
)
from autonomous_cre_underwriting.types.ingestion import (
    DocumentChunk,
    IngestionSourceType,
    OfferingMemorandum,
)
from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
    RelationType,
)
from autonomous_cre_underwriting.types.property import PropertyDeal
from autonomous_cre_underwriting.types.risk import (
    ChecklistStatus,
    MemoRecommendation,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)


# -------------------------------------------------------------------------
# DCF Engine Tests
# -------------------------------------------------------------------------


def test_compute_irr():
    """Verify internal rate of return calculation and boundary conditions."""
    # Standard $100 investment returning $20/yr for 5 yrs + $100 principal: IRR ~20%
    cf_standard = [-100.0, 20.0, 20.0, 20.0, 20.0, 120.0]
    irr = compute_irr(cf_standard)
    assert pytest.approx(irr, rel=1e-2) == 0.20

    # All positive or all negative flows have no real rate
    assert compute_irr([100.0, 200.0, 300.0]) == 0.0
    assert compute_irr([-100.0, -50.0, -20.0]) == 0.0
    assert compute_irr([100.0]) == 0.0


def test_compute_npv():
    """Verify net present value calculation discounting."""
    cfs = [-1000.0, 300.0, 400.0, 500.0]
    npv_10 = compute_npv(0.10, cfs)
    # Manual: -1000 + 300/1.1 + 400/1.21 + 500/1.331 = -1000 + 272.73 + 330.58 + 375.66 = -21.03
    assert pytest.approx(npv_10, abs=1.0) == -21.03


def test_loan_amortization_schedule(sample_financing):
    """Month-by-month loan amortization schedule."""
    schedule = generate_loan_amortization_schedule(sample_financing)
    assert len(schedule) == sample_financing.term_years * 12

    # First month is IO: principal paid must be 0
    m1 = schedule[0]
    assert m1.month == 1
    assert m1.principal == 0.0
    assert m1.interest > 0.0
    assert m1.ending_balance == sample_financing.loan_amount

    # Month after IO period (Year 3, Month 25): principal paid > 0
    m25 = schedule[24]
    assert m25.month == 25
    assert m25.principal > 0.0
    assert m25.ending_balance < m25.beginning_balance


def test_compute_remaining_loan_balance(sample_financing):
    """Check remaining balance during IO and amortizing years."""
    # Year 0 and IO years (1 and 2)
    b0 = compute_remaining_loan_balance(sample_financing, 0)
    assert b0 == sample_financing.loan_amount

    b1 = compute_remaining_loan_balance(sample_financing, 1)
    assert b1 == sample_financing.loan_amount

    b2 = compute_remaining_loan_balance(sample_financing, 2)
    assert b2 == sample_financing.loan_amount

    # Year 3 after amortization starts: balance must decrease
    b3 = compute_remaining_loan_balance(sample_financing, 3)
    assert b3 < sample_financing.loan_amount
    assert b3 > 0.0


def test_dcf_engine_full_valuation(
    sample_deal, sample_dcf_params, sample_financing, sample_historical_financials
):
    """Full multi-year DCF pro-forma, metrics, sensitivity, and checksum."""
    engine = DCFEngine()
    result = engine.compute_valuation(
        deal=sample_deal,
        parameters=sample_dcf_params,
        financing=sample_financing,
        t12=sample_historical_financials,
    )

    assert result.deal_id == sample_deal.id
    assert len(result.annual_cash_flows) == sample_dcf_params.holding_period_years

    # Check cash flow structure
    y1 = result.annual_cash_flows[0]
    assert y1.year == 1
    assert y1.effective_gross_income > 0.0
    assert y1.net_operating_income > 0.0
    assert y1.unlevered_cash_flow > 0.0
    assert y1.levered_cash_flow > 0.0
    assert y1.dscr > 1.0
    assert y1.debt_yield > 0.05

    # Check summary metrics
    m = result.metrics
    assert m.purchase_price == sample_deal.target_purchase_price
    assert m.equity_invested > 0.0
    assert m.levered_irr > 0.05
    assert m.unlevered_irr > 0.05
    assert m.equity_multiple > 1.0
    assert m.gross_exit_sales_price > 0.0
    assert m.net_sales_proceeds > 0.0
    assert m.min_dscr_observed > 1.0
    assert m.average_dscr >= m.min_dscr_observed

    # Check sensitivity matrix (5x5 grid = 25 scenarios)
    assert len(result.sensitivity.scenarios) == 25
    assert result.sensitivity.base_levered_irr == m.levered_irr

    # Check deterministic model checksum
    assert result.model_checksum.startswith("sha256:")


def test_dcf_stress_test(sample_deal, sample_dcf_params, sample_financing):
    """Downside stress scenario testing covenant breaches."""
    engine = DCFEngine()
    scenario = engine.stress_test(
        deal=sample_deal,
        parameters=sample_dcf_params,
        financing=sample_financing,
        name="Stagflation Stress",
        rent_shock_pct=-0.10,
        vacancy_shock_pct=0.08,
        opex_shock_pct=0.10,
        exit_cap_expansion_bps=100,
    )

    assert scenario.name == "Stagflation Stress"
    assert scenario.rent_shock_pct == -0.10
    assert scenario.vacancy_shock_pct == 0.08
    assert scenario.min_dscr_observed >= 0.0


# -------------------------------------------------------------------------
# Knowledge Graph Engine Tests
# -------------------------------------------------------------------------


def test_knowledge_graph_engine_crud():
    """Entity and relation insertion, retrieval, and type filtering."""
    engine = KnowledgeGraphEngine()

    p = GraphEntity(
        entity_id="prop-1",
        entity_type=EntityType.PROPERTY,
        label="Austin Plaza",
        properties={"deal_id": "deal-101"},
    )
    s = GraphEntity(
        entity_id="spon-1",
        entity_type=EntityType.SPONSOR,
        label="Apex Sponsor LP",
    )
    engine.upsert_entity(p)
    engine.upsert_entity(s)

    assert len(engine.find_entities_by_type(EntityType.PROPERTY)) == 1
    assert len(engine.find_entities_by_type(EntityType.SPONSOR)) == 1

    rel = GraphRelation(
        relation_id="rel-1",
        source_id="spon-1",
        target_id="prop-1",
        relation_type=RelationType.OWNS,
    )
    engine.upsert_relation(rel)
    assert len(engine.graph.relations) == 1

    # Deal subgraph extraction
    subgraph = engine.get_graph_for_deal("deal-101")
    assert "prop-1" in subgraph.entities
    assert "spon-1" in subgraph.entities
    assert len(subgraph.relations) == 1


def test_knowledge_graph_chain_of_title():
    """Verify chronological deed chain and gap detection."""
    engine = KnowledgeGraphEngine()

    prop = GraphEntity(entity_id="p1", entity_type=EntityType.PROPERTY, label="Target Property")
    o1 = GraphEntity(entity_id="owner-1", entity_type=EntityType.OWNER_ENTITY, label="First Owner LLC")
    o2 = GraphEntity(entity_id="owner-2", entity_type=EntityType.OWNER_ENTITY, label="Second Owner LLC")

    engine.upsert_entity(prop)
    engine.upsert_entity(o1)
    engine.upsert_entity(o2)

    # Deed 1: 2018 First Owner buys from Developer
    engine.upsert_relation(
        GraphRelation(
            relation_id="d1",
            source_id="owner-1",
            target_id="p1",
            relation_type=RelationType.OWNS,
            properties={
                "recording_date": "2018-05-01",
                "grantor": "Original Developer Inc",
                "grantee": "First Owner LLC",
                "consideration_amount": 12000000.0,
            },
        )
    )

    # Deed 2: 2022 Second Owner buys from First Owner (continuous chain)
    engine.upsert_relation(
        GraphRelation(
            relation_id="d2",
            source_id="owner-2",
            target_id="p1",
            relation_type=RelationType.OWNS,
            properties={
                "recording_date": "2022-09-15",
                "grantor": "First Owner LLC",
                "grantee": "Second Owner LLC",
                "consideration_amount": 16500000.0,
            },
        )
    )

    chain, is_continuous = engine.trace_chain_of_title("p1")
    assert len(chain) == 2
    assert is_continuous is True
    assert chain[0]["recording_date"] == date(2018, 5, 1)
    assert chain[1]["recording_date"] == date(2022, 9, 15)


def test_knowledge_graph_encumbrances_and_path():
    """Detect liens, aggregate dollar exposure, and shortest path."""
    engine = KnowledgeGraphEngine()

    prop = GraphEntity(entity_id="p1", entity_type=EntityType.PROPERTY, label="Property")
    lender = GraphEntity(entity_id="l1", entity_type=EntityType.LENDER, label="Bank of America")
    lien_holder = GraphEntity(entity_id="lh1", entity_type=EntityType.LIEN_HOLDER, label="City Tax Collector")

    engine.upsert_entity(prop)
    engine.upsert_entity(lender)
    engine.upsert_entity(lien_holder)

    engine.upsert_relation(
        GraphRelation(
            relation_id="enc-1",
            source_id="l1",
            target_id="p1",
            relation_type=RelationType.ENCUMBERS,
            properties={"lien_amount": 15000000.0},
        )
    )
    engine.upsert_relation(
        GraphRelation(
            relation_id="enc-2",
            source_id="lh1",
            target_id="p1",
            relation_type=RelationType.ENCUMBERS,
            properties={"lien_amount": 45000.0},
        )
    )

    encs, total_enc = engine.detect_encumbrances_and_liens("p1")
    assert len(encs) == 2
    assert total_enc == 15045000.0

    # Shortest path from l1 to lh1 (via p1)
    path = engine.find_shortest_path("l1", "lh1")
    assert path == ["l1", "p1", "lh1"]


# -------------------------------------------------------------------------
# Hybrid RAG Engine Tests
# -------------------------------------------------------------------------


def test_dense_embedding_and_cosine_similarity():
    """Test unit normalization and cosine angle math."""
    vec1 = compute_dense_embedding("Class A multifamily high occupancy Austin Texas")
    vec2 = compute_dense_embedding("Multifamily residential apartments located in Austin")
    vec3 = compute_dense_embedding("Industrial warehouse logistics cold storage Chicago")

    assert len(vec1) == 64
    # Unit norm
    norm1 = sum(x * x for x in vec1)
    assert pytest.approx(norm1, rel=1e-3) == 1.0

    sim_related = cosine_similarity(vec1, vec2)
    sim_unrelated = cosine_similarity(vec1, vec3)
    assert sim_related > sim_unrelated


def test_chunk_text():
    """Sliding-window chunk generation with overlap."""
    text = "Word " * 150
    chunks = chunk_text(text, document_id="doc-1", chunk_size_words=50, overlap_words=10)
    assert len(chunks) >= 3
    for c in chunks:
        assert c.document_id == "doc-1"
        assert len(c.embedding) == 64
        assert c.token_count <= 50


def test_hybrid_rag_search():
    """Index offering memorandum and execute hybrid search."""
    rag = HybridRAGEngine(alpha=0.6)

    om = OfferingMemorandum(
        deal_id="deal-atx-001",
        filename="Travis_OM.pdf",
        file_size_bytes=100000,
        file_hash="abc123hash",
        page_count=10,
        brokerage_firm="CBRE",
        publication_date=date(2026, 1, 1),
        claimed_asking_price=25000000.0,
        claimed_pro_forma_noi=1350000.0,
        claimed_cap_rate=0.054,
        claimed_occupancy=0.96,
        executive_summary="The property consists of 100 Class A apartment homes located in central Austin with rent upside.",
    )

    indexed = rag.index_document(om)
    assert indexed > 0

    # Search for relevant query
    results = rag.hybrid_search("apartment homes in central Austin", deal_id="deal-atx-001", top_k=2)
    assert len(results) > 0
    assert "austin" in results[0].text_content.lower()

    # Search with empty query or non-existent deal returns empty
    assert rag.hybrid_search("random text", deal_id="non-existent") == []


# -------------------------------------------------------------------------
# Event Bus Tests
# -------------------------------------------------------------------------


def test_event_bus_pub_sub_and_wildcard():
    """Test pub/sub subscriptions, wildcard matching, and filtering."""
    bus = InMemoryEventBus()
    received: list[SwarmEvent] = []

    def handler(evt: SwarmEvent) -> None:
        received.append(evt)

    # Subscribe to wildcard
    bus.subscribe("*", handler)

    evt1 = SwarmEvent(
        event_type=EventType.DEAL_CREATED,
        deal_id="deal-001",
        source_role=AgentRole.SWARM_ORCHESTRATOR.value,
        priority=EventPriority.HIGH,
        payload={"step": 1},
    )
    bus.publish(evt1)

    assert len(received) == 1
    assert received[0].event_type == EventType.DEAL_CREATED

    # History querying
    history = bus.get_history(deal_id="deal-001")
    assert len(history) == 1
    assert bus.get_history(deal_id="deal-other") == []

    # Unsubscribe
    bus.unsubscribe("*", handler)
    evt2 = SwarmEvent(
        event_type=EventType.DEED_AUDIT_COMPLETED,
        deal_id="deal-001",
        source_role=AgentRole.MUNICIPAL_DEED_AUDITOR.value,
        payload={},
    )
    bus.publish(evt2)
    assert len(received) == 1  # not received after unsubscribe


def test_event_bus_error_isolation():
    """Failed subscriber must not crash bus and gets recorded in dead letters."""
    bus = InMemoryEventBus()

    def crashing_handler(evt: SwarmEvent) -> None:
        raise ValueError("Handler deliberate failure")

    bus.subscribe(EventType.AGENT_ERROR_ENCOUNTERED.value, crashing_handler)

    evt = SwarmEvent(
        event_type=EventType.AGENT_ERROR_ENCOUNTERED,
        deal_id="deal-001",
        source_role="test",
        payload={},
    )
    # Should not raise exception
    bus.publish(evt)

    dead_letters = bus.get_dead_letters()
    assert len(dead_letters) == 1
    assert "deliberate failure" in dead_letters[0].error_message


# -------------------------------------------------------------------------
# Risk Synthesis Engine Tests
# -------------------------------------------------------------------------


def test_risk_synthesis_covenant_and_recommendation(
    sample_deal, sample_financing, sample_dcf_result
):
    """Test covenant compliance checks and consensus recommendation logic."""
    engine = RiskSynthesisEngine()

    covenants = engine.evaluate_covenant_compliance(
        deal=sample_deal,
        financing=sample_financing,
        dcf_result=sample_dcf_result,
    )
    assert len(covenants) >= 2

    # In sample_dcf_result min_dscr is 1.31 which exceeds 1.25 covenant -> PASS
    dscr_item = next(c for c in covenants if "DSCR" in c.requirement)
    assert dscr_item.status == ChecklistStatus.PASS

    std_items = engine.build_standard_checklist(deal=sample_deal, title_continuous=True)
    assert len(std_items) >= 3

    # Run decision synthesis under clean conditions
    rec, conditions, summary = engine.synthesize_decision(
        deal=sample_deal,
        metrics=sample_dcf_result.metrics,
        risk_findings=[],
        checklist=covenants + std_items,
        stress_scenarios=[],
    )
    assert rec == MemoRecommendation.STRONGLY_RECOMMEND
    assert "Strongly recommend" in summary


def test_risk_synthesis_rejection_on_critical_risk(
    sample_deal, sample_dcf_result
):
    """Critical unresolved finding forces REJECT recommendation."""
    engine = RiskSynthesisEngine()
    crit = RiskFinding(
        category=RiskCategory.TITLE_AND_LEGAL,
        severity=RiskSeverity.CRITICAL,
        title="Fraudulent Forged Deed Detected",
        description="Recorded conveyance DOC-123 exhibits forged notary acknowledgement.",
        evidence_citation="County Grand Jury Indictment 2026-CR-012",
        impact_summary="Title void ab initio; property ownership disputed.",
        confirmed_by_role=AgentRole.MUNICIPAL_DEED_AUDITOR,
    )

    rec, conditions, summary = engine.synthesize_decision(
        deal=sample_deal,
        metrics=sample_dcf_result.metrics,
        risk_findings=[crit],
        checklist=[],
        stress_scenarios=[],
    )
    assert rec == MemoRecommendation.REJECT
    assert "Critical" in summary


# -------------------------------------------------------------------------
# Swarm Orchestrator Full Lifecycle Tests
# -------------------------------------------------------------------------


def test_swarm_orchestrator_full_workflow(sample_deal):
    """End-to-end multi-agent diligence DAG workflow execution."""
    orchestrator = SwarmOrchestrator()

    # 1. Initialize workflow
    state = orchestrator.initialize_workflow(sample_deal)
    assert state.deal_id == sample_deal.id
    assert len(state.tasks) == 6
    assert state.is_terminal is False

    # 2. Advance through all 6 stages sequentially
    for step in range(len(state.tasks)):
        state = orchestrator.advance_workflow(state.id)

    # 3. Workflow should reach terminal state
    assert state.is_terminal is True
    assert len(state.completed_roles) == 6
    assert len(state.audit_trail) == 6
    assert state.final_memo_id is not None

    # 4. Underwriting memo generated
    memo = orchestrator.generate_underwriting_memo(sample_deal.id)
    assert memo.deal_id == sample_deal.id
    assert memo.valuation_summary.levered_irr > 0.0
    assert len(memo.sign_offs) == 5
    assert len(memo.stress_scenarios) >= 1

    # 5. Check events logged on the bus
    history = orchestrator.event_bus.get_history(deal_id=sample_deal.id)
    assert len(history) >= 7  # WORKFLOW_STARTED + 6 tasks + MEMO_GENERATED

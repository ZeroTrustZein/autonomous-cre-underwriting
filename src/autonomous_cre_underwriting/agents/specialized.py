"""Specialized diligence agents implementing AgentProtocol for all 6 swarm roles."""

from typing import List, Optional

from autonomous_cre_underwriting.agents.base import BaseAgent
from autonomous_cre_underwriting.engine.dcf import DCFEngine
from autonomous_cre_underwriting.engine.graph import KnowledgeGraphEngine
from autonomous_cre_underwriting.engine.rag import HybridRAGEngine
from autonomous_cre_underwriting.engine.risk import RiskSynthesisEngine
from autonomous_cre_underwriting.mcp.municipal_deed import DeedIngestor
from autonomous_cre_underwriting.mcp.sec_edgar import SECIngestor
from autonomous_cre_underwriting.types.agents import (
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)
from autonomous_cre_underwriting.types.financial import (
    DCFParameters,
    DCFValuationResult,
    FinancingAssumptions,
)
from autonomous_cre_underwriting.types.ingestion import OfferingMemorandum
from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
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
from autonomous_cre_underwriting.types.risk import (
    DiligenceChecklistItem,
    MemoRecommendation,
    RiskFinding,
    SignOff,
    StressScenario,
)


class IngestionCoordinatorAgent(BaseAgent):
    """Coordinates intake of municipal deeds, SEC filings, and broker Offering Memorandums."""

    def __init__(
        self,
        rag_engine: Optional[HybridRAGEngine] = None,
        deed_ingestor: Optional[DeedIngestor] = None,
        sec_ingestor: Optional[SECIngestor] = None,
    ) -> None:
        super().__init__(AgentRole.INGESTION_COORDINATOR)
        self.rag_engine = rag_engine if rag_engine is not None else HybridRAGEngine()
        self.deed_ingestor = deed_ingestor if deed_ingestor is not None else DeedIngestor()
        self.sec_ingestor = sec_ingestor if sec_ingestor is not None else SECIngestor()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        deal_id = task.deal_id
        om: Optional[OfferingMemorandum] = task.input_artifacts.get("offering_memorandum")
        chunks_indexed = 0

        if om is not None:
            chunks_indexed = self.rag_engine.index_document(om)

        task.output_artifacts = {
            "deal_id": deal_id,
            "chunks_indexed": chunks_indexed,
            "has_om": om is not None,
            "status": "ingestion_completed",
        }
        task.status = TaskStatus.COMPLETED
        return task


class MunicipalDeedAuditorAgent(BaseAgent):
    """Audits municipal recorded deeds, traces title continuity, and maps liens/encumbrances."""

    def __init__(
        self,
        deed_ingestor: Optional[DeedIngestor] = None,
        graph_engine: Optional[KnowledgeGraphEngine] = None,
    ) -> None:
        super().__init__(AgentRole.MUNICIPAL_DEED_AUDITOR)
        self.deed_ingestor = deed_ingestor if deed_ingestor is not None else DeedIngestor()
        self.graph_engine = graph_engine if graph_engine is not None else KnowledgeGraphEngine()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        apn = task.input_artifacts.get("apn", "")
        county = task.input_artifacts.get("county", "")
        state = task.input_artifacts.get("state", "tx")
        reported_seller = task.input_artifacts.get("reported_seller", "")

        deeds = self.deed_ingestor.fetch_deed_records(apn=apn, county=county, state=state)
        audit_res = self.deed_ingestor.audit_chain_of_title(apn=apn)
        verified = True
        if reported_seller:
            verified = self.deed_ingestor.verify_chain_of_title(
                apn=apn, reported_seller=reported_seller
            )

        # Populate knowledge graph nodes and relations if deeds exist
        if self.graph_engine is not None:
            for d in deeds:
                self.graph_engine.upsert_entity(
                    GraphEntity(
                        entity_id=f"owner-{d.document_number}",
                        entity_type=EntityType.SPONSOR,
                        label=d.grantee,
                        properties={"deed_number": d.document_number, "apn": apn},
                    ),
                    deal_id=task.deal_id,
                )

        task.output_artifacts = {
            "apn": apn,
            "deeds_found": len(deeds),
            "chain_valid": audit_res["chain_valid"],
            "seller_verified": verified,
            "issues": audit_res["issues"],
            "latest_owner": audit_res.get("latest_owner", ""),
        }
        task.status = TaskStatus.COMPLETED
        return task


class SECDiligenceAnalystAgent(BaseAgent):
    """Analyzes SEC EDGAR filings for sponsor and key tenants, assessing debt reset & credit risk."""

    def __init__(self, sec_ingestor: Optional[SECIngestor] = None) -> None:
        super().__init__(AgentRole.SEC_DILIGENCE_ANALYST)
        self.sec_ingestor = sec_ingestor if sec_ingestor is not None else SECIngestor()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        sponsor_name = task.input_artifacts.get("sponsor_name", "")
        cik = task.input_artifacts.get("cik", sponsor_name)

        credit_assessment = self.sec_ingestor.assess_sponsor_credit(cik)
        filings = self.sec_ingestor.search_filings(cik)

        task.output_artifacts = {
            "sponsor": sponsor_name,
            "cik": cik,
            "filings_count": len(filings),
            "credit_risk_level": credit_assessment["credit_risk_level"],
            "refinancing_risk_flag": credit_assessment["refinancing_risk_flag"],
            "high_severity_mentions_count": len(credit_assessment["high_severity_mentions"]),
        }
        task.status = TaskStatus.COMPLETED
        return task


def _create_fallback_deal(deal_id: str, purchase_price: float, in_place_noi: float) -> PropertyDeal:
    """Construct minimal placeholder PropertyDeal when not provided in task artifacts."""
    target_price = purchase_price or 10000000.0
    return PropertyDeal(
        id=deal_id,
        title=f"Deal {deal_id}",
        property_type=PropertyType.MULTIFAMILY,
        status=DealStatus.UNDERWRITING,
        address=PropertyAddress(
            street="100 Main St",
            city="Austin",
            state="tx",
            postal_code="78701",
            county="Travis",
            apn="00-0000",
        ),
        physical=PropertyPhysical(
            gross_square_feet=50000,
            rentable_square_feet=45000,
            year_built=2020,
            site_area_acres=2.5,
        ),
        unit_mix=UnitMix(
            items=[
                UnitSpec(
                    unit_type="1B",
                    count=50,
                    square_feet=800,
                    in_place_rent=1500,
                    market_rent=1600,
                )
            ]
        ),
        asking_price=target_price * 1.05,
        target_purchase_price=target_price,
        in_place_noi=in_place_noi or 600000.0,
        sponsor_name="Apex Capital Partners",
    )


class DCFValuationEngineerAgent(BaseAgent):
    """Constructs multi-year pro-forma cash flows, evaluates debt sizing, and produces sensitivity matrices."""

    def __init__(self, dcf_engine: Optional[DCFEngine] = None) -> None:
        super().__init__(AgentRole.DCF_VALUATION_ENGINEER)
        self.dcf_engine = dcf_engine if dcf_engine is not None else DCFEngine()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        deal: Optional[PropertyDeal] = task.input_artifacts.get("deal")
        purchase_price = float(task.input_artifacts.get("purchase_price", 0.0))
        in_place_noi = float(task.input_artifacts.get("in_place_noi", 0.0))

        if deal is None:
            deal = _create_fallback_deal(task.deal_id, purchase_price, in_place_noi)

        financing: Optional[FinancingAssumptions] = task.input_artifacts.get("financing")
        if financing is None:
            financing = self.dcf_engine.create_default_financing(deal)

        params: Optional[DCFParameters] = task.input_artifacts.get("parameters")
        if params is None:
            params = self.dcf_engine.create_default_parameters(deal)

        dcf_result: DCFValuationResult = self.dcf_engine.compute_valuation(
            deal=deal,
            parameters=params,
            financing=financing,
            t12=deal.historical_financials[-1] if deal.historical_financials else None,
        )

        task.output_artifacts = {
            "levered_irr": dcf_result.metrics.levered_irr,
            "unlevered_irr": dcf_result.metrics.unlevered_irr,
            "equity_multiple": dcf_result.metrics.equity_multiple,
            "net_present_value": dcf_result.metrics.net_present_value,
            "min_dscr": dcf_result.metrics.min_dscr_observed,
            "model_checksum": dcf_result.model_checksum,
            "valuation_result": dcf_result,
        }
        task.status = TaskStatus.COMPLETED
        return task


class CreditRiskUnderwriterAgent(BaseAgent):
    """Evaluates lender covenant compliance, applies downside stress shocks, and drafts checklist."""

    def __init__(
        self,
        risk_engine: Optional[RiskSynthesisEngine] = None,
        dcf_engine: Optional[DCFEngine] = None,
    ) -> None:
        super().__init__(AgentRole.CREDIT_RISK_UNDERWRITER)
        self.risk_engine = risk_engine if risk_engine is not None else RiskSynthesisEngine()
        self.dcf_engine = dcf_engine if dcf_engine is not None else DCFEngine()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        deal: Optional[PropertyDeal] = task.input_artifacts.get("deal")
        dcf_result: Optional[DCFValuationResult] = task.input_artifacts.get("valuation_result")

        # Find DCF result from prior tasks if not in input
        if dcf_result is None:
            for t in context.tasks:
                if (
                    t.role == AgentRole.DCF_VALUATION_ENGINEER
                    and "valuation_result" in t.output_artifacts
                ):
                    dcf_result = t.output_artifacts["valuation_result"]
                    break

        checklist_items: List[DiligenceChecklistItem] = []
        stress_scenarios: List[StressScenario] = []

        if deal is not None and dcf_result is not None:
            covenants = self.risk_engine.evaluate_covenant_compliance(
                deal=deal,
                financing=dcf_result.financing,
                dcf_result=dcf_result,
            )
            standard_chk = self.risk_engine.build_standard_checklist(deal=deal)
            checklist_items = covenants + standard_chk

            # Run standard stress scenarios
            stress_scenarios = self.dcf_engine.create_standard_stress_scenarios(
                deal=deal, dcf_result=dcf_result
            )

        task.output_artifacts = {
            "checklist_count": len(checklist_items),
            "covenants_passed": all(item.status.value == "pass" for item in checklist_items),
            "stress_scenarios_count": len(stress_scenarios),
            "checklist_items": checklist_items,
            "stress_scenarios": stress_scenarios,
        }
        task.status = TaskStatus.COMPLETED
        return task


class InvestmentCommitteeChairAgent(BaseAgent):
    """Synthesizes all multi-agent diligence findings and executes final IC sign-off decision."""

    def __init__(self, risk_engine: Optional[RiskSynthesisEngine] = None) -> None:
        super().__init__(AgentRole.INVESTMENT_COMMITTEE_CHAIR)
        self.risk_engine = risk_engine if risk_engine is not None else RiskSynthesisEngine()

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        deal: Optional[PropertyDeal] = task.input_artifacts.get("deal")
        dcf_result: Optional[DCFValuationResult] = task.input_artifacts.get("valuation_result")
        checklist: List[DiligenceChecklistItem] = task.input_artifacts.get("checklist_items", [])
        stress: List[StressScenario] = task.input_artifacts.get("stress_scenarios", [])
        risk_findings: List[RiskFinding] = task.input_artifacts.get("risk_findings", [])

        # Recover artifacts from context if missing
        if dcf_result is None or not checklist or not stress:
            for t in context.tasks:
                if (
                    t.role == AgentRole.DCF_VALUATION_ENGINEER
                    and "valuation_result" in t.output_artifacts
                ):
                    dcf_result = t.output_artifacts["valuation_result"]
                elif t.role == AgentRole.CREDIT_RISK_UNDERWRITER:
                    if "checklist_items" in t.output_artifacts:
                        checklist = t.output_artifacts["checklist_items"]
                    if "stress_scenarios" in t.output_artifacts:
                        stress = t.output_artifacts["stress_scenarios"]

        decision_ready = dcf_result is not None and len(checklist) > 0

        deal_title = deal.title if deal is not None else task.deal_id
        rationale = (
            f"IC Chair completed review for {deal_title} with {len(risk_findings)} risk findings."
        )

        # Sign-off record
        recommendation = MemoRecommendation.APPROVE_WITH_CONDITIONS
        if decision_ready and dcf_result is not None and dcf_result.metrics.levered_irr >= 0.14:
            recommendation = MemoRecommendation.STRONGLY_RECOMMEND

        sign_off = SignOff(
            role=self.role,
            recommendation=recommendation,
            rationale=rationale,
        )

        task.output_artifacts = {
            "decision_ready": decision_ready,
            "recommendation": sign_off.recommendation.value,
            "sign_off": sign_off,
        }
        task.status = TaskStatus.COMPLETED
        return task

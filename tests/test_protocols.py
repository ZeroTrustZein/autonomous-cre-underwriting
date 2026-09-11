"""Unit tests verifying runtime conformances to system protocol contracts."""

from typing import Any, Dict, List, Optional

from autonomous_cre_underwriting.agents import (
    CreditRiskUnderwriterAgent,
    DCFValuationEngineerAgent,
    IngestionCoordinatorAgent,
    InvestmentCommitteeChairAgent,
    MunicipalDeedAuditorAgent,
    SECDiligenceAnalystAgent,
)
from autonomous_cre_underwriting.engine import (
    DCFEngine,
    HybridRAGEngine,
    InMemoryEventBus,
    KnowledgeGraphEngine,
    SwarmOrchestrator,
)
from autonomous_cre_underwriting.mcp import DeedIngestor, SECIngestor
from autonomous_cre_underwriting.protocols import (
    AgentProtocol,
    DCFEngineProtocol,
    DeedIngestorProtocol,
    EventBusProtocol,
    EventHandlerProtocol,
    KnowledgeGraphStoreProtocol,
    RAGEngineProtocol,
    SECIngestorProtocol,
    SwarmOrchestratorProtocol,
)
from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
)
from autonomous_cre_underwriting.types.events import SwarmEvent
from autonomous_cre_underwriting.types.financial import (
    DCFParameters,
    DCFValuationResult,
    FinancingAssumptions,
)
from autonomous_cre_underwriting.types.ingestion import (
    DeedRecord,
    DocumentChunk,
    OfferingMemorandum,
    SECFiling,
)
from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
)
from autonomous_cre_underwriting.types.property import HistoricalFinancials, PropertyDeal
from autonomous_cre_underwriting.types.risk import UnderwritingMemo


class MockDeedIngestor:
    def fetch_deed_records(self, apn: str, county: str, state: str) -> List[DeedRecord]:
        return []

    def verify_chain_of_title(self, apn: str, reported_seller: str) -> bool:
        return True


class MockSECIngestor:
    def search_filings(
        self, cik_or_ticker: str, form_types: Optional[List[str]] = None
    ) -> List[SECFiling]:
        return []

    def extract_risk_factors(self, accession_number: str) -> List[Dict[str, Any]]:
        return []


class MockEventBus:
    def publish(self, event: SwarmEvent) -> None:
        pass

    def subscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        pass

    def unsubscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        pass


class MockKnowledgeGraphStore:
    def upsert_entity(self, entity: GraphEntity) -> None:
        pass

    def upsert_relation(self, relation: GraphRelation) -> None:
        pass

    def get_graph_for_deal(self, deal_id: str) -> KnowledgeGraph:
        return KnowledgeGraph()

    def find_entities_by_type(self, entity_type: EntityType) -> List[GraphEntity]:
        return []


class MockRAGEngine:
    def index_document(self, memorandum: OfferingMemorandum) -> int:
        return 0

    def hybrid_search(self, query: str, deal_id: str, top_k: int = 5) -> List[DocumentChunk]:
        return []


class MockDCFEngine:
    def compute_valuation(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials] = None,
    ) -> DCFValuationResult:
        raise NotImplementedError()


class MockAgent:
    @property
    def role(self) -> AgentRole:
        return AgentRole.MUNICIPAL_DEED_AUDITOR

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        return task

    def produce_audit_entry(self, task: AgentTask, action: str, rationale: str) -> AgentAuditEntry:
        return AgentAuditEntry(
            task_id=task.id,
            role=self.role,
            action_taken=action,
            justification=rationale,
            input_hash="test",
            output_summary="test",
        )


class MockSwarmOrchestrator:
    def initialize_workflow(self, deal: PropertyDeal) -> SwarmWorkflowState:
        return SwarmWorkflowState(deal_id=deal.id)

    def advance_workflow(self, workflow_id: str) -> SwarmWorkflowState:
        return SwarmWorkflowState(deal_id="test")

    def generate_underwriting_memo(self, deal_id: str) -> UnderwritingMemo:
        raise NotImplementedError()


def test_protocol_conformances():
    """Verify mock implementations satisfy runtime protocol definitions."""
    assert isinstance(MockDeedIngestor(), DeedIngestorProtocol)
    assert isinstance(MockSECIngestor(), SECIngestorProtocol)
    assert isinstance(MockEventBus(), EventBusProtocol)
    assert isinstance(MockKnowledgeGraphStore(), KnowledgeGraphStoreProtocol)
    assert isinstance(MockRAGEngine(), RAGEngineProtocol)
    assert isinstance(MockDCFEngine(), DCFEngineProtocol)
    assert isinstance(MockAgent(), AgentProtocol)
    assert isinstance(MockSwarmOrchestrator(), SwarmOrchestratorProtocol)


def test_real_engine_protocol_conformances():
    """Verify production engine implementations satisfy runtime protocol definitions."""
    assert isinstance(EventBusProtocol, type)
    assert isinstance(InMemoryEventBus(), EventBusProtocol)
    assert isinstance(KnowledgeGraphEngine(), KnowledgeGraphStoreProtocol)
    assert isinstance(HybridRAGEngine(), RAGEngineProtocol)
    assert isinstance(DCFEngine(), DCFEngineProtocol)
    assert isinstance(SwarmOrchestrator(), SwarmOrchestratorProtocol)
    assert isinstance(DeedIngestor(), DeedIngestorProtocol)
    assert isinstance(SECIngestor(), SECIngestorProtocol)
    assert isinstance(IngestionCoordinatorAgent(), AgentProtocol)
    assert isinstance(MunicipalDeedAuditorAgent(), AgentProtocol)
    assert isinstance(SECDiligenceAnalystAgent(), AgentProtocol)
    assert isinstance(DCFValuationEngineerAgent(), AgentProtocol)
    assert isinstance(CreditRiskUnderwriterAgent(), AgentProtocol)
    assert isinstance(InvestmentCommitteeChairAgent(), AgentProtocol)

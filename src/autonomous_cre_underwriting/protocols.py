"""Protocol contracts and interfaces for the autonomous CRE underwriting system."""

from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

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


@runtime_checkable
class EventHandlerProtocol(Protocol):
    """Callback hook handling dispatched swarm events."""

    def __call__(self, event: SwarmEvent) -> None:
        """Handle incoming event."""
        ...


@runtime_checkable
class EventBusProtocol(Protocol):
    """Publish-subscribe communication bus for agent swarm coordination."""

    def publish(self, event: SwarmEvent) -> None:
        """Publish an event to the bus."""
        ...

    def subscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        """Subscribe a handler callback to a specific event topic."""
        ...

    def unsubscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        """Remove an existing subscription."""
        ...


@runtime_checkable
class DeedIngestorProtocol(Protocol):
    """MCP client interface for municipal deed retrieval and validation."""

    def fetch_deed_records(self, apn: str, county: str, state: str) -> List[DeedRecord]:
        """Query county recorder for conveyance history given parcel identifiers."""
        ...

    def verify_chain_of_title(self, apn: str, reported_seller: str) -> bool:
        """Verify whether the reported seller matches the recorded grantee in the latest deed."""
        ...


@runtime_checkable
class SECIngestorProtocol(Protocol):
    """MCP client interface for SEC EDGAR 10-K/10-Q/8-K extraction."""

    def search_filings(
        self, cik_or_ticker: str, form_types: Optional[List[str]] = None
    ) -> List[SECFiling]:
        """Fetch SEC filings for sponsor or anchor tenant."""
        ...

    def extract_risk_factors(self, accession_number: str) -> List[Dict[str, Any]]:
        """Parse Item 1A Risk Factors and relevant lease disclosures."""
        ...


@runtime_checkable
class KnowledgeGraphStoreProtocol(Protocol):
    """Storage and traversal interface for property diligence knowledge graph."""

    def upsert_entity(self, entity: GraphEntity) -> None:
        """Insert or update an entity node."""
        ...

    def upsert_relation(self, relation: GraphRelation) -> None:
        """Insert or update a relation edge."""
        ...

    def get_graph_for_deal(self, deal_id: str) -> KnowledgeGraph:
        """Extract connected subgraph for a target property deal."""
        ...

    def find_entities_by_type(self, entity_type: EntityType) -> List[GraphEntity]:
        """Filter graph nodes by taxonomy category."""
        ...


@runtime_checkable
class RAGEngineProtocol(Protocol):
    """Hybrid dense vector and graph RAG search over offering memorandums."""

    def index_document(self, memorandum: OfferingMemorandum) -> int:
        """Chunk, embed, and store an offering memorandum, returning chunk count."""
        ...

    def hybrid_search(
        self, query: str, deal_id: str, top_k: int = 5
    ) -> List[DocumentChunk]:
        """Retrieve relevant context combining semantic dense search and graph filters."""
        ...


@runtime_checkable
class DCFEngineProtocol(Protocol):
    """Financial modeling engine producing audit-ready DCF schedules and metrics."""

    def compute_valuation(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials] = None,
    ) -> DCFValuationResult:
        """Calculate multi-year pro-forma, IRR, NPV, DSCR, and sensitivity table."""
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """Interface for specialized autonomous diligence agents."""

    @property
    def role(self) -> AgentRole:
        """Agent role identifier."""
        ...

    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        """Execute diligence assignment, returning completed or failed task with artifacts."""
        ...

    def produce_audit_entry(self, task: AgentTask, action: str, rationale: str) -> AgentAuditEntry:
        """Produce cryptographic-ready audit trail record for an action."""
        ...


@runtime_checkable
class SwarmOrchestratorProtocol(Protocol):
    """Workflow coordinator managing stage transitions, agent dispatch, and final memo."""

    def initialize_workflow(self, deal: PropertyDeal) -> SwarmWorkflowState:
        """Bootstrap workflow state for a new deal."""
        ...

    def advance_workflow(self, workflow_id: str) -> SwarmWorkflowState:
        """Progress next pending task in DAG sequence."""
        ...

    def generate_underwriting_memo(self, deal_id: str) -> UnderwritingMemo:
        """Synthesize all artifacts into final audit-ready IC memo."""
        ...

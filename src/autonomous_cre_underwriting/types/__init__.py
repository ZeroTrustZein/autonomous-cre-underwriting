"""Domain types and schemas for autonomous CRE underwriting."""

from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentMessage,
    AgentRole,
    AgentState,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)
from autonomous_cre_underwriting.types.base import BaseEntity, generate_uuid, utc_now
from autonomous_cre_underwriting.types.events import (
    EventPriority,
    EventType,
    SwarmEvent,
)
from autonomous_cre_underwriting.types.financial import (
    AnnualCashFlow,
    DCFParameters,
    DCFValuationResult,
    FinancingAssumptions,
    LoanAmortizationRow,
    LoanType,
    SensitivityMatrix,
    SensitivityScenario,
    ValuationMetrics,
)
from autonomous_cre_underwriting.types.ingestion import (
    DeedRecord,
    DeedType,
    DocumentChunk,
    IngestionJob,
    IngestionSourceType,
    IngestionStatus,
    OfferingMemorandum,
    SECFiling,
    SECFilingType,
    SECRiskMention,
    SECRiskTopic,
)
from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
    RelationType,
)
from autonomous_cre_underwriting.types.property import (
    DealStatus,
    HistoricalFinancials,
    OperatingExpenses,
    PropertyAddress,
    PropertyDeal,
    PropertyPhysical,
    PropertyType,
    UnitMix,
    UnitSpec,
)
from autonomous_cre_underwriting.types.risk import (
    ChecklistStatus,
    DiligenceChecklistItem,
    MemoRecommendation,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
    SignOff,
    StressScenario,
    UnderwritingMemo,
)

__all__ = [
    # Base
    "BaseEntity",
    "generate_uuid",
    "utc_now",
    # Property
    "PropertyType",
    "DealStatus",
    "PropertyAddress",
    "UnitSpec",
    "UnitMix",
    "PropertyPhysical",
    "OperatingExpenses",
    "HistoricalFinancials",
    "PropertyDeal",
    # Ingestion
    "IngestionSourceType",
    "IngestionStatus",
    "DeedType",
    "DeedRecord",
    "SECFilingType",
    "SECRiskTopic",
    "SECRiskMention",
    "SECFiling",
    "DocumentChunk",
    "OfferingMemorandum",
    "IngestionJob",
    # Knowledge Graph
    "EntityType",
    "RelationType",
    "GraphEntity",
    "GraphRelation",
    "KnowledgeGraph",
    # Events
    "EventType",
    "EventPriority",
    "SwarmEvent",
    # Agents
    "AgentRole",
    "AgentState",
    "TaskStatus",
    "AgentTask",
    "AgentMessage",
    "AgentAuditEntry",
    "SwarmWorkflowState",
    # Financial
    "LoanType",
    "FinancingAssumptions",
    "LoanAmortizationRow",
    "DCFParameters",
    "AnnualCashFlow",
    "ValuationMetrics",
    "SensitivityScenario",
    "SensitivityMatrix",
    "DCFValuationResult",
    # Risk
    "RiskCategory",
    "RiskSeverity",
    "RiskFinding",
    "ChecklistStatus",
    "DiligenceChecklistItem",
    "StressScenario",
    "MemoRecommendation",
    "SignOff",
    "UnderwritingMemo",
]

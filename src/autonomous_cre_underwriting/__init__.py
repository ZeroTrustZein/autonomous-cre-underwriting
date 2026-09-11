"""Autonomous CRE Underwriting Swarm.

An event-driven multi-agent diligence platform providing custom MCP servers
for municipal deed and SEC filing ingestion, hybrid vector-graph RAG over
property offering memorandums, and an autonomous financial analyst swarm that
generates audit-ready DCF valuation models and portfolio risk memos.
"""

__version__ = "0.1.0"

from autonomous_cre_underwriting.types import (
    # Property models
    DealStatus,
    HistoricalFinancials,
    OperatingExpenses,
    PropertyAddress,
    PropertyDeal,
    PropertyPhysical,
    PropertyType,
    UnitMix,
    UnitSpec,
    # Ingestion models
    DeedRecord,
    DeedType,
    DocumentChunk,
    IngestionJob,
    IngestionSourceType,
    IngestionStatus,
    OfferingMemorandum,
    SECFiling,
    SECFilingType,
    # Knowledge Graph models
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
    RelationType,
    # Event models
    EventPriority,
    EventType,
    SwarmEvent,
    # Agent models
    AgentAuditEntry,
    AgentMessage,
    AgentRole,
    AgentState,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
    # Financial & DCF models
    AnnualCashFlow,
    DCFParameters,
    DCFValuationResult,
    FinancingAssumptions,
    LoanAmortizationRow,
    LoanType,
    SensitivityMatrix,
    SensitivityScenario,
    ValuationMetrics,
    # Risk & Memo models
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
    "__version__",
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
    "SECFiling",
    "DocumentChunk",
    "OfferingMemorandum",
    "IngestionJob",
    # Graph
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
    # Risk & Memo
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

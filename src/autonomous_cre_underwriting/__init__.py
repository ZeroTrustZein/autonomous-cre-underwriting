"""Autonomous CRE Underwriting Swarm.

An event-driven multi-agent diligence platform providing custom MCP servers
for municipal deed and SEC filing ingestion, hybrid vector-graph RAG over
property offering memorandums, and an autonomous financial analyst swarm that
generates audit-ready DCF valuation models and portfolio risk memos.
"""

__version__ = "0.1.0"

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
from autonomous_cre_underwriting.mcp import (
    DeedIngestor,
    MCPRequest,
    MCPResponse,
    MCPServerBase,
    MCPTool,
    MunicipalDeedMCPServer,
    SECEdgarMCPServer,
    SECIngestor,
)
from autonomous_cre_underwriting.portfolio import (
    ConcentrationMetrics,
    DealRollupItem,
    PortfolioStressImpact,
    PortfolioSummary,
    PortfolioUnderwriter,
    RuleCheckResult,
    UnderwritingCriteria,
    UnderwritingRulesEngine,
)
from autonomous_cre_underwriting.reporting import (
    AuditTrailVerifier,
    DCFScheduleExporter,
    MemoExporter,
)
from autonomous_cre_underwriting.storage import DealRepository
from autonomous_cre_underwriting.types import (
    # Agent models
    AgentAuditEntry,
    AgentMessage,
    AgentRole,
    AgentState,
    AgentTask,
    # Financial & DCF models
    AnnualCashFlow,
    # Risk & Memo models
    ChecklistStatus,
    DCFParameters,
    DCFValuationResult,
    # Property models
    DealStatus,
    # Ingestion models
    DeedRecord,
    DeedType,
    DiligenceChecklistItem,
    DocumentChunk,
    # Knowledge Graph models
    EntityType,
    # Event models
    EventPriority,
    EventType,
    FinancingAssumptions,
    GraphEntity,
    GraphRelation,
    HistoricalFinancials,
    IngestionJob,
    IngestionSourceType,
    IngestionStatus,
    KnowledgeGraph,
    LoanAmortizationRow,
    LoanType,
    MemoRecommendation,
    OfferingMemorandum,
    OperatingExpenses,
    PropertyAddress,
    PropertyDeal,
    PropertyPhysical,
    PropertyType,
    RelationType,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
    SECFiling,
    SECFilingType,
    SensitivityMatrix,
    SensitivityScenario,
    SignOff,
    StressScenario,
    SwarmEvent,
    SwarmWorkflowState,
    TaskStatus,
    UnderwritingMemo,
    UnitMix,
    UnitSpec,
    ValuationMetrics,
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
    # Core Engines
    "DCFEngine",
    "compute_irr",
    "compute_npv",
    "generate_loan_amortization_schedule",
    "compute_remaining_loan_balance",
    "KnowledgeGraphEngine",
    "HybridRAGEngine",
    "chunk_text",
    "compute_dense_embedding",
    "cosine_similarity",
    "InMemoryEventBus",
    "DeadLetterEntry",
    "RiskSynthesisEngine",
    "SwarmOrchestrator",
    # MCP Subsystem
    "MCPTool",
    "MCPRequest",
    "MCPResponse",
    "MCPServerBase",
    "DeedIngestor",
    "MunicipalDeedMCPServer",
    "SECIngestor",
    "SECEdgarMCPServer",
    # Agent Swarm Subsystem
    "BaseAgent",
    "IngestionCoordinatorAgent",
    "MunicipalDeedAuditorAgent",
    "SECDiligenceAnalystAgent",
    "DCFValuationEngineerAgent",
    "CreditRiskUnderwriterAgent",
    "InvestmentCommitteeChairAgent",
    "create_agent_swarm",
    # Portfolio Subsystem
    "DealRollupItem",
    "PortfolioSummary",
    "ConcentrationMetrics",
    "PortfolioStressImpact",
    "PortfolioUnderwriter",
    "UnderwritingCriteria",
    "RuleCheckResult",
    "UnderwritingRulesEngine",
    # Reporting Subsystem
    "DCFScheduleExporter",
    "MemoExporter",
    "AuditTrailVerifier",
    # Storage Subsystem
    "DealRepository",
]

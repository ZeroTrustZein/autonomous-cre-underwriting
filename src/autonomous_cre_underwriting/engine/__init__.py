"""Core algorithms and calculation engines for autonomous CRE underwriting."""

from autonomous_cre_underwriting.engine.dcf import (
    DCFEngine,
    compute_irr,
    compute_npv,
    compute_remaining_loan_balance,
    generate_loan_amortization_schedule,
)
from autonomous_cre_underwriting.engine.event_bus import (
    DeadLetterEntry,
    InMemoryEventBus,
)
from autonomous_cre_underwriting.engine.graph import KnowledgeGraphEngine
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.engine.rag import (
    HybridRAGEngine,
    chunk_text,
    compute_dense_embedding,
    cosine_similarity,
)
from autonomous_cre_underwriting.engine.risk import RiskSynthesisEngine

__all__ = [
    # DCF Engine
    "DCFEngine",
    "compute_irr",
    "compute_npv",
    "generate_loan_amortization_schedule",
    "compute_remaining_loan_balance",
    # Knowledge Graph Engine
    "KnowledgeGraphEngine",
    # Hybrid RAG Engine
    "HybridRAGEngine",
    "chunk_text",
    "compute_dense_embedding",
    "cosine_similarity",
    # Event Bus
    "InMemoryEventBus",
    "DeadLetterEntry",
    # Risk Synthesis Engine
    "RiskSynthesisEngine",
    # Swarm Orchestrator
    "SwarmOrchestrator",
]

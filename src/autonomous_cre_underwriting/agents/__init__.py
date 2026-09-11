"""Autonomous diligence agents implementing AgentProtocol for CRE underwriting."""

from autonomous_cre_underwriting.agents.base import BaseAgent
from autonomous_cre_underwriting.agents.specialized import (
    CreditRiskUnderwriterAgent,
    DCFValuationEngineerAgent,
    IngestionCoordinatorAgent,
    InvestmentCommitteeChairAgent,
    MunicipalDeedAuditorAgent,
    SECDiligenceAnalystAgent,
)
from autonomous_cre_underwriting.agents.swarm import create_agent_swarm

__all__ = [
    "BaseAgent",
    "IngestionCoordinatorAgent",
    "MunicipalDeedAuditorAgent",
    "SECDiligenceAnalystAgent",
    "DCFValuationEngineerAgent",
    "CreditRiskUnderwriterAgent",
    "InvestmentCommitteeChairAgent",
    "create_agent_swarm",
]

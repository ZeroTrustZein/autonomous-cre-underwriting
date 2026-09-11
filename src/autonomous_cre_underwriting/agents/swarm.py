"""Agent swarm assembly and registration factory for autonomous diligence orchestration."""

from typing import Dict, Optional

from autonomous_cre_underwriting.agents.base import BaseAgent
from autonomous_cre_underwriting.agents.specialized import (
    CreditRiskUnderwriterAgent,
    DCFValuationEngineerAgent,
    IngestionCoordinatorAgent,
    InvestmentCommitteeChairAgent,
    MunicipalDeedAuditorAgent,
    SECDiligenceAnalystAgent,
)
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.mcp.municipal_deed import DeedIngestor
from autonomous_cre_underwriting.mcp.sec_edgar import SECIngestor
from autonomous_cre_underwriting.types.agents import AgentRole


def create_agent_swarm(
    orchestrator: Optional[SwarmOrchestrator] = None,
    deed_ingestor: Optional[DeedIngestor] = None,
    sec_ingestor: Optional[SECIngestor] = None,
) -> Dict[AgentRole, BaseAgent]:
    """Instantiate and configure all 6 specialized diligence agents, registering them with an orchestrator."""
    orch = orchestrator if orchestrator is not None else SwarmOrchestrator()
    d_ingestor = deed_ingestor if deed_ingestor is not None else DeedIngestor()
    s_ingestor = sec_ingestor if sec_ingestor is not None else SECIngestor()

    agents: Dict[AgentRole, BaseAgent] = {
        AgentRole.INGESTION_COORDINATOR: IngestionCoordinatorAgent(
            rag_engine=orch.rag_engine,
            deed_ingestor=d_ingestor,
            sec_ingestor=s_ingestor,
        ),
        AgentRole.MUNICIPAL_DEED_AUDITOR: MunicipalDeedAuditorAgent(
            deed_ingestor=d_ingestor,
            graph_engine=orch.graph_engine,
        ),
        AgentRole.SEC_DILIGENCE_ANALYST: SECDiligenceAnalystAgent(
            sec_ingestor=s_ingestor,
        ),
        AgentRole.DCF_VALUATION_ENGINEER: DCFValuationEngineerAgent(
            dcf_engine=orch.dcf_engine,
        ),
        AgentRole.CREDIT_RISK_UNDERWRITER: CreditRiskUnderwriterAgent(
            risk_engine=orch.risk_engine,
            dcf_engine=orch.dcf_engine,
        ),
        AgentRole.INVESTMENT_COMMITTEE_CHAIR: InvestmentCommitteeChairAgent(
            risk_engine=orch.risk_engine,
        ),
    }

    for agent in agents.values():
        orch.register_agent(agent)

    return agents

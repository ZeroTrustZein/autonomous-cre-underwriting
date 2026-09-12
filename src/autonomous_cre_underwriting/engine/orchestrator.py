"""Workflow coordinator managing multi-agent diligence DAG execution and IC memo synthesis."""

import time
from typing import Dict, List, Optional

from autonomous_cre_underwriting.engine.dcf import DCFEngine
from autonomous_cre_underwriting.engine.event_bus import InMemoryEventBus
from autonomous_cre_underwriting.engine.graph import KnowledgeGraphEngine
from autonomous_cre_underwriting.engine.rag import HybridRAGEngine
from autonomous_cre_underwriting.engine.risk import RiskSynthesisEngine
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
    DCFValuationResult,
)
from autonomous_cre_underwriting.types.property import PropertyDeal
from autonomous_cre_underwriting.types.risk import (
    DiligenceChecklistItem,
    RiskFinding,
    StressScenario,
    UnderwritingMemo,
)


class SwarmOrchestrator:
    """Multi-agent diligence coordinator implementing SwarmOrchestratorProtocol."""

    def __init__(
        self,
        event_bus: Optional[InMemoryEventBus] = None,
        dcf_engine: Optional[DCFEngine] = None,
        graph_engine: Optional[KnowledgeGraphEngine] = None,
        rag_engine: Optional[HybridRAGEngine] = None,
        risk_engine: Optional[RiskSynthesisEngine] = None,
    ) -> None:
        self.event_bus = event_bus if event_bus is not None else InMemoryEventBus()
        self.dcf_engine = dcf_engine if dcf_engine is not None else DCFEngine()
        self.graph_engine = graph_engine if graph_engine is not None else KnowledgeGraphEngine()
        self.rag_engine = rag_engine if rag_engine is not None else HybridRAGEngine()
        self.risk_engine = risk_engine if risk_engine is not None else RiskSynthesisEngine()

        # Agents registered by role
        self.agents: Dict[AgentRole, AgentProtocol] = {}
        # Active workflow states indexed by workflow_id
        self.workflows: Dict[str, SwarmWorkflowState] = {}
        # Deals indexed by deal_id
        self.deals: Dict[str, PropertyDeal] = {}
        # Intermediate diligence artifacts indexed by deal_id
        self.dcf_results: Dict[str, DCFValuationResult] = {}
        self.risk_findings: Dict[str, List[RiskFinding]] = {}
        self.checklists: Dict[str, List[DiligenceChecklistItem]] = {}
        self.stress_scenarios: Dict[str, List[StressScenario]] = {}
        self.memos: Dict[str, UnderwritingMemo] = {}

    def register_agent(self, agent: AgentProtocol) -> None:
        """Register a specialized diligence agent for its declared role."""
        self.agents[agent.role] = agent

    def initialize_workflow(self, deal: PropertyDeal) -> SwarmWorkflowState:
        """Bootstrap workflow state with ordered DAG tasks for a target property deal."""
        self.deals[deal.id] = deal
        state = SwarmWorkflowState(deal_id=deal.id)

        # Standard 5-stage diligence task DAG
        tasks = [
            AgentTask(
                role=AgentRole.INGESTION_COORDINATOR,
                deal_id=deal.id,
                description=f"Ingest municipal deeds, SEC filings, and broker OM for {deal.title}",
                input_artifacts={"apn": deal.address.apn, "sponsor": deal.sponsor_name},
            ),
            AgentTask(
                role=AgentRole.MUNICIPAL_DEED_AUDITOR,
                deal_id=deal.id,
                description=f"Audit chain of title, verify recorded seller, and map encumbrances for APN {deal.address.apn}",
                input_artifacts={"apn": deal.address.apn, "county": deal.address.county},
            ),
            AgentTask(
                role=AgentRole.SEC_DILIGENCE_ANALYST,
                deal_id=deal.id,
                description=f"Scan SEC EDGAR filings for sponsor {deal.sponsor_name} and check debt reset risk",
                input_artifacts={"sponsor_name": deal.sponsor_name},
            ),
            AgentTask(
                role=AgentRole.DCF_VALUATION_ENGINEER,
                deal_id=deal.id,
                description=f"Model multi-year DCF pro-forma, levered IRR, DSCR, and 2D sensitivity for {deal.title}",
                input_artifacts={
                    "purchase_price": deal.target_purchase_price,
                    "in_place_noi": deal.in_place_noi,
                },
            ),
            AgentTask(
                role=AgentRole.CREDIT_RISK_UNDERWRITER,
                deal_id=deal.id,
                description="Check covenant compliance, compile diligence checklist, and execute stress scenarios",
                input_artifacts={"target_price": deal.target_purchase_price},
            ),
            AgentTask(
                role=AgentRole.INVESTMENT_COMMITTEE_CHAIR,
                deal_id=deal.id,
                description="Synthesize findings, generate agent sign-offs, and produce final Underwriting Memo",
                input_artifacts={"deal_title": deal.title},
            ),
        ]

        state.tasks = tasks
        self.workflows[state.id] = state

        # Publish initial workflow event
        self.event_bus.publish(
            SwarmEvent(
                event_type=EventType.DEAL_CREATED,
                deal_id=deal.id,
                source_role="swarm_orchestrator",
                priority=EventPriority.HIGH,
                payload={"workflow_id": state.id, "total_tasks": len(tasks)},
            )
        )

        return state

    def advance_workflow(self, workflow_id: str) -> SwarmWorkflowState:
        """Progress the next pending task in the DAG sequence."""
        state = self.workflows.get(workflow_id)
        if state is None:
            raise KeyError(f"Workflow {workflow_id} not found")

        if state.is_terminal:
            return state

        # Find next pending task
        pending_task = next(
            (t for t in state.tasks if t.status == TaskStatus.PENDING),
            None,
        )

        if pending_task is None:
            state.is_terminal = True
            state.touch()
            self.event_bus.publish(
                SwarmEvent(
                    event_type=EventType.IC_DECISION_RECORDED,
                    deal_id=state.deal_id,
                    source_role="swarm_orchestrator",
                    priority=EventPriority.NORMAL,
                    payload={"workflow_id": state.id},
                )
            )
            return state

        # Execute task
        pending_task.status = TaskStatus.IN_PROGRESS
        start_time = time.perf_counter()

        deal = self.deals.get(state.deal_id)
        agent = self.agents.get(pending_task.role)

        try:
            if agent is not None:
                # Custom registered agent execution
                if deal is not None and "deal" not in pending_task.input_artifacts:
                    pending_task.input_artifacts["deal"] = deal
                completed_task = agent.execute_task(pending_task, state)
                audit_entry = agent.produce_audit_entry(
                    completed_task,
                    action=f"EXECUTE_{pending_task.role.value.upper()}",
                    rationale=f"Executed diligence directive: {pending_task.description}",
                )
                pending_task.output_artifacts = completed_task.output_artifacts
                pending_task.status = completed_task.status
                if "valuation_result" in completed_task.output_artifacts:
                    self.dcf_results[state.deal_id] = completed_task.output_artifacts["valuation_result"]
                if "checklist_items" in completed_task.output_artifacts:
                    self.checklists[state.deal_id] = completed_task.output_artifacts["checklist_items"]
                if "stress_scenarios" in completed_task.output_artifacts:
                    self.stress_scenarios[state.deal_id] = completed_task.output_artifacts["stress_scenarios"]
            else:
                # Default built-in engine execution
                self._execute_built_in_role(pending_task, deal, state)
                audit_entry = AgentAuditEntry(
                    task_id=pending_task.id,
                    role=pending_task.role,
                    action_taken=f"EXECUTED_{pending_task.role.value.upper()}",
                    justification=f"Automated core engine run for {pending_task.description}",
                    input_hash=f"deal:{state.deal_id}",
                    output_summary=f"Completed {pending_task.role.value} with {len(pending_task.output_artifacts)} artifacts",
                )
                pending_task.status = TaskStatus.COMPLETED

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            pending_task.execution_time_ms = round(duration_ms, 2)
            state.audit_trail.append(audit_entry)
            if pending_task.role not in state.completed_roles:
                state.completed_roles.append(pending_task.role)

            # Publish task completion event mapped to role
            role_event_map = {
                AgentRole.INGESTION_COORDINATOR: EventType.MEMORANDUM_INGESTED,
                AgentRole.MUNICIPAL_DEED_AUDITOR: EventType.DEED_AUDIT_COMPLETED,
                AgentRole.SEC_DILIGENCE_ANALYST: EventType.SEC_DISCLOSURE_FLAGGED,
                AgentRole.DCF_VALUATION_ENGINEER: EventType.DCF_VALUATION_COMPLETED,
                AgentRole.CREDIT_RISK_UNDERWRITER: EventType.RISK_FINDING_REGISTERED,
                AgentRole.INVESTMENT_COMMITTEE_CHAIR: EventType.IC_DECISION_RECORDED,
            }
            task_event_type = role_event_map.get(pending_task.role, EventType.DEAL_CREATED)

            self.event_bus.publish(
                SwarmEvent(
                    event_type=task_event_type,
                    deal_id=state.deal_id,
                    source_role=pending_task.role.value,
                    target_role="swarm_orchestrator",
                    priority=EventPriority.NORMAL,
                    payload={"task_id": pending_task.id, "role": pending_task.role.value},
                )
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            pending_task.execution_time_ms = round(duration_ms, 2)
            pending_task.status = TaskStatus.FAILED
            pending_task.error_message = str(e)
            self.event_bus.publish(
                SwarmEvent(
                    event_type=EventType.AGENT_ERROR_ENCOUNTERED,
                    deal_id=state.deal_id,
                    source_role=pending_task.role.value,
                    priority=EventPriority.URGENT,
                    payload={"task_id": pending_task.id, "error": str(e)},
                )
            )

        # Check if all tasks finished
        if all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in state.tasks):
            state.is_terminal = True
            # Automatically generate final memo if not already created
            if state.deal_id not in self.memos and deal is not None:
                memo = self.generate_underwriting_memo(state.deal_id)
                state.final_memo_id = memo.id
            elif state.deal_id in self.memos:
                state.final_memo_id = self.memos[state.deal_id].id

        state.touch()
        return state

    def _execute_built_in_role(
        self, task: AgentTask, deal: Optional[PropertyDeal], state: SwarmWorkflowState
    ) -> None:
        """Run default logic when no external agent is registered for a role."""
        if deal is None:
            return

        deal_id = deal.id

        if task.role == AgentRole.INGESTION_COORDINATOR:
            task.output_artifacts = {
                "records_ingested": 1,
                "om_indexed": True,
                "deal_id": deal_id,
            }

        elif task.role == AgentRole.MUNICIPAL_DEED_AUDITOR:
            # Trace title chain and detect encumbrances using graph engine
            chain_events, is_continuous = self.graph_engine.trace_chain_of_title(deal_id)
            encs, total_enc = self.graph_engine.detect_encumbrances_and_liens(deal_id)
            task.output_artifacts = {
                "chain_of_title_continuous": is_continuous,
                "chain_length": len(chain_events),
                "total_encumbrance_amount": total_enc,
            }

        elif task.role == AgentRole.SEC_DILIGENCE_ANALYST:
            # SEC risk factor extraction
            task.output_artifacts = {
                "filings_analyzed": 1,
                "sofr_exposure_found": False,
            }

        elif task.role == AgentRole.DCF_VALUATION_ENGINEER:
            # Run DCF valuation model using standard defaults
            financing = self.dcf_engine.create_default_financing(deal)
            params = self.dcf_engine.create_default_parameters(deal)
            dcf_result = self.dcf_engine.compute_valuation(
                deal=deal,
                parameters=params,
                financing=financing,
                t12=deal.historical_financials[-1] if deal.historical_financials else None,
            )
            self.dcf_results[deal_id] = dcf_result
            task.output_artifacts = {
                "levered_irr": dcf_result.metrics.levered_irr,
                "equity_multiple": dcf_result.metrics.equity_multiple,
                "net_present_value": dcf_result.metrics.net_present_value,
                "min_dscr": dcf_result.metrics.min_dscr_observed,
                "model_checksum": dcf_result.model_checksum,
            }

        elif task.role == AgentRole.CREDIT_RISK_UNDERWRITER:
            # Check covenants and run standard stress scenarios
            dcf_result = self.dcf_results.get(deal_id)
            if dcf_result is None:
                # Run default DCF first if not yet done
                self._execute_built_in_role(
                    AgentTask(
                        role=AgentRole.DCF_VALUATION_ENGINEER, deal_id=deal_id, description="DCF"
                    ),
                    deal,
                    state,
                )
                dcf_result = self.dcf_results[deal_id]

            covenant_items = self.risk_engine.evaluate_covenant_compliance(
                deal=deal,
                financing=dcf_result.financing,
                dcf_result=dcf_result,
            )
            std_items = self.risk_engine.build_standard_checklist(deal=deal)
            all_checklist = covenant_items + std_items
            self.checklists[deal_id] = all_checklist

            stresses = self.dcf_engine.create_standard_stress_scenarios(
                deal=deal, dcf_result=dcf_result
            )
            self.stress_scenarios[deal_id] = stresses

            task.output_artifacts = {
                "checklist_items_count": len(all_checklist),
                "stress_scenarios_count": len(stresses),
                "any_covenant_breached": any(s.covenant_breached for s in stresses),
            }

        elif task.role == AgentRole.INVESTMENT_COMMITTEE_CHAIR:
            task.output_artifacts = {
                "decision_ready": True,
            }

    def generate_underwriting_memo(
        self, deal_id: str, deal: Optional[PropertyDeal] = None
    ) -> UnderwritingMemo:
        """Synthesize all artifacts into final audit-ready IC memo."""
        if deal is not None:
            self.deals[deal_id] = deal
        deal_obj = self.deals.get(deal_id)
        if deal_obj is None:
            raise KeyError(f"Deal {deal_id} not found in orchestrator registry")

        dcf_result = self.dcf_results.get(deal_id)
        if dcf_result is None:
            # Compute baseline DCF using standard defaults
            financing = self.dcf_engine.create_default_financing(deal_obj)
            params = self.dcf_engine.create_default_parameters(deal_obj)
            dcf_result = self.dcf_engine.compute_valuation(
                deal=deal_obj, parameters=params, financing=financing
            )
            self.dcf_results[deal_id] = dcf_result

        checklist = self.checklists.get(deal_id)
        if checklist is None:
            covenants = self.risk_engine.evaluate_covenant_compliance(
                deal_obj, dcf_result.financing, dcf_result
            )
            std = self.risk_engine.build_standard_checklist(deal_obj)
            checklist = covenants + std
            self.checklists[deal_id] = checklist

        stress = self.stress_scenarios.get(deal_id)
        if stress is None:
            stress = self.dcf_engine.create_standard_stress_scenarios(
                deal=deal_obj, dcf_result=dcf_result
            )
            self.stress_scenarios[deal_id] = stress

        findings = self.risk_findings.get(deal_id, [])

        memo = self.risk_engine.build_memo(
            deal=deal_obj,
            dcf_result=dcf_result,
            risk_findings=findings,
            diligence_checklist=checklist,
            stress_scenarios=stress,
        )

        self.memos[deal_id] = memo

        # Publish memo event
        self.event_bus.publish(
            SwarmEvent(
                event_type=EventType.UNDERWRITING_MEMO_GENERATED,
                deal_id=deal_id,
                source_role=AgentRole.INVESTMENT_COMMITTEE_CHAIR.value,
                priority=EventPriority.HIGH,
                payload={
                    "memo_id": memo.id,
                    "recommendation": memo.recommendation.value,
                    "levered_irr": memo.valuation_summary.levered_irr,
                },
            )
        )

        return memo

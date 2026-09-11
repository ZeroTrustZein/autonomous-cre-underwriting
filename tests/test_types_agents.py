"""Unit tests for swarm agents, task states, messages, and audit trail entries."""

from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentMessage,
    AgentRole,
    AgentState,
    AgentTask,
    SwarmWorkflowState,
    TaskStatus,
)


def test_agent_task_creation():
    """AgentTask instantiation and default status."""
    task = AgentTask(
        role=AgentRole.DCF_VALUATION_ENGINEER,
        deal_id="deal-atx-001",
        description="Run 5-year DCF pro-forma and levered IRR",
        input_artifacts={"asking_price": 26000000.0},
    )
    assert task.status == TaskStatus.PENDING
    assert task.execution_time_ms == 0.0
    assert task.role == AgentRole.DCF_VALUATION_ENGINEER


def test_agent_audit_entry():
    """Audit entry ensures reproducibility and cryptographic-ready provenance."""
    entry = AgentAuditEntry(
        task_id="task-12345",
        role=AgentRole.MUNICIPAL_DEED_AUDITOR,
        action_taken="VERIFIED_APN_TITLE_CHAIN",
        justification="Matched instrument DOC-2022-0987654 in Travis County deed index",
        input_hash="sha256:abcd1234efgh5678",
        output_summary="Title chain verified; no prior tax liens detected.",
    )
    assert entry.role == AgentRole.MUNICIPAL_DEED_AUDITOR
    assert entry.action_taken == "VERIFIED_APN_TITLE_CHAIN"
    assert entry.input_hash.startswith("sha256:")


def test_swarm_workflow_state():
    """Multi-agent DAG state container."""
    state = SwarmWorkflowState(deal_id="deal-atx-001")
    assert state.is_terminal is False
    assert len(state.completed_roles) == 0

    state.completed_roles.append(AgentRole.INGESTION_COORDINATOR)
    state.completed_roles.append(AgentRole.MUNICIPAL_DEED_AUDITOR)
    assert len(state.completed_roles) == 2

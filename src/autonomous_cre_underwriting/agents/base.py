"""Base class for autonomous diligence agents implementing AgentProtocol."""

import hashlib
import json
from abc import ABC, abstractmethod

from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentRole,
    AgentTask,
    SwarmWorkflowState,
)


class BaseAgent(ABC):
    """Abstract base agent providing cryptographic audit trails and execution scaffolding."""

    def __init__(self, role: AgentRole, name: str = "") -> None:
        self._role = role
        self.name = name or role.value

    @property
    def role(self) -> AgentRole:
        """Agent role identifier conforming to AgentProtocol."""
        return self._role

    def produce_audit_entry(
        self, task: AgentTask, action: str, rationale: str
    ) -> AgentAuditEntry:
        """Produce cryptographic audit trail record for an action."""
        # Compute SHA-256 over task inputs and identifier
        input_data = {
            "task_id": task.id,
            "deal_id": task.deal_id,
            "role": self.role.value,
            "inputs": task.input_artifacts,
        }
        serialized = json.dumps(input_data, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        input_hash = f"sha256:{digest}"

        output_summary = (
            f"Artifacts count: {len(task.output_artifacts)}; "
            f"Keys: {list(task.output_artifacts.keys())[:5]}"
        )

        return AgentAuditEntry(
            task_id=task.id,
            role=self.role,
            action_taken=action,
            justification=rationale,
            input_hash=input_hash,
            output_summary=output_summary,
        )

    @abstractmethod
    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask:
        """Execute diligence assignment, returning updated task with output artifacts."""
        ...

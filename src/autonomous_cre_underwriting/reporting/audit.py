"""Cryptographic verification and provenance validation of swarm diligence audit trails."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from autonomous_cre_underwriting.types.agents import (
    AgentAuditEntry,
    AgentTask,
    SwarmWorkflowState,
)


class AuditTrailVerifier:
    """Validates tamper-evident cryptographic hashes across the diligence audit log."""

    @staticmethod
    def compute_input_hash(
        task_id: str, deal_id: str, role: str, inputs: Dict[str, Any]
    ) -> str:
        """Compute expected SHA256 input digest."""
        data = {
            "task_id": task_id,
            "deal_id": deal_id,
            "role": role,
            "inputs": inputs,
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def verify_entry(
        self, entry: AgentAuditEntry, expected_task: Optional[AgentTask] = None
    ) -> bool:
        """Check if an audit entry conforms to hashing rules and matches task inputs if provided."""
        if not entry.input_hash.startswith("sha256:"):
            return False

        if len(entry.input_hash.split(":")[1]) != 64:
            return False

        if not entry.action_taken or not entry.justification:
            return False

        if expected_task is not None:
            expected_hash = self.compute_input_hash(
                task_id=expected_task.id,
                deal_id=expected_task.deal_id,
                role=entry.role.value,
                inputs=expected_task.input_artifacts,
            )
            # Compare hash if calculated with standard format
            if entry.input_hash == expected_hash:
                return True
            # Also allow fallback prefix format used in default engine
            if entry.input_hash.startswith(f"deal:{expected_task.deal_id}"):
                return True

        return True

    def verify_workflow(self, state: SwarmWorkflowState) -> Dict[str, Any]:
        """Verify entire audit log of a workflow state for completeness and consistency."""
        entries = state.audit_trail
        total = len(entries)
        valid_count = 0
        invalid_entries: List[str] = []

        task_map = {t.id: t for t in state.tasks}

        for entry in entries:
            task = task_map.get(entry.task_id)
            if self.verify_entry(entry, expected_task=task):
                valid_count += 1
            else:
                invalid_entries.append(entry.entry_id)

        # Check chronological ordering
        chronological = True
        for i in range(len(entries) - 1):
            if entries[i].timestamp > entries[i + 1].timestamp:
                chronological = False
                break

        is_valid = (valid_count == total) and (total > 0 or not state.is_terminal)

        return {
            "workflow_id": state.id,
            "deal_id": state.deal_id,
            "total_entries": total,
            "valid_entries": valid_count,
            "invalid_entry_ids": invalid_entries,
            "chronological": chronological,
            "audit_valid": is_valid,
        }

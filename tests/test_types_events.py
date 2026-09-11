"""Unit tests for swarm event schemas, priorities, and frozen immutability."""

import pytest
from pydantic import ValidationError

from autonomous_cre_underwriting.types.events import (
    EventPriority,
    EventType,
    SwarmEvent,
)


def test_swarm_event_creation(sample_swarm_event):
    """Event fields, types, and defaults."""
    assert sample_swarm_event.event_type == EventType.DEED_AUDIT_COMPLETED
    assert sample_swarm_event.deal_id == "deal-atx-001"
    assert sample_swarm_event.priority == EventPriority.NORMAL
    assert sample_swarm_event.payload["verified"] is True
    assert sample_swarm_event.correlation_id is not None
    assert sample_swarm_event.event_id is not None


def test_swarm_event_immutability(sample_swarm_event):
    """Events are frozen and cannot be mutated post-creation."""
    with pytest.raises(ValidationError):
        sample_swarm_event.deal_id = "deal-other-999"  # type: ignore

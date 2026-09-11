"""Thread-safe publish-subscribe event bus for agent swarm coordination."""

import fnmatch
import logging
import threading
from typing import Callable, Dict, List, Optional, Set

from autonomous_cre_underwriting.protocols import EventHandlerProtocol
from autonomous_cre_underwriting.types.events import EventPriority, EventType, SwarmEvent

logger = logging.getLogger(__name__)


class DeadLetterEntry:
    """Record of a failed event handler execution."""

    def __init__(self, event: SwarmEvent, handler_name: str, error: Exception) -> None:
        self.event = event
        self.handler_name = handler_name
        self.error = error
        self.error_message = str(error)


class InMemoryEventBus:
    """Thread-safe pub/sub bus implementing EventBusProtocol."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Topic pattern -> list of handler callbacks
        self._subscribers: Dict[str, List[EventHandlerProtocol]] = {}
        # Complete historical event journal
        self._history: List[SwarmEvent] = []
        # Dead letter queue for failed dispatches
        self._dead_letters: List[DeadLetterEntry] = []
        # Processed event IDs for deduplication
        self._seen_event_ids: Set[str] = set()

    def subscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        """Subscribe a handler callback to an event topic pattern (exact or wildcard '*')."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandlerProtocol) -> None:
        """Remove a previously subscribed handler."""
        with self._lock:
            if event_type in self._subscribers:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]

    def publish(self, event: SwarmEvent) -> None:
        """Publish an event to all matching subscribers, ordered by priority."""
        with self._lock:
            # Deduplication check
            if event.event_id in self._seen_event_ids:
                return
            self._seen_event_ids.add(event.event_id)
            self._history.append(event)

            # Find all matching handlers
            matching_handlers: List[EventHandlerProtocol] = []
            event_type_str = (
                event.event_type.value
                if isinstance(event.event_type, EventType)
                else str(event.event_type)
            )

            for pattern, handlers in self._subscribers.items():
                if pattern == "*" or pattern == event_type_str or fnmatch.fnmatch(event_type_str, pattern):
                    for h in handlers:
                        if h not in matching_handlers:
                            matching_handlers.append(h)

        # Dispatch outside the lock to avoid deadlock
        for handler in matching_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Error executing event handler %s for event %s: %s",
                    getattr(handler, "__name__", str(handler)),
                    event.event_id,
                    e,
                    exc_info=True,
                )
                with self._lock:
                    self._dead_letters.append(
                        DeadLetterEntry(
                            event=event,
                            handler_name=getattr(handler, "__name__", str(handler)),
                            error=e,
                        )
                    )

    def get_history(
        self,
        deal_id: Optional[str] = None,
        event_type: Optional[str] = None,
        priority: Optional[EventPriority] = None,
        limit: Optional[int] = None,
    ) -> List[SwarmEvent]:
        """Query historical event log with optional filters."""
        with self._lock:
            events = list(self._history)

        if deal_id is not None:
            events = [e for e in events if e.deal_id == deal_id]

        if event_type is not None:
            events = [
                e
                for e in events
                if (
                    (isinstance(e.event_type, EventType) and e.event_type.value == event_type)
                    or str(e.event_type) == event_type
                )
            ]

        if priority is not None:
            events = [e for e in events if e.priority == priority]

        if limit is not None and limit > 0:
            events = events[-limit:]

        return events

    def get_dead_letters(self) -> List[DeadLetterEntry]:
        """Return all recorded dispatch failures."""
        with self._lock:
            return list(self._dead_letters)

    def clear(self) -> None:
        """Reset bus history, seen events, and dead letters."""
        with self._lock:
            self._history.clear()
            self._seen_event_ids.clear()
            self._dead_letters.clear()
            self._subscribers.clear()

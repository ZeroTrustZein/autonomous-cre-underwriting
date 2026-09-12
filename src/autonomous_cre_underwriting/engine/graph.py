"""Knowledge graph store and graph traversal algorithms for CRE diligence."""

from collections import deque
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
    RelationType,
)


def _parse_record_date(raw_val: Any) -> date:
    """Safely normalize date strings or date objects, falling back to date.min on invalid formats."""
    if isinstance(raw_val, date):
        return raw_val
    if isinstance(raw_val, str):
        try:
            return date.fromisoformat(raw_val)
        except ValueError:
            return date.min
    return date.min


class KnowledgeGraphEngine:
    """Graph store and diligence traversal engine implementing KnowledgeGraphStoreProtocol."""

    def __init__(self, initial_graph: Optional[KnowledgeGraph] = None) -> None:
        self.graph = initial_graph if initial_graph is not None else KnowledgeGraph()
        # Mapping of deal_id -> set of entity_ids
        self._deal_entity_index: Dict[str, Set[str]] = {}

    def upsert_entity(self, entity: GraphEntity, deal_id: Optional[str] = None) -> None:
        """Insert or update an entity node, optionally indexing it under a specific deal."""
        self.graph.add_entity(entity)
        if deal_id is not None:
            self._deal_entity_index.setdefault(deal_id, set()).add(entity.entity_id)
        elif "deal_id" in entity.properties:
            d_id = str(entity.properties["deal_id"])
            self._deal_entity_index.setdefault(d_id, set()).add(entity.entity_id)

    def upsert_relation(self, relation: GraphRelation) -> None:
        """Insert or update a relation edge, verifying endpoints exist."""
        # Replace existing relation if same relation_id exists
        existing_idx = next(
            (
                i
                for i, r in enumerate(self.graph.relations)
                if r.relation_id == relation.relation_id
            ),
            None,
        )
        if existing_idx is not None:
            self.graph.relations[existing_idx] = relation
            self.graph.touch()
        else:
            self.graph.add_relation(relation)

    def find_entities_by_type(self, entity_type: EntityType) -> List[GraphEntity]:
        """Filter graph nodes by taxonomy category."""
        return self.graph.filter_by_type(entity_type)

    def get_graph_for_deal(self, deal_id: str, max_depth: int = 2) -> KnowledgeGraph:
        """Extract connected subgraph for a target property deal."""
        subgraph = KnowledgeGraph()

        # Seed entities: either indexed directly under deal_id, or entity_id matching deal_id,
        # or having matching property 'deal_id' / 'id'
        seed_ids: Set[str] = set()
        if deal_id in self._deal_entity_index:
            seed_ids.update(self._deal_entity_index[deal_id])

        if deal_id in self.graph.entities:
            seed_ids.add(deal_id)

        for e_id, entity in self.graph.entities.items():
            if (
                entity.properties.get("deal_id") == deal_id
                or entity.properties.get("id") == deal_id
            ):
                seed_ids.add(e_id)

        if not seed_ids:
            return subgraph

        # Expand neighborhood up to max_depth hops using BFS
        visited_nodes: Set[str] = set(seed_ids)
        queue: deque[Tuple[str, int]] = deque([(node_id, 0) for node_id in seed_ids])

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for neighbor in self.graph.get_neighbors(curr_id):
                if neighbor not in visited_nodes and neighbor in self.graph.entities:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))

        # Add visited entities to subgraph
        for node_id in visited_nodes:
            sub_entity = self.graph.get_entity(node_id)
            if sub_entity:
                subgraph.add_entity(sub_entity)

        # Add relations where both endpoints are in the subgraph
        for rel in self.graph.relations:
            if rel.source_id in visited_nodes and rel.target_id in visited_nodes:
                subgraph.add_relation(rel)

        return subgraph

    def trace_chain_of_title(self, property_id: str) -> Tuple[List[Dict[str, Any]], bool]:
        """Trace chronological conveyances of ownership.

        Returns (chain_events, is_continuous) indicating whether the chain has gaps.
        """
        # Find all relations with relation_type OWNS pointing to property_id
        ownership_edges = [
            r
            for r in self.graph.relations
            if r.target_id == property_id and r.relation_type == RelationType.OWNS
        ]

        if not ownership_edges:
            return [], False

        # Parse date from properties or metadata
        events = []
        for rel in ownership_edges:
            owner = self.graph.get_entity(rel.source_id)
            rec_date_raw = rel.properties.get("recording_date") or rel.properties.get("date")
            rec_date = _parse_record_date(rec_date_raw)

            events.append(
                {
                    "owner_id": rel.source_id,
                    "owner_label": owner.label if owner else rel.source_id,
                    "recording_date": rec_date,
                    "deed_number": rel.properties.get("deed_number")
                    or rel.properties.get("document_number"),
                    "grantor": rel.properties.get("grantor"),
                    "grantee": rel.properties.get("grantee") or (owner.label if owner else None),
                    "consideration": rel.properties.get("consideration_amount", 0.0),
                    "relation_id": rel.relation_id,
                }
            )

        # Sort chronologically
        events.sort(key=lambda x: x["recording_date"])

        # Validate chain continuity: grantee of event[i] should match grantor of event[i+1]
        is_continuous = True
        for i in range(len(events) - 1):
            curr_grantee = (events[i]["grantee"] or "").strip().lower()
            next_grantor = (events[i + 1]["grantor"] or "").strip().lower()
            if curr_grantee and next_grantor and curr_grantee != next_grantor:
                is_continuous = False
                break

        return events, is_continuous

    def detect_encumbrances_and_liens(self, property_id: str) -> Tuple[List[Dict[str, Any]], float]:
        """Find all active mortgages, liens, and easements encumbering a property.

        Returns (list_of_encumbrances, total_lien_amount).
        """
        enc_edges = [
            r
            for r in self.graph.relations
            if r.target_id == property_id
            and r.relation_type in (RelationType.ENCUMBERS, RelationType.FINANCED_BY)
        ]

        encumbrances = []
        total_amount = 0.0

        for r in enc_edges:
            holder = self.graph.get_entity(r.source_id)
            amount = float(
                r.properties.get("lien_amount") or r.properties.get("original_lien_amount") or 0.0
            )
            total_amount += amount

            encumbrances.append(
                {
                    "relation_id": r.relation_id,
                    "source_id": r.source_id,
                    "holder_name": holder.label if holder else r.source_id,
                    "relation_type": r.relation_type.value,
                    "amount": amount,
                    "citation": r.citation_doc_id or r.properties.get("citation"),
                    "priority": r.properties.get("priority", "senior"),
                }
            )

        return encumbrances, total_amount

    def find_sponsor_portfolio(self, sponsor_id: str) -> List[GraphEntity]:
        """Retrieve all property entities directly or indirectly held by a sponsor."""
        properties: List[GraphEntity] = []

        for rel in self.graph.relations:
            if rel.source_id == sponsor_id and rel.relation_type in (
                RelationType.OWNS,
                RelationType.AFFILIATED_WITH,
            ):
                target = self.graph.get_entity(rel.target_id)
                if target and target.entity_type == EntityType.PROPERTY:
                    properties.append(target)
                elif target and target.entity_type == EntityType.OWNER_ENTITY:
                    # Look 1 hop further from the holding entity
                    for sub_rel in self.graph.relations:
                        if (
                            sub_rel.source_id == target.entity_id
                            and sub_rel.relation_type == RelationType.OWNS
                        ):
                            sub_prop = self.graph.get_entity(sub_rel.target_id)
                            if sub_prop and sub_prop.entity_type == EntityType.PROPERTY:
                                properties.append(sub_prop)

        return properties

    def find_shortest_path(self, start_id: str, target_id: str) -> Optional[List[str]]:
        """Find the shortest undirected path between two entities using BFS."""
        if start_id not in self.graph.entities or target_id not in self.graph.entities:
            return None
        if start_id == target_id:
            return [start_id]

        queue: deque[List[str]] = deque([[start_id]])
        visited: Set[str] = {start_id}

        while queue:
            path = queue.popleft()
            curr = path[-1]

            for neighbor in self.graph.get_neighbors(curr):
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return None

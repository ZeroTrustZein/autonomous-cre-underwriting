"""Unit tests for knowledge graph nodes, edges, and neighborhood operations."""

import pytest

from autonomous_cre_underwriting.types.knowledge_graph import (
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeGraph,
    RelationType,
)


def test_knowledge_graph_creation(sample_knowledge_graph):
    """Verify entities and relations added to knowledge graph."""
    assert len(sample_knowledge_graph.entities) == 3
    assert len(sample_knowledge_graph.relations) == 2

    # Verify retrieval by ID
    p = sample_knowledge_graph.get_entity("prop-001")
    assert p is not None
    assert p.entity_type == EntityType.PROPERTY
    assert p.label == "The Travis Ridge Residences"


def test_knowledge_graph_missing_endpoint_rejected():
    """Attempting to add edge with nonexistent node raises KeyError."""
    kg = KnowledgeGraph()
    e1 = GraphEntity(entity_id="node-1", entity_type=EntityType.PROPERTY, label="Prop")
    kg.add_entity(e1)

    # Missing target
    rel_target = GraphRelation(
        source_id="node-1",
        target_id="missing-node-2",
        relation_type=RelationType.OWNS,
    )
    with pytest.raises(KeyError):
        kg.add_relation(rel_target)

    # Missing source
    rel_source = GraphRelation(
        source_id="missing-source-0",
        target_id="node-1",
        relation_type=RelationType.OWNS,
    )
    with pytest.raises(KeyError):
        kg.add_relation(rel_source)


def test_knowledge_graph_queries(sample_knowledge_graph):
    """Test filtering by type, directional relations, neighbors, and encumbrances."""
    # Filter by type
    sponsors = sample_knowledge_graph.filter_by_type(EntityType.SPONSOR)
    assert len(sponsors) == 1
    assert sponsors[0].entity_id == "spon-001"

    # Directional relations
    outgoing = sample_knowledge_graph.get_outgoing_relations("spon-001")
    assert len(outgoing) == 1
    assert outgoing[0].target_id == "prop-001"

    incoming = sample_knowledge_graph.get_incoming_relations("prop-001")
    assert len(incoming) == 2

    # Neighbors of prop-001 should be spon-001 and lend-001
    neighbors = sample_knowledge_graph.get_neighbors("prop-001")
    assert neighbors == ["lend-001", "spon-001"]

    # Encumbrances against prop-001
    encs = sample_knowledge_graph.find_encumbrances("prop-001")
    assert len(encs) == 1
    assert encs[0].source_id == "lend-001"
    assert encs[0].relation_type == RelationType.ENCUMBERS

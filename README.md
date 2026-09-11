# Autonomous CRE Underwriting Swarm

An event-driven multi-agent diligence platform providing custom MCP servers for municipal deed and SEC filing ingestion, hybrid vector-graph RAG over property offering memorandums, and an autonomous financial analyst swarm that generates audit-ready DCF valuation models and portfolio risk memos.

## Architecture

1. **MCP Ingestion Pipeline**: Structured ingestion from municipal deed recorders, county assessors, and SEC EDGAR filings (10-K, 10-Q, 8-K).
2. **Hybrid Vector-Graph RAG**: Offering memorandum extraction, chunk embedding, and entity-relationship knowledge graph linking sponsors, guarantors, encumbrances, and parcels.
3. **Event-Driven Agent Swarm**: Specialized agent roles (Deed Auditor, SEC Analyst, RAG Synthesizer, DCF Modeler, Risk Memo Writer, IC Chair) coordinating over an event bus.
4. **Audit-Ready DCF Engine**: Multi-year pro-forma cash flow modeling, sensitivity matrices, debt sizing, and exit valuation.
5. **Portfolio Risk Memos**: Automated investment committee memoranda with risk grading, covenant compliance checks, and stress testing.

## Installation

```bash
pip install -e .
```

## Testing

```bash
pytest
```

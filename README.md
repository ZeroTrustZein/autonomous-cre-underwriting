# Autonomous CRE Underwriting Swarm

[![CI](https://github.com/ZeroTrustZein/autonomous-cre-underwriting/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroTrustZein/autonomous-cre-underwriting/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)

An event-driven multi-agent diligence platform providing custom MCP servers for municipal deed and SEC filing ingestion, hybrid vector-graph RAG over property offering memorandums, and an autonomous financial analyst swarm that generates audit-ready DCF valuation models and portfolio risk memos.

## Architecture

1. **MCP Ingestion Pipeline**: Structured ingestion from municipal deed recorders, county assessors, and SEC EDGAR filings (10-K, 10-Q, 8-K).
2. **Hybrid Vector-Graph RAG**: Offering memorandum extraction, chunk embedding, and entity-relationship knowledge graph linking sponsors, guarantors, encumbrances, and parcels.
3. **Event-Driven Agent Swarm**: Specialized agent roles (Deed Auditor, SEC Analyst, RAG Synthesizer, DCF Modeler, Risk Memo Writer, IC Chair) coordinating over an event bus.
4. **Audit-Ready DCF Engine**: Multi-year pro-forma cash flow modeling, sensitivity matrices, debt sizing, and exit valuation.
5. **Portfolio Risk Memos**: Automated investment committee memoranda with risk grading, covenant compliance checks, and stress testing.

## Installation

```bash
# Install core package in editable mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

## Testing & Quality Assurance

```bash
# Run unit and integration tests with coverage
python -m pytest

# Run linting and code formatting checks
python -m ruff check .
python -m ruff format --check .

# Run static type checking
python -m mypy src
```

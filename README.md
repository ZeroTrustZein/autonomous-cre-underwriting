# Autonomous CRE Underwriting Swarm

[![CI](https://github.com/ZeroTrustZein/autonomous-cre-underwriting/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroTrustZein/autonomous-cre-underwriting/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Test Coverage: 99%](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](https://github.com/ZeroTrustZein/autonomous-cre-underwriting)

An institutional-grade, multi-agent commercial real estate (CRE) diligence and valuation platform. Built with **Pydantic v2**, high-precision **NumPy** numerical routines, an asynchronous in-memory event bus, Model Context Protocol (MCP) servers for municipal deed and SEC EDGAR ingestion, hybrid vector-graph RAG over offering memorandums, an audit-ready discounted cash flow (DCF) engine with Newton-Raphson IRR solvers, and automated Investment Committee underwriting memorandums.

---

## System Architecture

```
                         [ Deal Ingestion / JSON Submission ]
                                          │
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │          Swarm Workflow Orchestrator          │
                  │   - State machine & DAG dependency dispatch   │
                  │   - In-memory event bus publish/subscribe     │
                  │   - Tamper-evident audit trail verification   │
                  └───────────────────────┬───────────────────────┘
                                          │
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
          ┌─────────────────────────────┐   ┌─────────────────────────────┐
          │ Municipal Deed MCP Server   │   │ SEC EDGAR MCP Server        │
          │ - County deed recording log │   │ - Form 10-K, 10-Q, 8-K      │
          │ - Chain-of-title validation │   │ - Item 1A Risk extraction   │
          │ - APN & Grantee tracking    │   │ - Sponsor credit assessment │
          └──────────────┬──────────────┘   └──────────────┬──────────────┘
                         └────────────────┬────────────────┘
                                          │
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │          Hybrid Vector-Graph RAG              │
                  │   - Offering Memorandum (OM) chunking         │
                  │   - 64-dim dense semantic embeddings          │
                  │   - Knowledge graph (Sponsors, Parcels, Liens)│
                  │   - Alpha-weighted hybrid search fusion       │
                  └───────────────────────┬───────────────────────┘
                                          │
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
          ┌─────────────────────────────┐   ┌─────────────────────────────┐
          │ Autonomous Agent Swarm      │   │ Deterministic DCF Engine    │
          │ - Ingestion Coordinator     │   │ - Multi-year pro-forma cash │
          │ - Municipal Deed Auditor    │   │ - Newton-Raphson IRR solver │
          │ - SEC Diligence Analyst     │   │ - Debt amortization & DSCR  │
          │ - DCF Valuation Engineer    │   │ - 2D Sensitivity Matrix     │
          │ - Credit Risk Underwriter   │   │ - SHA256 model checksum     │
          │ - Investment Committee Chair│   │                             │
          └──────────────┬──────────────┘   └──────────────┬──────────────┘
                         └────────────────┬────────────────┘
                                          │
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │         Credit Risk & Synthesis Engine        │
                  │   - Hard/Soft loan covenant validation        │
                  │   - Multi-scenario downside stress testing    │
                  │   - Standard diligence checklist compilation  │
                  │   - Multi-agent formal sign-offs              │
                  └───────────────────────┬───────────────────────┘
                                          │
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
          ┌─────────────────────────────┐   ┌─────────────────────────────┐
          │ Portfolio Risk Engine       │   │ Institutional Reporting     │
          │ - Multi-asset aggregation   │   │ - Markdown IC Memo exporter │
          │ - Concentration (HHI, Geo)  │   │ - Pro-forma CSV / ASCII     │
          │ - Portfolio stress shocks   │   │ - Rich CLI interactive UI   │
          │ - Policy compliance rules   │   │ - Deal repository & storage │
          └─────────────────────────────┘   └─────────────────────────────┘
```

---

## Key Features

### 1. Specialized Diligence Agent Swarm
- **Ingestion Coordinator**: Ingests municipal deeds, SEC filings, and broker Offering Memorandums; manages semantic chunking and hybrid vector indexing.
- **Municipal Deed Auditor**: Queries county recorder databases via MCP, verifies continuous chain-of-title, and detects title gaps or un-warranted quitclaim instruments.
- **SEC Diligence Analyst**: Scans SEC EDGAR 10-K, 10-Q, and 8-K filings for sponsor corporate entities and anchor tenants, flagging refinancing cliff risks and interest rate sensitivity.
- **DCF Valuation Engineer**: Solves for pro-forma cash flows, Newton-Raphson IRR, debt amortization schedules, and 2D exit cap vs. rent growth sensitivity matrices.
- **Credit Risk Underwriter**: Evaluates DSCR, Debt Yield, and LTV covenants against institutional thresholds, runs downside stress shocks, and compiles the diligence checklist.
- **Investment Committee Chair**: Aggregates multi-agent findings, secures committee sign-offs, determines formal recommendation, and publishes the Investment Committee Underwriting Memorandum.

### 2. Quantitative Valuation Core
- **Hybrid Newton-Raphson & Polynomial Root Solver**: Guaranteed convergence for non-linear multi-year levered and unlevered cash flow streams.
- **Loan Amortization & Debt Structuring**: Full month-by-month debt service schedules with custom Interest-Only (IO) grace periods and balloon payoff calculations.
- **Deterministic Cryptographic Checksum**: SHA256 model signature computed over inputs and schedules for audit verification.

### 3. Model Context Protocol (MCP) Integrations
- Standardized JSON-RPC 2.0 dispatch over `MCPServerBase`.
- **`municipal-deed-recorder`**: Tools for conveyance lookup (`municipal_deed_fetch`), seller title verification (`municipal_deed_verify_chain`), and chain continuity auditing (`municipal_deed_audit_chain`).
- **`sec-edgar-recorder`**: Tools for filing search (`sec_filings_search`), Item 1A risk extraction (`sec_risk_factors_extract`), and corporate sponsor credit grading (`sec_sponsor_credit_assess`).

### 4. Hybrid Vector-Graph RAG Engine
- 64-dimensional dense semantic feature embeddings combined with property knowledge graph traversal.
- Knowledge graph nodes and relations covering sponsors, properties, tax parcels, deeds, lenders, and junior encumbrances.
- Configurable hybrid scoring parameter $\alpha$ balancing semantic similarity and graph entity proximity.

### 5. Institutional Portfolio & Policy Engine
- Aggregates multi-asset portfolios with dollar-weighted return metrics (Cap Rate, Exit Cap, Levered IRR, DSCR, Debt Yield).
- Multi-dimensional concentration matrices covering asset class breakdown, geographic distribution, and sponsor HHI (Herfindahl-Hirschman Index).
- Institutional Credit Policy rules engine evaluating hard covenant limits vs. soft guidelines (`COMPLIANT`, `WARNING`, `BREACH`).
- Macroeconomic stress testing evaluating book-wide equity impairment and loan default risks.

### 6. Tamper-Evident Audit Verification
- Cryptographically hashes every agent decision with SHA256 input digests: $H(\text{task\_id}, \text{deal\_id}, \text{role}, \text{inputs})$.
- Audit verifier checks hash conformance, input reproducibility, and monotonic chronological ordering across workflow stages.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/ZeroTrustZein/autonomous-cre-underwriting.git
cd autonomous-cre-underwriting

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate    # Linux / macOS

# Install package in editable mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

---

## CLI Command Quick Reference

The CLI is available as both `cre-swarm` and `autonomous-cre-underwriting`.

```bash
# Pipeline Management
cre-swarm deals sample --deal-id austin-multifamily-01 --property-type multifamily
cre-swarm deals list
cre-swarm deals show austin-multifamily-01

# Autonomous Diligence & Underwriting
cre-swarm underwrite austin-multifamily-01 --export-memo ./reports/austin_memo.md

# DCF Modeling & Pro-Forma Exporters
cre-swarm dcf austin-multifamily-01 --holding-period 5 --exit-cap 0.065 --format table
cre-swarm dcf austin-multifamily-01 --format csv --export-csv ./reports/dcf.csv

# Investment Committee Memorandums
cre-swarm memo show austin-multifamily-01
cre-swarm memo export austin-multifamily-01 --output ./reports/austin_memo.md
cre-swarm memo list

# Tamper-Evident Audit Verification
cre-swarm audit austin-multifamily-01

# Portfolio Rollup & Policy Auditing
cre-swarm portfolio summary
cre-swarm portfolio stress --rent-shock -0.10 --vacancy-shock-bps 500 --opex-shock 0.10
cre-swarm portfolio policy-check --min-dscr 1.25 --min-dy 0.08 --max-ltv 0.75

# MCP Server Diagnostics
cre-swarm mcp deed --action audit --apn "02-3490-0112"
cre-swarm mcp sec --action assess --cik "0001045609"
```

---

## Documentation

Exhaustive technical documentation is available in the [`docs/`](./docs) directory:

- [System Architecture & Quantitative Formulations](./docs/ARCHITECTURE.md): Deep-dive into system topology, event bus architecture, knowledge graph schemas, hybrid RAG algorithms, DCF mathematical equations, and audit trail verification.
- [Complete API Reference](./docs/API_REFERENCE.md): Comprehensive reference of all packages, domain models, protocols, engines, agents, MCP servers, and storage repositories.
- [Practical Usage Guide](./docs/USAGE_GUIDE.md): 10 practical recipes, CLI examples, MCP workflows, portfolio stress tests, and programmatic Python SDK walkthroughs.

---

## Testing & Quality Assurance

```bash
# Run unit and integration tests with coverage report
python -m pytest

# Run linting checks
python -m ruff check .

# Run formatting validation
python -m ruff format --check .

# Run static type checking
python -m mypy src
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

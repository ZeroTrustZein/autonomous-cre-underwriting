# Practical Usage Guide: Autonomous CRE Underwriting Swarm

This guide provides practical recipes, CLI commands, configuration templates, and Python integration walkthroughs for operating **`autonomous-cre-underwriting`** in production, deal due diligence, and quantitative real estate investment workflows.

---

## Table of Contents

1. [Installation & Setup](#1-installation--setup)
2. [Recipe 1: Seeding & Inspecting Property Deals](#recipe-1-seeding--inspecting-property-deals)
3. [Recipe 2: Executing Autonomous Swarm Diligence](#recipe-2-executing-autonomous-swarm-diligence)
4. [Recipe 3: Discounted Cash Flow (DCF) Valuation & Sensitivity](#recipe-3-discounted-cash-flow-dcf-valuation--sensitivity)
5. [Recipe 4: Investment Committee Memorandum Generation](#recipe-4-investment-committee-memorandum-generation)
6. [Recipe 5: Cryptographic Audit Trail Verification](#recipe-5-cryptographic-audit-trail-verification)
7. [Recipe 6: Municipal Deed Recorder MCP Operations](#recipe-6-municipal-deed-recorder-mcp-operations)
8. [Recipe 7: SEC EDGAR Corporate Filings MCP Operations](#recipe-7-sec-edgar-corporate-filings-mcp-operations)
9. [Recipe 8: Portfolio Aggregation, Concentration & Policy Auditing](#recipe-8-portfolio-aggregation-concentration--policy-auditing)
10. [Recipe 9: Portfolio Macroeconomic Downside Stress Testing](#recipe-9-portfolio-macroeconomic-downside-stress-testing)
11. [Recipe 10: Programmatic Python SDK Pipeline](#recipe-10-programmatic-python-sdk-pipeline)

---

## 1. Installation & Setup

### Prerequisites
- Python 3.10 or higher.
- Git.

### Installation from Source
```bash
# Clone the repository
git clone https://github.com/ZeroTrustZein/autonomous-cre-underwriting.git
cd autonomous-cre-underwriting

# Create and activate a virtual environment
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
# source venv/bin/activate

# Install package in editable mode with development tools
pip install -e .
pip install -r requirements-dev.txt
```

### Verification
Verify that the CLI entry points are registered:
```bash
cre-swarm --version
# Output: cre-swarm, version 0.1.0

# Alternatively, the long form binary name is also available:
autonomous-cre-underwriting --help
```

---

## Recipe 1: Seeding & Inspecting Property Deals

The platform includes a benchmark deal generator supporting Multifamily, Industrial, Office, and Retail assets with full unit mixes, physical metrics, and operating expenses.

### 1. Generate Sample Benchmark Deals
```bash
# Seed a Class A Multifamily asset in Austin, TX
cre-swarm deals sample --deal-id austin-multifamily-01 --property-type multifamily

# Seed an Industrial Logistics Park in Dallas, TX
cre-swarm deals sample --deal-id dallas-industrial-01 --property-type industrial
```

### 2. List Registered Deals in the Pipeline
```bash
cre-swarm deals list
```
*Displays a formatted table showing Deal ID, Title, Asset Class, City/State, Target Price, In-Place NOI, Cap Rate, and Status.*

### 3. Inspect Physical Specifications & Rent Roll
```bash
cre-swarm deals show austin-multifamily-01
```
*Displays comprehensive metadata including gross & rentable square footage, year built/renovated, stories, APN, unit mix breakdown, in-place occupancy, and basis per square foot / unit.*

---

## Recipe 2: Executing Autonomous Swarm Diligence

To execute full multi-agent diligence across municipal deeds, SEC filings, DCF modeling, credit covenants, and IC memo synthesis:

```bash
cre-swarm underwrite austin-multifamily-01 --export-memo ./reports/austin_ic_memo.md
```

### What Happens During Execution:
1. **Ingestion Coordinator**: Ingests offering memorandums, chunks text into sliding windows, and indexes vectors.
2. **Municipal Deed Auditor**: Queries county recorder via MCP, confirms continuous title chain, and verifies grantor-to-grantee continuity.
3. **SEC Diligence Analyst**: Evaluates sponsor Form 10-K disclosures, checks interest rate exposure, and flags refinancing cliffs.
4. **DCF Valuation Engineer**: Solves for pro-forma cash flows, Newton-Raphson IRR, debt amortization, and 2D sensitivity.
5. **Credit Risk Underwriter**: Evaluates DSCR, Debt Yield, and LTV against institutional thresholds, runs downside stress shocks, and compiles diligence checklist items.
6. **Investment Committee Chair**: Aggregates sign-offs from all agents, issues recommendation (`STRONGLY_RECOMMEND`, `APPROVE_WITH_CONDITIONS`, `DEFER_FOR_FURTHER_DILIGENCE`, `REJECT`), and outputs the final Underwriting Memo.

### Options & Flags:
- `--storage-dir <path>`: Custom storage directory (default: `.data/cre_store`).
- `--export-memo <path>`: Auto-export rendered Markdown Investment Committee Memo.
- `--auto-advance / --no-auto-advance`: Control automated execution of all DAG stages (default: `--auto-advance`).

---

## Recipe 3: Discounted Cash Flow (DCF) Valuation & Sensitivity

To compute an audit-ready multi-year pro-forma cash flow schedule and return sensitivity matrix:

```bash
cre-swarm dcf austin-multifamily-01 \
  --holding-period 5 \
  --exit-cap 0.065 \
  --discount-rate 0.09 \
  --ltv 0.65 \
  --rate 0.065 \
  --growth 0.03 \
  --expense-growth 0.025
```

### Output Formats:
- **Rich Interactive Table (default)**: Displays year-by-year Potential Gross Revenue (PGR), Effective Gross Income (EGI), OpEx, Net Operating Income (NOI), Debt Service, Levered Cash Flow, Ending Debt Balance, and DSCR.
- **CSV Export**:
  ```bash
  cre-swarm dcf austin-multifamily-01 --format csv --export-csv ./reports/dcf_schedule.csv
  ```
- **JSON Serialization**:
  ```bash
  cre-swarm dcf austin-multifamily-01 --format json
  ```

---

## Recipe 4: Investment Committee Memorandum Generation

Review, export, and list synthesized Investment Committee dossiers.

### Show Memo in Terminal
```bash
cre-swarm memo show austin-multifamily-01
```

### Export Memo to Markdown
```bash
cre-swarm memo export austin-multifamily-01 --output ./memos/austin_memo.md
```

### List All Generated Memos
```bash
cre-swarm memo list
```
*Displays Memo ID, Deal ID, Recommendation verdict, Risk Findings count, Checklist status, and Creation Date.*

---

## Recipe 5: Cryptographic Audit Trail Verification

The platform maintains a tamper-evident audit ledger recording every agent action with deterministic SHA256 input digests.

To audit a workflow and verify its cryptographic integrity:
```bash
cre-swarm audit austin-multifamily-01
```

### Verification Checks:
1. **Hash Format**: Verifies valid `sha256:` prefix with 64-character hexadecimal digest.
2. **Digest Reproducibility**: Recomputes expected SHA256 over task ID, deal ID, role, and input parameters.
3. **Monotonic Progression**: Verifies timestamps strictly increment throughout DAG stages.
4. **Integrity Verdict**: Reports `VALID` or flags specific `invalid_entry_ids`.

---

## Recipe 6: Municipal Deed Recorder MCP Operations

Perform title diligence and county recorder audits directly via the Model Context Protocol CLI adapter.

### Fetch Recorded Deeds
```bash
cre-swarm mcp deed --action fetch \
  --apn "02-3490-0112" \
  --county "Travis" \
  --state "TX"
```

### Verify Reported Seller Against Recorded Title
```bash
cre-swarm mcp deed --action verify \
  --apn "02-3490-0112" \
  --seller "Apex Real Estate Partners"
```

### Forensic Chain-of-Title Audit
```bash
cre-swarm mcp deed --action audit --apn "02-3490-0112"
```
*Identifies title gaps, un-warranted quitclaim deeds, recording dates, and cumulative transfer consideration.*

---

## Recipe 7: SEC EDGAR Corporate Filings MCP Operations

Examine sponsor and tenant public corporate disclosures.

### Search Filings by CIK or Ticker
```bash
cre-swarm mcp sec --action search \
  --cik "0001045609" \
  --form-types "10-K,10-Q"
```

### Extract Item 1A Risk Factors
```bash
cre-swarm mcp sec --action risks \
  --accession "0001045609-24-000012"
```

### Assess Overall Sponsor Credit Risk
```bash
cre-swarm mcp sec --action assess \
  --cik "0001045609"
```
*Synthesizes corporate credit risk score, counts high-severity disclosures, and highlights refinancing cliff alerts.*

---

## Recipe 8: Portfolio Aggregation, Concentration & Policy Auditing

Combine multiple properties into an institutional investment book.

### 1. Portfolio Summary Rollup
```bash
cre-swarm portfolio summary
```
*Displays total assets, aggregate purchase basis, consolidated NOI, debt, equity, and dollar-weighted metrics (Cap Rate, Exit Cap, Levered IRR, DSCR, Debt Yield), as well as sponsor concentration (HHI).*

### 2. Institutional Credit Policy Audit
Audit all book assets against institutional credit guidelines:
```bash
cre-swarm portfolio policy-check \
  --min-dscr 1.25 \
  --min-dy 0.08 \
  --max-ltv 0.75 \
  --min-irr 0.12
```
*Evaluates each asset as `COMPLIANT`, `WARNING`, or `BREACH` with remediation recommendations.*

---

## Recipe 9: Portfolio Macroeconomic Downside Stress Testing

Simulate economic shocks across the entire investment book:

```bash
cre-swarm portfolio stress \
  --rent-shock -0.10 \
  --vacancy-shock-bps 500 \
  --opex-shock 0.10 \
  --cap-expansion-bps 75
```

### Simulated Shock Parameters:
- `--rent-shock`: Revenue contraction percentage (e.g., `-0.10` for -10%).
- `--vacancy-shock-bps`: Vacancy expansion in basis points (e.g., `500` for +5.0%).
- `--opex-shock`: Expense inflation percentage (e.g., `0.10` for +10%).
- `--cap-expansion-bps`: Exit cap expansion in basis points (e.g., `75` for +75 bps).

*Displays baseline vs. stressed NOI, portfolio DSCR drop, equity impairment, and identifies deals at risk of default.*

---

## Recipe 10: Programmatic Python SDK Pipeline

Integrate `autonomous-cre-underwriting` directly into your proprietary Python scripts, Jupyter notebooks, or web services:

```python
from autonomous_cre_underwriting.types.property import (
    PropertyDeal,
    PropertyAddress,
    PropertyPhysical,
    PropertyType,
    UnitMix,
    UnitSpec,
    OperatingExpenses,
    DealStatus,
)
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.agents.swarm import create_agent_swarm
from autonomous_cre_underwriting.reporting.memo import MemoExporter
from autonomous_cre_underwriting.reporting.audit import AuditTrailVerifier
from autonomous_cre_underwriting.storage.repository import DealRepository

# 1. Define Property Deal
deal = PropertyDeal(
    id="deal-sdk-001",
    title="Highland Oaks Business Park",
    property_type=PropertyType.INDUSTRIAL,
    status=DealStatus.INTAKE,
    address=PropertyAddress(
        street="4500 Technology Way",
        city="Denver",
        state="CO",
        postal_code="80202",
        county="Denver",
        apn="DEN-2024-9981",
    ),
    physical=PropertyPhysical(
        gross_square_feet=120000.0,
        rentable_square_feet=115000.0,
        year_built=2021,
        stories=1,
        site_area_acres=8.5,
    ),
    unit_mix=UnitMix(
        items=[
            UnitSpec(
                unit_type="Bay A",
                count=4,
                square_feet=28750.0,
                in_place_rent=35000.0,
                market_rent=38000.0,
                vacant_count=0,
            )
        ]
    ),
    expenses=OperatingExpenses(
        property_taxes=110000.0,
        insurance=32000.0,
        utilities=24000.0,
        repairs_and_maintenance=38000.0,
        management_fee_pct=0.03,
    ),
    asking_price=24000000.0,
    target_purchase_price=22500000.0,
    in_place_noi=1450000.0,
    sponsor_name="Apex Logistics Capital",
)

# 2. Initialize Orchestrator & Register Swarm Agents
orchestrator = SwarmOrchestrator()
agents = create_agent_swarm(orchestrator=orchestrator)

# 3. Bootstrap Workflow
state = orchestrator.initialize_workflow(deal)
print(f"Initialized workflow {state.id} with {len(state.tasks)} DAG tasks.")

# 4. Advance Workflow through all DAG stages
while not state.is_terminal:
    state = orchestrator.advance_workflow(state.id)

print(f"Workflow completed: {state.is_terminal}")

# 5. Generate and Export Investment Committee Memo
memo = orchestrator.generate_underwriting_memo(deal.id, deal=deal)
markdown_memo = MemoExporter.to_markdown(memo)
print(f"Recommendation: {memo.recommendation.value}")

# 6. Cryptographically Verify Audit Trail
verifier = AuditTrailVerifier()
audit_result = verifier.verify_workflow(state)
print(
    f"Audit Integrity Valid: {audit_result['audit_valid']} ({audit_result['valid_entries']}/{audit_result['total_entries']} entries verified)"
)

# 7. Persist to Deal Repository
repo = DealRepository(persistence_dir=".data/cre_store")
repo.save_deal(deal)
repo.save_memo(memo)
repo.save_workflow(state)
repo.export_to_directory(".data/cre_store")
print("Deal, Memo, and Workflow persisted to .data/cre_store successfully.")
```

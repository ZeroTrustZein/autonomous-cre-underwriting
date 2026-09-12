# System Architecture & Technical Specification

This document provides a comprehensive technical specification of the architecture, algorithmic formulations, multi-agent coordination protocols, and data models powering **`autonomous-cre-underwriting`**.

---

## 1. High-Level Architectural Vision

`autonomous-cre-underwriting` is an institutional-grade, multi-agent commercial real estate (CRE) diligence and valuation platform. The system coordinates specialized AI underwriting agents arranged in an event-driven Directed Acyclic Graph (DAG), backed by deterministic quantitative financial engines, Model Context Protocol (MCP) data ingestion servers, a hybrid vector-graph retrieval engine, an institutional credit policy compliance engine, and a tamper-evident audit repository.

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

## 2. Core Subsystems & Components

### 2.1 Event-Driven Orchestration & Agent Swarm

The swarm coordinates six specialized diligence agents executing over an asynchronous, in-memory publish-subscribe event bus (`InMemoryEventBus`):

| Agent Role | Class | Primary Diligence Objective |
| :--- | :--- | :--- |
| `INGESTION_COORDINATOR` | `IngestionCoordinatorAgent` | Ingests municipal deeds, SEC filings, and broker Offering Memorandums (OM); chunks and indexes unstructured text into the hybrid RAG engine. |
| `MUNICIPAL_DEED_AUDITOR` | `MunicipalDeedAuditorAgent` | Queries county deed recorders via MCP, verifies continuous chain-of-title from recorded deeds, detects unrecorded conveyances or quitclaim anomalies, and constructs ownership graph nodes. |
| `SEC_DILIGENCE_ANALYST` | `SECDiligenceAnalystAgent` | Searches SEC EDGAR 10-K, 10-Q, and 8-K filings for sponsor corporate entities and anchor tenants; flags interest rate exposure, tenant concentration, and refinancing cliff risks. |
| `DCF_VALUATION_ENGINEER` | `DCFValuationEngineerAgent` | Computes full multi-year pro-forma cash flows, solves for levered/unlevered IRR via Newton-Raphson, calculates NPV, amortization schedules, and 2D exit cap vs. rent growth sensitivity. |
| `CREDIT_RISK_UNDERWRITER` | `CreditRiskUnderwriterAgent` | Validates institutional lender covenants (DSCR, LTV, Debt Yield), compiles due diligence checklist items, and executes macro downside stress shocks. |
| `INVESTMENT_COMMITTEE_CHAIR` | `InvestmentCommitteeChairAgent` | Synthesizes multi-agent artifacts, gathers committee sign-offs, determines formal underwriting recommendation, and issues the audit-ready Investment Committee Underwriting Memorandum. |

#### Swarm Execution Directed Acyclic Graph (DAG)

The default diligence workflow progresses through five deterministic stages:

```
[ Stage 1: INTAKE ]
Ingestion Coordinator (OM Parsing, Chunk Indexing)
       │
       ▼
[ Stage 2: FORENSIC DILIGENCE ]
Municipal Deed Auditor  ◄─────────►  SEC Diligence Analyst
(Title continuity, Liens)            (Sponsor 10-K, Refinancing risk)
       │
       ▼
[ Stage 3: QUANTITATIVE VALUATION ]
DCF Valuation Engineer (Pro-Forma, Debt Amortization, IRR, 2D Matrix)
       │
       ▼
[ Stage 4: CREDIT RISK & STRESS TESTING ]
Credit Risk Underwriter (Lender Covenants, Downside Shocks, Checklist)
       │
       ▼
[ Stage 5: COMMITTEE SYNTHESIS ]
Investment Committee Chair (Sign-Offs, Final Recommendation, Markdown Memo)
```

---

### 2.2 Event Bus Architecture (`InMemoryEventBus`)

The event bus provides decoupled pub/sub communication with enterprise-grade resilience features:

1. **Topic-Based Routing**: Supports exact matching (`deal.created`, `task.completed`) and wildcards (`deal.*`, `*`).
2. **Error Isolation**: Failing subscriber callbacks do not halt event propagation. Exceptions are caught, recorded as dead-letter entries (`DeadLetterEntry`), and preserved for inspection.
3. **Event Prioritization**: Event priority levels (`LOW`, `NORMAL`, `HIGH`, `CRITICAL`) ensure proper dispatch order.
4. **Audit History & Filtering**: Full chronological log with topic and minimum priority filtering.

```python
# Event envelope structure
class SwarmEvent(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    event_type: EventType  # e.g., EventType.TASK_COMPLETED
    priority: EventPriority = EventPriority.NORMAL
    deal_id: Optional[str]
    source_role: Optional[AgentRole]
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

### 2.3 Model Context Protocol (MCP) Ingestion

The platform implements the Model Context Protocol (MCP) standard over JSON-RPC 2.0 via `MCPServerBase`:

```
               JSON-RPC 2.0 Request
   Client  ──────────────────────────────►  MCPServerBase
                                                 │
                                                 ├── ping
                                                 ├── tools/list
                                                 └── tools/call
                                                         │
                                             ┌───────────┴───────────┐
                                             ▼                       ▼
                                   MunicipalDeedMCPServer    SECEDGARMCPServer
```

#### Municipal Deed Recorder Server (`municipal-deed-recorder`)
Exposes three standardized tools for title verification:
1. `municipal_deed_fetch(apn, county, state)`: Retrieves recorded conveyance instruments matching parcel number and jurisdiction.
2. `municipal_deed_verify_chain(apn, reported_seller)`: Validates that the transaction seller matches the latest grantee of record on title.
3. `municipal_deed_audit_chain(apn)`: Performs forensic analysis of grantor-to-grantee continuity across history, detecting title gaps and identifying un-warranted quitclaim deeds.

#### SEC EDGAR Corporate Diligence Server (`sec-edgar-recorder`)
Exposes three standardized tools for corporate sponsor credit analysis:
1. `sec_filings_search(cik_or_ticker, form_types)`: Queries filings by CIK (automatically padded to 10 digits) or ticker across Form 10-K, 10-Q, and 8-K.
2. `sec_risk_factors_extract(accession_number)`: Extracts Item 1A Risk Factors classified into topics: `INTEREST_RATE_RISK`, `REFINANCING_RISK`, `TENANT_CONCENTRATION`, `LIQUIDITY_RISK`, `LITIGATION`, and `REGULATORY`.
3. `sec_sponsor_credit_assess(cik_or_ticker)`: Synthesizes credit risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), counts high-severity disclosures, and flags debt maturity cliff risks.

---

### 2.4 Hybrid Vector-Graph RAG Engine (`HybridRAGEngine`)

Diligence over unstructured Offering Memorandums combines dense semantic vector retrieval with property knowledge graph filtering:

#### Dense Embedding & Text Chunking
- Documents are partitioned into sliding text windows with configurable token chunks (default: 120 words) and overlap (default: 25 words).
- Generates 64-dimensional dense semantic vectors using normalized term-frequency and character hash projections:
$$\mathbf{v} \in \mathbb{R}^{64}, \quad \|\mathbf{v}\|_2 = 1.0$$
- Vector similarity is evaluated via Cosine Similarity:
$$\text{Sim}_{\text{dense}}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|} = \sum_{i=1}^{64} u_i v_i$$

#### Knowledge Graph Engine (`KnowledgeGraphEngine`)
- Graph representation consists of nodes (`GraphEntity`) and typed directed edges (`GraphRelation`):
  - **Entity Types**: `SPONSOR`, `PROPERTY`, `PARCEL`, `DEED`, `LENDER`, `TENANT`, `ENCUMBRANCE`.
  - **Relation Types**: `OWNS`, `TRANSFERRED_TO`, `SECURED_BY`, `LEASES_TO`, `LOCATED_IN`, `GUARANTEES`, `CROSS_COLLATERALIZED`.
- Graph Algorithms:
  - **Breadth-First Search (BFS)** for shortest path discovery between sponsors, borrowers, and encumbrances.
  - **Chain-of-Title Traversal** ordering chronological transfers and identifying broken links.
  - **Lien & Encumbrance Detection** totaling outstanding mortgage debt secured against the parcel.

#### Hybrid Fusion Scoring
The hybrid search score balances semantic relevance and graph entity overlap via parameter $\alpha \in [0, 1]$ (default: $0.6$):
$$\text{Score}_{\text{hybrid}} = \alpha \cdot \text{Score}_{\text{dense}} + (1 - \alpha) \cdot \text{Score}_{\text{graph}}$$

---

### 2.5 Quantitative DCF Valuation Engine (`DCFEngine`)

The valuation core executes high-precision, audit-ready discounted cash flow projections.

#### Pro-Forma Cash Flow Mechanics
For holding period year $t \in [1, N]$:
1. **Potential Gross Revenue (PGR)**:
$$\text{PGR}_t = \text{PGR}_0 \times (1 + g_{\text{rev}})^t$$
2. **Effective Gross Income (EGI)**:
$$\text{EGI}_t = \text{PGR}_t \times (1 - v_t)$$
3. **Operating Expenses (OpEx)**:
$$\text{OpEx}_t = \text{OpEx}_0 \times (1 + g_{\text{exp}})^t$$
4. **Net Operating Income (NOI)**:
$$\text{NOI}_t = \text{EGI}_t - \text{OpEx}_t$$
5. **Capital Expenditures & Replacement Reserves**:
$$\text{CapEx}_t = \text{Rentable SF} \times \text{Reserve PSF}$$
6. **Unlevered Cash Flow**:
$$\text{UCF}_t = \text{NOI}_t - \text{CapEx}_t$$
7. **Debt Service Deduction**:
$$\text{DS}_t = 12 \times (\text{Monthly Principal} + \text{Monthly Interest})$$
8. **Levered Cash Flow**:
$$\text{LCF}_t = \text{UCF}_t - \text{DS}_t$$

#### Exit Reversion & Net Disposition Proceeds
At exit year $N$:
$$\text{Disposition Price} = \frac{\text{NOI}_{N+1}}{\text{Exit Cap Rate}}$$
$$\text{Net Sales Proceeds} = \text{Disposition Price} \times (1 - \text{Sales Cost Pct}) - \text{Remaining Loan Balance}_N$$

#### Numerical IRR Root Finding (Newton-Raphson & Fallback)
The internal rate of return $r^*$ satisfies:
$$\text{NPV}(r^*) = \sum_{t=0}^N \frac{C_t}{(1 + r^*)^t} = 0$$

Newton-Raphson iteration:
$$r_{k+1} = r_k - \frac{\text{NPV}(r_k)}{\text{NPV}'(r_k)}$$
where the derivative is:
$$\text{NPV}'(r) = -\sum_{t=1}^N \frac{t \cdot C_t}{(1 + r)^{t+1}}$$

If Newton-Raphson diverges or encounters local extrema, the engine falls back to NumPy's polynomial companion matrix solver on discount factor $x = \frac{1}{1 + r}$.

#### Deterministic Model Checksum
To guarantee auditability and tamper-resistance, every DCF output computes an immutable SHA256 checksum:
$$\text{Checksum} = \text{SHA256}\left(\text{DealID} \,\|\, \text{PurchasePrice} \,\|\, \text{IRR} \,\|\, \text{NPV} \,\|\, \text{EquityMultiple} \,\|\, \text{CashFlows}\right)$$

---

### 2.6 Credit Risk & Policy Synthesis

#### Institutional Covenant Evaluation
The risk engine checks deal parameters against hard underwriting constraints:
- **Debt Service Coverage Ratio (DSCR)**:
$$\text{DSCR}_t = \frac{\text{NOI}_t}{\text{Annual Debt Service}_t} \ge 1.25\text{x}$$
- **Debt Yield**:
$$\text{Debt Yield} = \frac{\text{In-Place NOI}}{\text{Initial Loan Amount}} \ge 8.0\%$$
- **Loan-to-Value (LTV)**:
$$\text{LTV} = \frac{\text{Initial Loan Amount}}{\text{Purchase Price}} \le 75.0\%$$
- **Physical Occupancy**:
$$\text{Occupancy} = 1 - \frac{\text{Vacant Units}}{\text{Total Units}} \ge 85.0\%$$

#### Standard Downside Stress Testing
The engine automatically evaluates five macroeconomic stress scenarios:
1. **Mild Downturn**: Rent growth -3.0%, Vacancy +200 bps, Exit Cap +25 bps.
2. **Severe Recession**: Rent growth -10.0%, Vacancy +500 bps, OpEx +10.0%, Exit Cap +100 bps.
3. **Stagflation Shock**: Rent growth 0.0%, OpEx +15.0%, Exit Cap +75 bps.
4. **Major Tenant Default**: Rent growth -15.0%, Vacancy +1000 bps, Exit Cap +50 bps.
5. **Interest Rate Spike**: Refinancing exit rate +150 bps.

---

### 2.7 Portfolio Underwriting & Risk Engine

Aggregates individual asset underwritings into a consolidated investment book:
- **Weighted Average Return Metrics**: Dollar-weighted In-Place Cap Rate, Exit Cap Rate, Levered IRR, DSCR, and Debt Yield.
- **Concentration Analytics**:
  - Property type breakdown (Multifamily, Industrial, Office, Retail).
  - Geographic state distribution.
  - Sponsor concentration using the **Herfindahl-Hirschman Index (HHI)**:
$$\text{HHI} = \sum_{i=1}^M \left(\frac{\text{Value}_i}{\text{Total Portfolio Value}} \times 100\right)^2$$
- **Portfolio-Wide Macro Stress**: Evaluates combined equity degradation, portfolio DSCR decline, and defaulted loan amounts across the book.

---

### 2.8 Cryptographic Audit Trail Verification

Every diligence action generates a cryptographically hashed `AgentAuditEntry`. The `AuditTrailVerifier` inspects:
1. **Hash Format & Length**: Validates `sha256:` prefix and 64-character hexadecimal digest.
2. **Input Reproducibility**: Recomputes expected hash over task ID, deal ID, agent role, and serialized input artifacts.
3. **Monotonic Ordering**: Verifies strict chronological progression across all workflow events.
4. **Integrity Verdict**: Returns complete validation metrics detailing valid vs. invalid entries.

---

## 3. Data Flow & Execution Lifecycles

```
┌──────────────┐     1. Ingest OM & APN     ┌────────────────────────┐
│ Property Deal├───────────────────────────►│ Swarm Orchestrator     │
└──────────────┘                            └───────────┬────────────┘
                                                        │
                      2. Dispatches DAG Tasks           ▼
                      ┌──────────────────────────────────────────────┐
                      │ Agent 1: IngestionCoordinatorAgent           │
                      │ - Hybrid RAG chunking & vector indexing      │
                      │ Agent 2: MunicipalDeedAuditorAgent           │
                      │ - MCP deed queries & chain-of-title audit    │
                      │ Agent 3: SECDiligenceAnalystAgent            │
                      │ - SEC EDGAR 10-K Item 1A risk scanning       │
                      │ Agent 4: DCFValuationEngineerAgent           │
                      │ - Cash flow pro-forma & Newton-Raphson IRR   │
                      │ Agent 5: CreditRiskUnderwriterAgent          │
                      │ - Covenant checks, stress tests & checklist  │
                      │ Agent 6: InvestmentCommitteeChairAgent       │
                      │ - Committee sign-offs & Underwriting Memo    │
                      └─────────────────────────┬────────────────────┘
                                                │
                      3. Emits Events & Audits  ▼
                      ┌──────────────────────────────────────────────┐
                      │ InMemoryEventBus & AuditTrailVerifier        │
                      └─────────────────────────┬────────────────────┘
                                                │
                      4. Persists & Exports     ▼
                      ┌──────────────────────────────────────────────┐
                      │ DealRepository (.data/cre_store)             │
                      │ - Markdown Investment Committee Memo         │
                      │ - Pro-Forma Cash Flow Schedules (CSV/ASCII)  │
                      │ - Audit Trail & Checksum Reports             │
                      └──────────────────────────────────────────────┘
```

---

## 4. Software Design Patterns & Architectural Traits

1. **Protocol-First Interfaces**: All core engines, agents, and ingestors adhere to strict runtime-checkable `typing.Protocol` interfaces defined in `protocols.py`.
2. **Pydantic v2 Strong Typing**: Every domain model uses strict validation, frozen/forbid configs where appropriate, and built-in type conversions.
3. **Pure Python & Zero C-Extension Overhead**: Implemented with Python stdlib, `pydantic`, `numpy`, `click`, and `rich`.
4. **Offline Resilience & Determinism**: All engines operate deterministically without requiring live external internet connections, utilizing standardized seed datasets and MCP protocol adapters.

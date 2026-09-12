# Complete API Reference

This document provides an exhaustive, production-grade API reference for all packages, modules, classes, methods, protocols, and data models within **`autonomous-cre-underwriting`**.

---

## Table of Contents

1. [Domain Models & Types (`autonomous_cre_underwriting.types`)](#1-domain-models--types-autonomous_cre_underwritingtypes)
   - [Base (`types.base`)](#base-typesbase)
   - [Property & Deal Specifications (`types.property`)](#property--deal-specifications-typesproperty)
   - [Financial Modeling & DCF (`types.financial`)](#financial-modeling--dcf-typesfinancial)
   - [Events & Bus Contracts (`types.events`)](#events--bus-contracts-typesevents)
   - [Agent Swarm & Workflow State (`types.agents`)](#agent-swarm--workflow-state-typesagents)
   - [Ingestion & Document Sources (`types.ingestion`)](#ingestion--document-sources-typesingestion)
   - [Knowledge Graph Entities & Relations (`types.knowledge_graph`)](#knowledge-graph-entities--relations-typesknowledge_graph)
   - [Risk, Covenants & Underwriting Memos (`types.risk`)](#risk-covenants--underwriting-memos-typesrisk)
2. [Interface Protocols (`autonomous_cre_underwriting.protocols`)](#2-interface-protocols-autonomous_cre_underwritingprotocols)
3. [Quantitative & Diligence Engines (`autonomous_cre_underwriting.engine`)](#3-quantitative--diligence-engines-autonomous_cre_underwritingengine)
   - [Event Bus Engine (`engine.event_bus`)](#event-bus-engine-engineevent_bus)
   - [Knowledge Graph Engine (`engine.graph`)](#knowledge-graph-engine-enginegraph)
   - [Hybrid Vector-Graph RAG Engine (`engine.rag`)](#hybrid-vector-graph-rag-engine-enginerag)
   - [Discounted Cash Flow Engine (`engine.dcf`)](#discounted-cash-flow-engine-enginedcf)
   - [Credit Risk Synthesis Engine (`engine.risk`)](#credit-risk-synthesis-engine-enginerisk)
   - [Swarm Orchestrator Engine (`engine.orchestrator`)](#swarm-orchestrator-engine-engineorchestrator)
4. [Autonomous Diligence Agents (`autonomous_cre_underwriting.agents`)](#4-autonomous-diligence-agents-autonomous_cre_underwritingagents)
   - [Base Agent (`agents.base`)](#base-agent-agentsbase)
   - [Specialized Role Agents (`agents.specialized`)](#specialized-role-agents-agentsspecialized)
   - [Swarm Factory (`agents.swarm`)](#swarm-factory-agentsswarm)
5. [Model Context Protocol Servers (`autonomous_cre_underwriting.mcp`)](#5-model-context-protocol-servers-autonomous_cre_underwritingmcp)
   - [MCP Protocol Base (`mcp.protocol`)](#mcp-protocol-base-mcpprotocol)
   - [Municipal Deed Server (`mcp.municipal_deed`)](#municipal-deed-server-mcpmunicipal_deed)
   - [SEC EDGAR Server (`mcp.sec_edgar`)](#sec-edgar-server-mcpsec_edgar)
6. [Portfolio Risk & Policy Engine (`autonomous_cre_underwriting.portfolio`)](#6-portfolio-risk--policy-engine-autonomous_cre_underwritingportfolio)
   - [Portfolio Underwriter (`portfolio.engine`)](#portfolio-underwriter-portfolioengine)
   - [Policy Rules Engine (`portfolio.rules`)](#policy-rules-engine-portfoliorules)
   - [Portfolio Data Models (`portfolio.models`)](#portfolio-data-models-portfoliomodels)
7. [Reporting & Exporters (`autonomous_cre_underwriting.reporting`)](#7-reporting--exporters-autonomous_cre_underwritingreporting)
   - [IC Memo Exporter (`reporting.memo`)](#ic-memo-exporter-reportingmemo)
   - [DCF Schedule Exporter (`reporting.exporter`)](#dcf-schedule-exporter-reportingexporter)
   - [Audit Trail Verifier (`reporting.audit`)](#audit-trail-verifier-reportingaudit)
8. [Persistence Storage Repository (`autonomous_cre_underwriting.storage`)](#8-persistence-storage-repository-autonomous_cre_underwritingstorage)
9. [Command-Line Interface (`autonomous_cre_underwriting.cli`)](#9-command-line-interface-autonomous_cre_underwritingcli)

---

## 1. Domain Models & Types (`autonomous_cre_underwriting.types`)

### Base (`types.base`)

#### `generate_uuid() -> str`
Generates a random UUID v4 string for entities, events, tasks, and audit logs.

---

### Property & Deal Specifications (`types.property`)

#### `PropertyType(str, Enum)`
Enumeration of institutional real estate asset classes:
- `MULTIFAMILY = "multifamily"`
- `OFFICE = "office"`
- `INDUSTRIAL = "industrial"`
- `RETAIL = "retail"`
- `MIXED_USE = "mixed_use"`
- `HOSPITALITY = "hospitality"`
- `SELF_STORAGE = "self_storage"`
- `DATA_CENTER = "data_center"`

#### `DealStatus(str, Enum)`
Underwriting lifecycle states:
- `DRAFT = "draft"`
- `INTAKE = "intake"`
- `UNDERWRITING = "underwriting"`
- `IC_REVIEW = "ic_review"`
- `APPROVED = "approved"`
- `REJECTED = "rejected"`
- `ARCHIVED = "archived"`

#### `PropertyAddress(BaseModel)`
Normalized real property physical location and tax parcel metadata.
- **Fields**:
  - `street: str`: Street address line.
  - `city: str`: Municipality name.
  - `state: str`: 2-letter state abbreviation (validated via regex `^[A-Za-z]{2}$`).
  - `postal_code: str`: US ZIP code.
  - `county: str`: County jurisdiction name.
  - `apn: str`: Assessor Parcel Number.

#### `PropertyPhysical(BaseModel)`
Structural specifications and site geometry.
- **Fields**:
  - `gross_square_feet: float`: Total gross architectural square footage ($> 0$).
  - `rentable_square_feet: float`: Net leasable area ($> 0$, $\le \text{gross\_square\_feet}$).
  - `year_built: int`: Construction year ($1800 \le \text{year} \le 2100$).
  - `year_renovated: Optional[int]`: Year of substantial renovation ($\ge \text{year\_built}$).
  - `stories: int = 1`: Vertical building levels ($\ge 1$).
  - `site_area_acres: float = 1.0`: Site footprint in acres ($> 0$).
  - `parking_spaces: int = 0`: Total dedicated parking stalls ($\ge 0$).
  - `zoning: Optional[str] = None`: Municipal zoning designation.

#### `UnitSpec(BaseModel)`
Specification for a specific unit type within a property.
- **Fields**:
  - `unit_type: str`: Floorplan designation (e.g., "1B1B", "2B2B", "Suite 400").
  - `count: int`: Total number of units of this type ($\ge 1$).
  - `square_feet: float`: Average rentable square feet per unit ($> 0$).
  - `in_place_rent: float`: Current contractual monthly rent per unit ($\ge 0$).
  - `market_rent: float`: Prevailing market monthly rent per unit ($\ge 0$).
  - `vacant_count: int = 0`: Currently unoccupied units ($0 \le \text{vacant\_count} \le \text{count}$).
- **Properties**:
  - `monthly_in_place_revenue -> float`: Count $\times$ in-place rent.
  - `monthly_market_revenue -> float`: Count $\times$ market rent.
  - `occupancy_rate -> float`: $1.0 - \frac{\text{vacant\_count}}{\text{count}}$.

#### `UnitMix(BaseModel)`
Aggregated unit inventory across all floorplans.
- **Fields**:
  - `items: List[UnitSpec]`: List of unit plan configurations.
- **Properties**:
  - `total_units -> int`: Total unit count across all floorplans.
  - `total_vacant_units -> int`: Total unoccupied units.
  - `physical_occupancy_rate -> float`: Overall portfolio occupancy percentage.
  - `weighted_in_place_rent -> float`: Rent-weighted average in-place monthly rent.
  - `weighted_market_rent -> float`: Rent-weighted average market monthly rent.
  - `in_place_monthly_potential -> float`: Aggregate monthly rent roll.
  - `market_monthly_potential -> float`: Pro-forma monthly potential.
  - `loss_to_lease_monthly -> float`: Monthly spread between market and contractual rent.

#### `OperatingExpenses(BaseModel)`
Itemized operational expense line items.
- **Fields**:
  - `property_taxes: float = 0.0`: Real estate ad valorem taxes.
  - `insurance: float = 0.0`: Property & casualty insurance premium.
  - `utilities: float = 0.0`: Water, sewer, electric, gas.
  - `repairs_and_maintenance: float = 0.0`: Day-to-day R&M budget.
  - `management_fee_pct: float = 0.03`: Third-party property management fee ($0.0 \le \text{pct} \le 0.15$).
  - `general_administrative: float = 0.0`: Legal, accounting, software, marketing.
  - `capital_reserve_psf: float = 0.25`: Replacement reserves per rentable SF.
  - `other_expenses: float = 0.0`: Ancillary operational expenses.
- **Methods**:
  - `total_operating_expenses(effective_gross_income: float, rentable_sf: float) -> float`: Evaluates total operational outflows including variable management fees and reserves.

#### `HistoricalFinancials(BaseModel)`
Past accounting records (T12, prior calendar years).
- **Fields**:
  - `period_name: str`: E.g., "Trailing 12-Month", "2024 Audited".
  - `year: int`: Fiscal year of records.
  - `effective_gross_income: float`: Historical revenue collected.
  - `operating_expenses: float`: Historical operational expenses.
  - `net_operating_income: float`: Net operating income ($\text{EGI} - \text{OpEx}$).
  - `capital_expenditures: float = 0.0`: Historical capital improvements.

#### `PropertyDeal(BaseModel)`
Master commercial real estate underwriting file.
- **Fields**:
  - `id: str = Field(default_factory=generate_uuid)`
  - `title: str`: Deal descriptive name.
  - `property_type: PropertyType`: Asset classification.
  - `status: DealStatus = DealStatus.INTAKE`: Current deal stage.
  - `address: PropertyAddress`: Physical location and APN.
  - `physical: PropertyPhysical`: Physical building dimensions.
  - `unit_mix: UnitMix`: Floorplan composition and rent roll.
  - `expenses: OperatingExpenses`: Baseline operational expenses.
  - `asking_price: float`: Broker guidance / seller list price.
  - `target_purchase_price: float`: Underwritten purchase basis.
  - `in_place_noi: float`: Baseline contractual Net Operating Income.
  - `sponsor_name: str`: Borrower / general partner legal entity.
  - `broker_name: Optional[str] = None`: Sponsoring brokerage firm.
  - `historical_financials: List[HistoricalFinancials] = []`: Prior financial statements.
- **Properties**:
  - `in_place_cap_rate -> float`: $\frac{\text{in\_place\_noi}}{\text{asking\_price}}$.
  - `target_cap_rate -> float`: $\frac{\text{in\_place\_noi}}{\text{target\_purchase\_price}}$.
  - `price_per_sqft -> float`: Basis per rentable square foot.
  - `price_per_unit -> float`: Basis per apartment unit or commercial bay.

---

### Financial Modeling & DCF (`types.financial`)

#### `FinancingAssumptions(BaseModel)`
Lender terms and debt structuring parameters.
- **Fields**:
  - `loan_to_value: float = 0.65`: Loan-to-Cost / Loan-to-Value ratio ($0.0 \le \text{LTV} \le 0.90$).
  - `interest_rate: float = 0.065`: Annual nominal coupon rate ($0.0 \le \text{rate} \le 0.25$).
  - `amortization_years: int = 30`: Amortization schedule ($1 \le \text{years} \le 40$).
  - `term_years: int = 5`: Maturity balloon date ($1 \le \text{term} \le 40$).
  - `interest_only_years: int = 0`: Interest-only holiday period ($0 \le \text{io} \le \text{term\_years}$).
  - `lender_name: Optional[str] = None`: Originating financing institution.
  - `loan_amount: float = 0.0`: Principal loan balance.
- **Properties**:
  - `monthly_interest_rate -> float`: $\frac{\text{interest\_rate}}{12}$.
  - `annual_debt_service -> float`: Annual principal and interest payment.
  - `monthly_debt_service -> float`: Periodic monthly debt service.

#### `DCFParameters(BaseModel)`
Macroeconomic underwriting assumptions and holding criteria.
- **Fields**:
  - `holding_period_years: int = 5`: Investment analysis horizon ($1 \le N \le 20$).
  - `discount_rate: float = 0.09`: Periodic discount rate for NPV calculations.
  - `exit_cap_rate: float = 0.065`: Reversion capitalization rate.
  - `general_inflation_rate: float = 0.025`: Baseline inflation factor.
  - `revenue_growth_rate: float = 0.03`: Annual compounded rent growth.
  - `expense_growth_rate: float = 0.025`: Annual compounded expense inflation.
  - `general_vacancy_rate: float = 0.05`: Underwritten economic vacancy floor.
  - `sales_cost_pct: float = 0.02`: Brokerage and transfer costs at disposition.

#### `AnnualCashFlow(BaseModel)`
Granular line-item cash flow for a single pro-forma operating year.
- **Fields**:
  - `year: int`: Operational year index ($1, \dots, N$).
  - `potential_gross_revenue: float`: Gross potential income.
  - `vacancy_and_credit_loss: float`: Deductions for vacancy/bad debt.
  - `effective_gross_income: float`: Net realized collections.
  - `operating_expenses: float`: Total operational expenditures.
  - `net_operating_income: float`: $\text{EGI} - \text{OpEx}$.
  - `capex_reserves: float`: Replacement capital reserves.
  - `unlevered_cash_flow: float`: $\text{NOI} - \text{CapEx}$.
  - `debt_service: float`: Principal and interest paid.
  - `levered_cash_flow: float`: Cash flow after debt service.
  - `ending_loan_balance: float`: Remaining principal at year end.
  - `dscr: float`: Debt Service Coverage Ratio.
  - `debt_yield: float`: $\frac{\text{NOI}}{\text{Ending Loan Balance}}$.

#### `ValuationMetrics(BaseModel)`
Consolidated return and credit performance benchmarks.
- **Fields**:
  - `levered_irr: float`: Internal Rate of Return to equity holders.
  - `unlevered_irr: float`: Property-level unlevered return.
  - `equity_multiple: float`: Cumulative cash distributions divided by initial equity.
  - `net_present_value: float`: Net Present Value at underwritten discount rate.
  - `average_dscr: float`: Arithmetic mean DSCR across the holding period.
  - `min_dscr_observed: float`: Lowest observed single-year DSCR.
  - `terminal_exit_price: float`: Gross disposition valuation.
  - `net_sales_proceeds: float`: Net exit cash distributed after debt payoff.
  - `equity_invested: float`: Initial sponsor and limited partner equity capital.

#### `SensitivityScenario(BaseModel)`
Point evaluation in a 2D sensitivity matrix:
- `exit_cap_rate: float`: Scenario exit cap.
- `revenue_growth_rate: float`: Scenario annual revenue growth.
- `levered_irr: float`: Scenario levered return.
- `unlevered_irr: float`: Scenario unlevered return.
- `equity_multiple: float`: Scenario multiple.
- `net_present_value: float`: Scenario NPV.

#### `SensitivityMatrix(BaseModel)`
Two-dimensional sensitivity grid:
- `base_exit_cap: float`: Baseline exit cap rate.
- `base_growth: float`: Baseline rent growth rate.
- `exit_caps: List[float]`: Grid column values.
- `revenue_growths: List[float]`: Grid row values.
- `matrix: List[List[SensitivityScenario]]`: 2D evaluation cells.

#### `DCFValuationResult(BaseModel)`
Complete valuation model output with cryptographic integrity signature.
- **Fields**:
  - `deal_id: str`: Associated deal identifier.
  - `parameters: DCFParameters`: Applied underwriting assumptions.
  - `financing: FinancingAssumptions`: Applied debt assumptions.
  - `annual_cash_flows: List[AnnualCashFlow]`: Multi-year schedules.
  - `metrics: ValuationMetrics`: Summary performance return indicators.
  - `sensitivity: SensitivityMatrix`: 2D sensitivity table.
  - `model_checksum: str`: Immutable SHA256 digest guaranteeing reproducibility.

---

### Events & Bus Contracts (`types.events`)

#### `EventType(str, Enum)`
Swarm orchestration event topics:
- `DEAL_CREATED = "deal.created"`
- `DEAL_UPDATED = "deal.updated"`
- `INGESTION_STARTED = "ingestion.started"`
- `INGESTION_COMPLETED = "ingestion.completed"`
- `DEED_AUDIT_COMPLETED = "deed.audit.completed"`
- `SEC_DILIGENCE_COMPLETED = "sec.diligence.completed"`
- `DCF_MODEL_COMPLETED = "dcf.model.completed"`
- `RISK_SYNTHESIS_COMPLETED = "risk.synthesis.completed"`
- `MEMO_GENERATED = "memo.generated"`
- `TASK_STARTED = "task.started"`
- `TASK_COMPLETED = "task.completed"`
- `TASK_FAILED = "task.failed"`
- `WORKFLOW_STARTED = "workflow.started"`
- `WORKFLOW_COMPLETED = "workflow.completed"`

#### `EventPriority(str, Enum)`
Priority levels: `LOW`, `NORMAL`, `HIGH`, `CRITICAL`.

#### `SwarmEvent(BaseModel)`
Event dispatch packet published over the event bus.
- **Fields**:
  - `id: str = Field(default_factory=generate_uuid)`
  - `event_type: EventType`: Event routing topic.
  - `priority: EventPriority = EventPriority.NORMAL`: Priority rank.
  - `deal_id: Optional[str] = None`: Target deal.
  - `source_role: Optional[AgentRole] = None`: Originating agent role.
  - `payload: Dict[str, Any]`: Event message contents.
  - `timestamp: datetime`: Creation timestamp.

---

### Agent Swarm & Workflow State (`types.agents`)

#### `AgentRole(str, Enum)`
Six specialized underwriting roles:
- `INGESTION_COORDINATOR = "ingestion_coordinator"`
- `MUNICIPAL_DEED_AUDITOR = "municipal_deed_auditor"`
- `SEC_DILIGENCE_ANALYST = "sec_diligence_analyst"`
- `DCF_VALUATION_ENGINEER = "dcf_valuation_engineer"`
- `CREDIT_RISK_UNDERWRITER = "credit_risk_underwriter"`
- `INVESTMENT_COMMITTEE_CHAIR = "investment_committee_chair"`

#### `TaskStatus(str, Enum)`
Lifecycle status of an agent task: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `SKIPPED`.

#### `AgentTask(BaseModel)`
Unit of work assigned to a specialized agent.
- **Fields**:
  - `id: str = Field(default_factory=generate_uuid)`
  - `role: AgentRole`: Assigned agent.
  - `deal_id: str`: Associated deal.
  - `description: str`: Natural language instructions.
  - `status: TaskStatus = TaskStatus.PENDING`: Current status.
  - `input_artifacts: Dict[str, Any] = {}`: Input models and data.
  - `output_artifacts: Dict[str, Any] = {}`: Produced findings and calculations.
  - `error_message: Optional[str] = None`: Traceback detail if failed.
  - `created_at: datetime`
  - `completed_at: Optional[datetime] = None`

#### `AgentAuditEntry(BaseModel)`
Cryptographic record of an agent decision.
- **Fields**:
  - `entry_id: str = Field(default_factory=generate_uuid)`
  - `task_id: str`: Reference task ID.
  - `role: AgentRole`: Agent role.
  - `action_taken: str`: Action description.
  - `justification: str`: Detailed rationale.
  - `input_hash: str`: SHA256 digest of input parameters.
  - `timestamp: datetime`

#### `SwarmWorkflowState(BaseModel)`
State container for a deal's multi-agent workflow DAG.
- **Fields**:
  - `id: str = Field(default_factory=generate_uuid)`
  - `deal_id: str`: Target deal ID.
  - `is_active: bool = True`: Workflow in-flight flag.
  - `is_terminal: bool = False`: Workflow termination flag.
  - `tasks: List[AgentTask] = []`: Ordered list of tasks in DAG.
  - `audit_trail: List[AgentAuditEntry] = []`: Monotonic ledger of audit entries.
  - `error: Optional[str] = None`: Unhandled workflow error if aborted.

---

### Ingestion & Document Sources (`types.ingestion`)

#### `DeedType(str, Enum)`
Real estate conveyance instrument classifications:
- `WARRANTY_DEED = "warranty_deed"`
- `SPECIAL_WARRANTY_DEED = "special_warranty_deed"`
- `QUITCLAIM_DEED = "quitclaim_deed"`
- `GRANT_DEED = "grant_deed"`
- `TRUSTEES_DEED = "trustees_deed"`

#### `SECFormType(str, Enum)`
EDGAR regulatory submission types:
- `FORM_10K = "10-K"`
- `FORM_10Q = "10-Q"`
- `FORM_8K = "8-K"`
- `DEF_14A = "DEF 14A"`

#### `SECRiskTopic(str, Enum)`
Diligence risk taxonomies:
- `INTEREST_RATE_RISK = "interest_rate_risk"`
- `REFINANCING_RISK = "refinancing_risk"`
- `TENANT_CONCENTRATION = "tenant_concentration"`
- `LIQUIDITY_RISK = "liquidity_risk"`
- `LITIGATION = "litigation"`
- `REGULATORY = "regulatory"`

#### `DeedRecord(BaseModel)`
Recorded municipal deed instrument.
- **Fields**: `document_number`, `recording_date`, `county_name`, `state`, `grantor`, `grantee`, `deed_type`, `consideration_amount`, `parcel_number`, `legal_description`.

#### `SECRiskMention(BaseModel)`
Extracted Item 1A disclosure excerpt.
- **Fields**: `topic`, `excerpt`, `item_section`, `severity_score` ($0.0 \le s \le 1.0$), `relevance_score` ($0.0 \le r \le 1.0$).

#### `SECFiling(BaseModel)`
Corporate regulatory filing with extracted risk items.
- **Fields**: `accession_number`, `form_type`, `filing_date`, `cik`, `company_name`, `risk_mentions`.

#### `DocumentChunk(BaseModel)`
Segmented block of text from an Offering Memorandum.
- **Fields**: `chunk_id`, `document_title`, `text`, `embedding` (64-dim vector), `metadata`.

#### `OfferingMemorandum(BaseModel)`
Full property sales prospectus: `deal_id`, `title`, `raw_text`, `chunks`.

---

### Knowledge Graph Entities & Relations (`types.knowledge_graph`)

#### `EntityType(str, Enum)`
Node taxonomies: `SPONSOR`, `PROPERTY`, `PARCEL`, `DEED`, `LENDER`, `TENANT`, `ENCUMBRANCE`.

#### `RelationType(str, Enum)`
Edge taxonomies: `OWNS`, `TRANSFERRED_TO`, `SECURED_BY`, `LEASES_TO`, `LOCATED_IN`, `GUARANTEES`, `CROSS_COLLATERALIZED`.

#### `GraphEntity(BaseModel)`
Graph node: `entity_id`, `entity_type`, `label`, `properties: Dict[str, Any]`.

#### `GraphRelation(BaseModel)`
Directed graph edge: `relation_id`, `source_id`, `target_id`, `relation_type`, `properties: Dict[str, Any]`.

#### `KnowledgeGraph(BaseModel)`
Connected subgraph: `deal_id`, `entities: List[GraphEntity]`, `relations: List[GraphRelation]`.

---

### Risk, Covenants & Underwriting Memos (`types.risk`)

#### `RiskSeverity(str, Enum)`
Severity classifications: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

#### `RiskCategory(str, Enum)`
Risk categories: `TITLE_LEGAL`, `SPONSOR_CREDIT`, `MARKET_LEASING`, `PHYSICAL_ASSET`, `FINANCIAL_DEBT`, `REGULATORY_ENVIRONMENTAL`.

#### `ChecklistStatus(str, Enum)`
Verification statuses: `PASS`, `FAIL`, `WAIVED`, `PENDING`.

#### `MemoRecommendation(str, Enum)`
Investment Committee outcomes:
- `STRONGLY_RECOMMEND = "strongly_recommend"`
- `APPROVE_WITH_CONDITIONS = "approve_with_conditions"`
- `DEFER_FOR_FURTHER_DILIGENCE = "defer_for_further_diligence"`
- `REJECT = "reject"`

#### `RiskFinding(BaseModel)`
Flagged underwriting risk: `finding_id`, `title`, `category`, `severity`, `description`, `evidence_citation`, `impact_summary`, `proposed_mitigation`, `confirmed_by_role`.

#### `DiligenceChecklistItem(BaseModel)`
Credit policy requirement checklist item: `item_id`, `category`, `requirement`, `status`, `comments`, `verified_by_role`.

#### `StressScenario(BaseModel)`
Downside stress shock test evaluation: `name`, `rent_shock_pct`, `vacancy_shock_pct`, `opex_shock_pct`, `exit_cap_expansion_bps`, `resultant_irr`, `resultant_equity_multiple`, `min_dscr_observed`, `covenant_breached`.

#### `SignOff(BaseModel)`
Formal agent sign-off: `role`, `recommendation`, `rationale`, `timestamp`.

#### `UnderwritingMemo(BaseModel)`
Final publication-ready Investment Committee dossier: `memo_id`, `deal_id`, `deal_title`, `executive_summary`, `valuation_summary`, `risk_findings`, `diligence_checklist`, `stress_scenarios`, `conditions_precedent`, `recommendation`, `sign_offs`, `created_at`.

---

## 2. Interface Protocols (`autonomous_cre_underwriting.protocols`)

All system subsystems are governed by runtime-checkable `typing.Protocol` interfaces:

```python
@runtime_checkable
class EventHandlerProtocol(Protocol):
    def __call__(self, event: SwarmEvent) -> None: ...


@runtime_checkable
class EventBusProtocol(Protocol):
    def publish(self, event: SwarmEvent) -> None: ...
    def subscribe(self, event_type: str, handler: EventHandlerProtocol) -> None: ...
    def unsubscribe(self, event_type: str, handler: EventHandlerProtocol) -> None: ...


@runtime_checkable
class DeedIngestorProtocol(Protocol):
    def fetch_deed_records(self, apn: str, county: str, state: str) -> List[DeedRecord]: ...
    def verify_chain_of_title(self, apn: str, reported_seller: str) -> bool: ...


@runtime_checkable
class SECIngestorProtocol(Protocol):
    def search_filings(
        self, cik_or_ticker: str, form_types: Optional[List[str]] = None
    ) -> List[SECFiling]: ...
    def extract_risk_factors(self, accession_number: str) -> List[Dict[str, Any]]: ...


@runtime_checkable
class KnowledgeGraphStoreProtocol(Protocol):
    def upsert_entity(self, entity: GraphEntity) -> None: ...
    def upsert_relation(self, relation: GraphRelation) -> None: ...
    def get_graph_for_deal(self, deal_id: str) -> KnowledgeGraph: ...
    def find_entities_by_type(self, entity_type: EntityType) -> List[GraphEntity]: ...


@runtime_checkable
class RAGEngineProtocol(Protocol):
    def index_document(self, memorandum: OfferingMemorandum) -> int: ...
    def hybrid_search(self, query: str, deal_id: str, top_k: int = 5) -> List[DocumentChunk]: ...


@runtime_checkable
class DCFEngineProtocol(Protocol):
    def compute_valuation(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials] = None,
    ) -> DCFValuationResult: ...


@runtime_checkable
class AgentProtocol(Protocol):
    @property
    def role(self) -> AgentRole: ...
    def execute_task(self, task: AgentTask, context: SwarmWorkflowState) -> AgentTask: ...
    def produce_audit_entry(
        self, task: AgentTask, action: str, rationale: str
    ) -> AgentAuditEntry: ...


@runtime_checkable
class SwarmOrchestratorProtocol(Protocol):
    def initialize_workflow(self, deal: PropertyDeal) -> SwarmWorkflowState: ...
    def advance_workflow(self, workflow_id: str) -> SwarmWorkflowState: ...
    def generate_underwriting_memo(
        self, deal_id: str, deal: Optional[PropertyDeal] = None
    ) -> UnderwritingMemo: ...
```

---

## 3. Quantitative & Diligence Engines (`autonomous_cre_underwriting.engine`)

### Event Bus Engine (`engine.event_bus`)

#### `InMemoryEventBus`
Publish-subscribe dispatcher with wildcard subscriptions, error isolation, priority sorting, and dead-letter queues.
- `subscribe(event_type: str, handler: EventHandlerProtocol) -> None`: Subscribes a callable.
- `unsubscribe(event_type: str, handler: EventHandlerProtocol) -> None`: Removes subscription.
- `publish(event: SwarmEvent) -> None`: Dispatches event to matching subscribers. Catches exceptions and logs to dead letter entries.
- `get_history(event_type: Optional[str] = None, min_priority: Optional[EventPriority] = None) -> List[SwarmEvent]`: Queries history.
- `get_dead_letters() -> List[DeadLetterEntry]`: Retrieves handler failure records.
- `clear() -> None`: Clears bus state.

---

### Knowledge Graph Engine (`engine.graph`)

#### `KnowledgeGraphEngine`
In-memory property knowledge graph store with BFS path discovery, chain-of-title verification, and lien detection.
- `upsert_entity(entity: GraphEntity, deal_id: Optional[str] = None) -> None`: Inserts or updates node.
- `upsert_relation(relation: GraphRelation) -> None`: Inserts or updates directed edge. Validates endpoint existence.
- `find_entities_by_type(entity_type: EntityType) -> List[GraphEntity]`: Filters nodes by type.
- `get_graph_for_deal(deal_id: str, max_depth: int = 2) -> KnowledgeGraph`: Extracts connected subgraph.
- `trace_chain_of_title(property_id: str) -> Tuple[List[Dict[str, Any]], bool]`: Evaluates title continuity and flags broken links.
- `detect_encumbrances_and_liens(property_id: str) -> Tuple[List[Dict[str, Any]], float]`: Traverses `SECURED_BY` relations and calculates total senior/junior debt encumbrances.
- `find_sponsor_portfolio(sponsor_id: str) -> List[GraphEntity]`: Discovers all properties owned by a given sponsor.
- `find_shortest_path(start_id: str, target_id: str) -> Optional[List[str]]`: BFS shortest path finder across graph relations.

---

### Hybrid Vector-Graph RAG Engine (`engine.rag`)

#### Helper Functions
- `tokenize(text: str) -> List[str]`: Lowercases, removes punctuation, and tokenizes strings.
- `compute_dense_embedding(text: str, dim: int = 64) -> List[float]`: Generates normalized 64-dimensional dense semantic feature vector.
- `cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float`: Evaluates dot product of unit vectors.
- `chunk_text(text: str, chunk_size: int = 120, overlap: int = 25) -> List[str]`: Sliding-window text segmentation.

#### `HybridRAGEngine`
Combines dense semantic vector search with keyword filters.
- `__init__(alpha: float = 0.6)`: Initializes hybrid balance weight $\alpha$.
- `index_document(memorandum: OfferingMemorandum) -> int`: Chunks and indexes an OM, returning indexed count.
- `hybrid_search(query: str, deal_id: str, top_k: int = 5) -> List[DocumentChunk]`: Returns top-$k$ context chunks ranked by hybrid fusion score.

---

### Discounted Cash Flow Engine (`engine.dcf`)

#### Numerical Solvers & Utility Functions
- `compute_irr(cash_flows: List[float], max_iter: int = 100, tol: float = 1e-7) -> float`: Robust Newton-Raphson IRR solver with fallback to polynomial companion matrix roots.
- `compute_npv(rate: float, cash_flows: List[float]) -> float`: Net present value of cash flows at discount rate.
- `generate_loan_amortization_schedule(financing: FinancingAssumptions) -> List[LoanAmortizationRow]`: Month-by-month debt schedule with interest-only handling.
- `compute_remaining_loan_balance(financing: FinancingAssumptions, year: int) -> float`: Calculates ending principal balance at end of specified year.
- `create_default_financing(deal: PropertyDeal) -> FinancingAssumptions`: Factory creating conservative 65% LTV financing structure.
- `create_default_parameters(deal: PropertyDeal, holding_period: int = 5) -> DCFParameters`: Factory generating market baseline parameters.
- `create_standard_stress_scenarios(deal: PropertyDeal, dcf_result: Optional[DCFValuationResult] = None) -> List[StressScenario]`: Pre-configures standard downside stress tests.

#### `DCFEngine`
- `compute_valuation(deal: PropertyDeal, parameters: DCFParameters, financing: FinancingAssumptions, t12: Optional[HistoricalFinancials] = None) -> DCFValuationResult`: Full pro-forma valuation schedule, metrics, and sensitivity matrix.
- `stress_test(deal: PropertyDeal, base_parameters: DCFParameters, financing: FinancingAssumptions, rent_shock_pct: float, vacancy_shock_pct: float, opex_shock_pct: float, exit_cap_expansion_bps: int) -> Tuple[float, float, float]`: Evaluates stressed levered IRR, equity multiple, and minimum DSCR under macroeconomic shocks.

---

### Credit Risk Synthesis Engine (`engine.risk`)

#### `RiskSynthesisEngine`
- `evaluate_covenant_compliance(deal: PropertyDeal, financing: FinancingAssumptions, dcf_result: DCFValuationResult) -> List[DiligenceChecklistItem]`: Evaluates DSCR, Debt Yield, LTV, and occupancy covenants.
- `build_standard_checklist(deal: PropertyDeal) -> List[DiligenceChecklistItem]`: Builds standard environmental, title, physical, and sponsor checklist.
- `synthesize_decision(deal: PropertyDeal, dcf_result: Optional[DCFValuationResult], checklist: List[DiligenceChecklistItem], risk_findings: List[RiskFinding]) -> MemoRecommendation`: Determines investment committee recommendation based on return hurdles and hard covenant failures.
- `generate_agent_sign_offs(deal: PropertyDeal, recommendation: MemoRecommendation, dcf_result: Optional[DCFValuationResult]) -> List[SignOff]`: Generates formal role-based approval signatures.
- `build_memo(deal: PropertyDeal, dcf_result: DCFValuationResult, checklist: List[DiligenceChecklistItem], stress_scenarios: List[StressScenario], risk_findings: List[RiskFinding]) -> UnderwritingMemo`: Synthesizes final comprehensive memorandum.

---

### Swarm Orchestrator Engine (`engine.orchestrator`)

#### `SwarmOrchestrator`
Coordinates multi-agent diligence DAG execution and IC memo production.
- `register_agent(agent: AgentProtocol) -> None`: Registers an agent instance.
- `initialize_workflow(deal: PropertyDeal) -> SwarmWorkflowState`: Bootstraps workflow state and populates ordered tasks.
- `advance_workflow(workflow_id: str) -> SwarmWorkflowState`: Advances the workflow by executing the next pending task. Automatically invokes built-in fallback routines if an external agent is not registered for that role.
- `generate_underwriting_memo(deal_id: str, deal: Optional[PropertyDeal] = None) -> UnderwritingMemo`: Assembles final memo.

---

## 4. Autonomous Diligence Agents (`autonomous_cre_underwriting.agents`)

### Base Agent (`agents.base`)

#### `BaseAgent(ABC)`
Abstract base class implementing `AgentProtocol`:
- `role: AgentRole`: Agent role identifier.
- `produce_audit_entry(task: AgentTask, action: str, rationale: str) -> AgentAuditEntry`: Generates cryptographically hashed audit entry for task action.
- `execute_task(task: AgentTask, context: SwarmWorkflowState) -> AgentTask`: Abstract method.

---

### Specialized Role Agents (`agents.specialized`)

#### `IngestionCoordinatorAgent(BaseAgent)`
Coordinates OM parsing, deed/SEC ingestion, and hybrid vector chunk indexing.

#### `MunicipalDeedAuditorAgent(BaseAgent)`
Audits recorded instruments, validates title chain continuity, and updates knowledge graph ownership nodes.

#### `SECDiligenceAnalystAgent(BaseAgent)`
Analyzes Form 10-K, 10-Q, 8-K filings for sponsor and anchor tenants, flags refinancing cliffs, and detects credit risks.

#### `DCFValuationEngineerAgent(BaseAgent)`
Builds multi-year pro-forma schedules, solves for levered/unlevered IRR, computes NPV, debt amortization, and 2D sensitivity matrix.

#### `CreditRiskUnderwriterAgent(BaseAgent)`
Evaluates credit covenants (DSCR, Debt Yield, LTV), compiles diligence checklist items, and runs standard downside stress shocks.

#### `InvestmentCommitteeChairAgent(BaseAgent)`
Aggregates findings from prior agents, collects committee sign-offs, determines investment recommendation, and prepares the Underwriting Memo.

---

### Swarm Factory (`agents.swarm`)

#### `create_agent_swarm(orchestrator, deed_ingestor, sec_ingestor) -> Dict[AgentRole, BaseAgent]`
Instantiates and configures all 6 specialized agents, binding them to the orchestrator and data ingestors.

---

## 5. Model Context Protocol Servers (`autonomous_cre_underwriting.mcp`)

### MCP Protocol Base (`mcp.protocol`)

- `MCPTool`: Pydantic model defining tool metadata and JSON Schema.
- `MCPRequest`: JSON-RPC 2.0 request envelope.
- `MCPResponse`: JSON-RPC 2.0 response envelope.
- `MCPServerBase`: Dispatch handler managing tool registration, JSON-RPC handling, and ping endpoints.

---

### Municipal Deed Server (`mcp.municipal_deed`)

#### `DeedIngestor`
Municipal deed recorder repository implementing `DeedIngestorProtocol`:
- `add_record(record: DeedRecord) -> None`: Caches deed instrument.
- `fetch_deed_records(apn: str, county: str, state: str) -> List[DeedRecord]`: Retrieves records.
- `verify_chain_of_title(apn: str, reported_seller: str) -> bool`: Verifies recorded ownership against reported seller.
- `audit_chain_of_title(apn: str) -> Dict[str, Any]`: Traverses deed sequence, flags quitclaims, and checks continuity.

#### `MunicipalDeedMCPServer(MCPServerBase)`
Exposes tools `municipal_deed_fetch`, `municipal_deed_verify_chain`, and `municipal_deed_audit_chain`.

---

### SEC EDGAR Server (`mcp.sec_edgar`)

#### `SECIngestor`
SEC filing store implementing `SECIngestorProtocol`:
- `normalize_cik(cik_or_ticker: str) -> str`: Normalizes CIK to 10 digits or returns uppercase ticker.
- `add_filing(filing: SECFiling) -> None`: Registers SEC filing.
- `search_filings(cik_or_ticker: str, form_types: Optional[List[str]] = None) -> List[SECFiling]`: Queries filings.
- `extract_risk_factors(accession_number: str) -> List[Dict[str, Any]]`: Parses Item 1A Risk Factors.
- `assess_sponsor_credit(cik_or_ticker: str) -> Dict[str, Any]`: Evaluates sponsor credit risk level.

#### `SECEDGARMCPServer(MCPServerBase)`
Exposes tools `sec_filings_search`, `sec_risk_factors_extract`, and `sec_sponsor_credit_assess`.

---

## 6. Portfolio Risk & Policy Engine (`autonomous_cre_underwriting.portfolio`)

### Portfolio Underwriter (`portfolio.engine`)

#### `PortfolioUnderwriter`
Consolidates individual asset underwritings into a portfolio book:
- `add_deal(deal: PropertyDeal, dcf_result: Optional[DCFValuationResult] = None) -> DealRollupItem`: Adds/updates deal.
- `remove_deal(deal_id: str) -> bool`: Removes deal by ID.
- `get_deals() -> List[DealRollupItem]`: Lists portfolio deals.
- `compute_portfolio_summary() -> PortfolioSummary`: Calculates total book valuation, aggregate debt, equity, and dollar-weighted metrics (Cap Rate, Exit Cap, IRR, DSCR, Debt Yield).
- `compute_concentration() -> ConcentrationMetrics`: Evaluates property type breakdown, geographic distribution, and sponsor HHI index.
- `simulate_portfolio_stress(rent_shock_pct: float = -0.10, vacancy_shock_bps: int = 500, opex_shock_pct: float = 0.10, cap_expansion_bps: int = 75) -> PortfolioStressImpact`: Evaluates portfolio-wide macro stress impact, resulting portfolio DSCR, and defaulted loans.

---

### Policy Rules Engine (`portfolio.rules`)

#### `UnderwritingCriteria(BaseModel)`
Institutional underwriting policy guidelines:
- `min_dscr: float = 1.25`: Minimum acceptable DSCR.
- `min_debt_yield: float = 0.08`: Minimum acceptable Debt Yield.
- `max_ltv: float = 0.75`: Maximum permitted Loan-to-Value.
- `min_levered_irr: float = 0.12`: Target hurdle rate for levered return.
- `min_occupancy: float = 0.85`: Minimum acceptable physical occupancy.
- `max_sponsor_concentration: float = 0.35`: Maximum portfolio allocation to a single sponsor.

#### `UnderwritingRulesEngine`
Evaluates deals against institutional policy guidelines:
- `evaluate_deal(deal: PropertyDeal, dcf_result: Optional[DCFValuationResult] = None) -> PolicyCheckResult`: Checks all parameters and returns detailed status (`COMPLIANT`, `WARNING`, `BREACH`).
- `evaluate_portfolio(portfolio_deals: List[PropertyDeal]) -> List[PolicyCheckResult]`: Evaluates entire portfolio.

---

## 7. Reporting & Exporters (`autonomous_cre_underwriting.reporting`)

### IC Memo Exporter (`reporting.memo`)

#### `MemoExporter`
- `to_markdown(memo: UnderwritingMemo) -> str`: Renders publication-ready Markdown Underwriting Memorandum with tables, risk citations, and sign-offs.
- `to_summary_text(memo: UnderwritingMemo) -> str`: Produces concise plain-text executive summary.
- `to_dict(memo: UnderwritingMemo) -> Dict[str, Any]`: Serializes memo to dictionary.

---

### DCF Schedule Exporter (`reporting.exporter`)

#### `DCFScheduleExporter`
- `to_csv(result: DCFValuationResult) -> str`: Exports multi-year pro-forma cash flows to standard CSV format.
- `to_markdown_table(result: DCFValuationResult) -> str`: Formats pro-forma schedule as Markdown table.
- `to_dict(result: DCFValuationResult) -> Dict[str, Any]`: Serializes DCF result to dictionary.

---

### Audit Trail Verifier (`reporting.audit`)

#### `AuditTrailVerifier`
- `compute_input_hash(task_id: str, deal_id: str, role: str, inputs: Dict[str, Any]) -> str`: Calculates SHA256 input digest formatted as `sha256:<hex>`.
- `verify_entry(entry: AgentAuditEntry, expected_task: Optional[AgentTask] = None) -> bool`: Validates entry structure, hash format, and reproducibility.
- `verify_workflow(state: SwarmWorkflowState) -> Dict[str, Any]`: Verifies complete workflow audit ledger for cryptographic integrity and monotonic chronological ordering.

---

## 8. Persistence Storage Repository (`autonomous_cre_underwriting.storage`)

#### `DealRepository`
Multi-entity storage repository providing in-memory caching and JSON file persistence:
- `save_deal(deal: PropertyDeal) -> None`: Stores deal.
- `get_deal(deal_id: str) -> Optional[PropertyDeal]`: Fetches deal by ID.
- `list_deals() -> List[PropertyDeal]`: Retrieves all deals.
- `delete_deal(deal_id: str) -> bool`: Deletes deal and associated files.
- `query_deals(...) -> List[PropertyDeal]`: Filters deals by status, property type, price range, or sponsor name.
- `save_memo(memo: UnderwritingMemo) -> None`: Stores IC memorandum.
- `get_memo(deal_id: str) -> Optional[UnderwritingMemo]`: Fetches memo.
- `list_memos() -> List[UnderwritingMemo]`: Lists all stored memos.
- `save_valuation(valuation: DCFValuationResult) -> None`: Stores valuation.
- `get_valuation(deal_id: str) -> Optional[DCFValuationResult]`: Fetches valuation.
- `save_workflow(state: SwarmWorkflowState) -> None`: Stores workflow state.
- `get_workflow(workflow_id: str) -> Optional[SwarmWorkflowState]`: Fetches workflow.
- `export_to_directory(directory_path: str) -> None`: Exports entire catalog to structured JSON folder (`deals/`, `memos/`, `valuations/`, `workflows/`).
- `import_from_directory(directory_path: str) -> None`: Imports saved JSON dossiers.

---

## 9. Command-Line Interface (`autonomous_cre_underwriting.cli`)

Registered entry points: `cre-swarm` and `autonomous-cre-underwriting`.

| Command | Arguments / Flags | Description |
| :--- | :--- | :--- |
| `cre-swarm deals list` | `--storage-dir`, `--property-type`, `--sponsor` | List registered deals with key metrics in a Rich table. |
| `cre-swarm deals show` | `<deal_id>`, `--storage-dir` | Display comprehensive property metadata, unit mix, and physical specifications. |
| `cre-swarm deals sample` | `--deal-id`, `--property-type`, `--storage-dir` | Generate and seed an institutional benchmark deal with unit mix and expenses. |
| `cre-swarm deals add` | Interactive options | Interactively register a new property deal with full validation. |
| `cre-swarm deals delete` | `<deal_id>`, `--storage-dir` | Delete a deal and associated underwriting artifacts. |
| `cre-swarm underwrite` | `<deal_id>`, `--storage-dir`, `--export-memo`, `--auto-advance/--no-auto-advance` | Execute full multi-agent swarm diligence workflow and generate IC memo. |
| `cre-swarm dcf` | `<deal_id>`, `--holding-period`, `--exit-cap`, `--discount-rate`, `--ltv`, `--rate`, `--format [table\|csv\|json]`, `--export-csv` | Compute pro-forma cash flows, Newton-Raphson IRR, DSCR, and 2D sensitivity. |
| `cre-swarm memo show` | `<deal_id>`, `--storage-dir` | Display synthesized Investment Committee Underwriting Memorandum. |
| `cre-swarm memo export` | `<deal_id>`, `--output`, `--storage-dir` | Export Investment Committee Memorandum to Markdown or JSON file. |
| `cre-swarm memo list` | `--storage-dir` | List all existing underwriting memos with committee recommendations. |
| `cre-swarm audit` | `<workflow_id_or_deal_id>`, `--storage-dir` | Cryptographically verify diligence audit trail and monotonic chronology. |
| `cre-swarm portfolio summary` | `--storage-dir` | Display consolidated portfolio metrics, total debt, equity, and weighted returns. |
| `cre-swarm portfolio stress` | `--rent-shock`, `--vacancy-shock-bps`, `--opex-shock`, `--cap-expansion-bps`, `--storage-dir` | Run portfolio-wide macroeconomic downside stress simulation. |
| `cre-swarm portfolio policy-check` | `--min-dscr`, `--min-dy`, `--max-ltv`, `--min-irr`, `--storage-dir` | Audit all portfolio deals against institutional credit covenants and policy rules. |
| `cre-swarm mcp deed` | `--action [fetch\|verify\|audit]`, `--apn`, `--county`, `--state`, `--seller` | Query Municipal Deed Recorder MCP server for title history and seller verification. |
| `cre-swarm mcp sec` | `--action [search\|risks\|assess]`, `--cik`, `--form-types`, `--accession` | Query SEC EDGAR MCP server for filings, Item 1A risk factors, and credit risk score. |

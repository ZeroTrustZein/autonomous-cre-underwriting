"""Domain data models for multi-asset portfolio roll-up and risk aggregation."""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from autonomous_cre_underwriting.types.property import PropertyType


class DealRollupItem(BaseModel):
    """Normalized snapshot of a single property deal for portfolio aggregation."""

    model_config = ConfigDict(extra="forbid")

    deal_id: str = Field(..., description="Unique deal identifier")
    title: str = Field(..., description="Property or deal name")
    property_type: PropertyType = Field(..., description="CRE asset class")
    state: str = Field(..., description="US State code")
    sponsor_name: str = Field(..., description="Deal sponsor or GP entity")
    purchase_price: float = Field(..., ge=0.0, description="Agreed or target acquisition price")
    in_place_noi: float = Field(..., description="In-place net operating income")
    cap_rate: float = Field(..., ge=0.0, description="In-place capitalization rate")
    loan_amount: float = Field(default=0.0, ge=0.0, description="Senior debt principal")
    equity_amount: float = Field(default=0.0, ge=0.0, description="Required sponsor/LP equity")
    dscr: float = Field(default=1.0, ge=0.0, description="Debt service coverage ratio")
    debt_yield: float = Field(default=0.0, ge=0.0, description="NOI divided by loan amount")
    levered_irr: float = Field(default=0.0, description="Projected levered internal rate of return")


class PortfolioSummary(BaseModel):
    """Aggregate financial and return indicators across multiple CRE holdings."""

    model_config = ConfigDict(extra="forbid")

    property_count: int = Field(..., ge=0, description="Total number of assets in portfolio")
    total_purchase_price: float = Field(..., ge=0.0, description="Gross portfolio basis")
    total_equity: float = Field(..., ge=0.0, description="Total capital invested")
    total_debt: float = Field(..., ge=0.0, description="Total outstanding debt principal")
    total_noi: float = Field(..., description="Combined annual net operating income")
    weighted_avg_cap_rate: float = Field(
        ..., ge=0.0, description="Value-weighted in-place cap rate"
    )
    weighted_avg_dscr: float = Field(..., ge=0.0, description="Debt-weighted debt service coverage")
    portfolio_debt_yield: float = Field(..., ge=0.0, description="Combined NOI / Combined Debt")
    portfolio_ltv: float = Field(..., ge=0.0, le=1.0, description="Combined Loan-to-Value ratio")


class ConcentrationMetrics(BaseModel):
    """Diversification and exposure metrics across asset types, geographies, and sponsors."""

    model_config = ConfigDict(extra="forbid")

    by_property_type: Dict[str, float] = Field(
        default_factory=dict, description="Share of portfolio value by asset class (0.0 - 1.0)"
    )
    by_geography: Dict[str, float] = Field(
        default_factory=dict, description="Share of portfolio value by US State (0.0 - 1.0)"
    )
    by_sponsor: Dict[str, float] = Field(
        default_factory=dict, description="Share of portfolio value by GP sponsor (0.0 - 1.0)"
    )
    top_asset_concentration_pct: float = Field(
        ..., ge=0.0, le=1.0, description="Largest single asset percentage of total basis"
    )


class PortfolioStressImpact(BaseModel):
    """Macro stress test outcome across the entire multi-asset book."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str = Field(..., description="Macro stress scenario identifier")
    base_noi: float = Field(..., description="Pre-stress combined portfolio NOI")
    stressed_noi: float = Field(..., description="Post-stress combined portfolio NOI")
    noi_drop_pct: float = Field(..., description="Percentage decline in combined NOI")
    stressed_dscr: float = Field(..., ge=0.0, description="Combined DSCR under stress")
    covenant_breaches_count: int = Field(
        ..., ge=0, description="Number of assets failing minimum DSCR covenant"
    )

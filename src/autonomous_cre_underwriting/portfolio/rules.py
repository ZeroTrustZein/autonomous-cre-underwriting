"""Underwriting policy rules engine and investment criteria compliance verification."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from autonomous_cre_underwriting.portfolio.models import ConcentrationMetrics, PortfolioSummary
from autonomous_cre_underwriting.types.financial import DCFValuationResult
from autonomous_cre_underwriting.types.property import PropertyDeal


class UnderwritingCriteria(BaseModel):
    """Institutional investment committee underwriting parameters and gating thresholds."""

    model_config = ConfigDict(extra="forbid")

    max_ltv: float = Field(default=0.75, ge=0.0, le=1.0, description="Maximum allowable Loan-To-Value ratio")
    min_dscr: float = Field(default=1.25, ge=0.0, description="Minimum acceptable Debt Service Coverage Ratio")
    min_debt_yield: float = Field(default=0.08, ge=0.0, description="Minimum initial Debt Yield (NOI / Loan)")
    min_levered_irr: float = Field(default=0.14, description="Minimum hurdle levered IRR")
    min_unlevered_irr: float = Field(default=0.08, description="Minimum hurdle unlevered IRR")
    min_equity_multiple: float = Field(default=1.60, ge=1.0, description="Target minimum equity multiple")
    max_single_asset_concentration: float = Field(
        default=0.35, ge=0.0, le=1.0, description="Maximum share of single asset in portfolio"
    )
    max_geographic_concentration: float = Field(
        default=0.50, ge=0.0, le=1.0, description="Maximum share of single state in portfolio"
    )


class RuleCheckResult(BaseModel):
    """Result of a single policy guideline compliance check."""

    model_config = ConfigDict(extra="forbid")

    rule_name: str = Field(..., description="Guideline name or policy section")
    passed: bool = Field(..., description="Whether guideline is satisfied")
    threshold: float = Field(..., description="Policy threshold or limit")
    actual_value: float = Field(..., description="Observed metric value")
    detail: str = Field(..., description="Evaluation rationale or status description")


class UnderwritingRulesEngine:
    """Evaluates deals and consolidated portfolios against investment committee underwriting rules."""

    def __init__(self, criteria: Optional[UnderwritingCriteria] = None) -> None:
        self.criteria = criteria if criteria is not None else UnderwritingCriteria()

    def evaluate_deal(
        self, deal: PropertyDeal, dcf_result: DCFValuationResult
    ) -> List[RuleCheckResult]:
        """Verify deal against institutional acquisition criteria."""
        results: List[RuleCheckResult] = []

        # 1. LTV Check
        purchase_price = dcf_result.metrics.purchase_price
        ltv = (
            dcf_result.financing.loan_amount / purchase_price
            if purchase_price > 0
            else 0.0
        )
        passed_ltv = ltv <= self.criteria.max_ltv
        results.append(
            RuleCheckResult(
                rule_name="Max LTV Policy",
                passed=passed_ltv,
                threshold=self.criteria.max_ltv,
                actual_value=round(ltv, 4),
                detail=f"LTV {ltv:.1%} is {'<= ' if passed_ltv else '> '}max limit {self.criteria.max_ltv:.1%}",
            )
        )

        # 2. Min DSCR Check
        min_dscr = dcf_result.metrics.min_dscr_observed
        passed_dscr = min_dscr >= self.criteria.min_dscr
        results.append(
            RuleCheckResult(
                rule_name="Min DSCR Policy",
                passed=passed_dscr,
                threshold=self.criteria.min_dscr,
                actual_value=round(min_dscr, 3),
                detail=f"Minimum DSCR {min_dscr:.2f}x is {'>= ' if passed_dscr else '< '}threshold {self.criteria.min_dscr:.2f}x",
            )
        )

        # 3. Debt Yield Check
        in_place_noi = deal.in_place_noi
        loan_amount = dcf_result.financing.loan_amount
        debt_yield = (in_place_noi / loan_amount) if loan_amount > 0 else 1.0
        passed_dy = debt_yield >= self.criteria.min_debt_yield
        results.append(
            RuleCheckResult(
                rule_name="Min Debt Yield Policy",
                passed=passed_dy,
                threshold=self.criteria.min_debt_yield,
                actual_value=round(debt_yield, 4),
                detail=f"In-place Debt Yield {debt_yield:.1%} is {'>= ' if passed_dy else '< '}hurdle {self.criteria.min_debt_yield:.1%}",
            )
        )

        # 4. Levered IRR Hurdle
        irr = dcf_result.metrics.levered_irr
        passed_irr = irr >= self.criteria.min_levered_irr
        results.append(
            RuleCheckResult(
                rule_name="Levered IRR Hurdle",
                passed=passed_irr,
                threshold=self.criteria.min_levered_irr,
                actual_value=round(irr, 4),
                detail=f"Levered IRR {irr:.1%} is {'>= ' if passed_irr else '< '}target {self.criteria.min_levered_irr:.1%}",
            )
        )

        # 5. Equity Multiple Hurdle
        em = dcf_result.metrics.equity_multiple
        passed_em = em >= self.criteria.min_equity_multiple
        results.append(
            RuleCheckResult(
                rule_name="Equity Multiple Hurdle",
                passed=passed_em,
                threshold=self.criteria.min_equity_multiple,
                actual_value=round(em, 2),
                detail=f"Equity Multiple {em:.2f}x is {'>= ' if passed_em else '< '}target {self.criteria.min_equity_multiple:.2f}x",
            )
        )

        return results

    def evaluate_portfolio(
        self, summary: PortfolioSummary, concentration: ConcentrationMetrics
    ) -> List[RuleCheckResult]:
        """Verify consolidated book against concentration and debt portfolio guidelines."""
        results: List[RuleCheckResult] = []

        # 1. Single Asset Concentration
        top_asset = concentration.top_asset_concentration_pct
        passed_top = top_asset <= self.criteria.max_single_asset_concentration
        results.append(
            RuleCheckResult(
                rule_name="Max Single Asset Exposure",
                passed=passed_top,
                threshold=self.criteria.max_single_asset_concentration,
                actual_value=round(top_asset, 4),
                detail=f"Top asset basis share {top_asset:.1%} is {'<= ' if passed_top else '> '}limit {self.criteria.max_single_asset_concentration:.1%}",
            )
        )

        # 2. Geographic Concentration
        max_geo = max(concentration.by_geography.values()) if concentration.by_geography else 0.0
        passed_geo = max_geo <= self.criteria.max_geographic_concentration
        results.append(
            RuleCheckResult(
                rule_name="Max Geographic State Exposure",
                passed=passed_geo,
                threshold=self.criteria.max_geographic_concentration,
                actual_value=round(max_geo, 4),
                detail=f"Max single state share {max_geo:.1%} is {'<= ' if passed_geo else '> '}limit {self.criteria.max_geographic_concentration:.1%}",
            )
        )

        # 3. Portfolio LTV
        passed_ltv = summary.portfolio_ltv <= self.criteria.max_ltv
        results.append(
            RuleCheckResult(
                rule_name="Portfolio Aggregate LTV",
                passed=passed_ltv,
                threshold=self.criteria.max_ltv,
                actual_value=round(summary.portfolio_ltv, 4),
                detail=f"Portfolio LTV {summary.portfolio_ltv:.1%} is {'<= ' if passed_ltv else '> '}cap {self.criteria.max_ltv:.1%}",
            )
        )

        return results

    @staticmethod
    def is_approved(results: List[RuleCheckResult]) -> bool:
        """Return True if all rules passed without exceptions."""
        return all(r.passed for r in results)

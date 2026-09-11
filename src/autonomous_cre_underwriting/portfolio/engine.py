"""Portfolio risk engine aggregating underwriting models across multi-asset books."""

from typing import Dict, List, Optional

from autonomous_cre_underwriting.portfolio.models import (
    ConcentrationMetrics,
    DealRollupItem,
    PortfolioStressImpact,
    PortfolioSummary,
)
from autonomous_cre_underwriting.types.financial import DCFValuationResult
from autonomous_cre_underwriting.types.property import PropertyDeal


class PortfolioUnderwriter:
    """Engine aggregating individual CRE asset underwritings into a consolidated portfolio view."""

    def __init__(self) -> None:
        self._deals: Dict[str, DealRollupItem] = {}

    def add_deal(
        self, deal: PropertyDeal, dcf_result: Optional[DCFValuationResult] = None
    ) -> DealRollupItem:
        """Add or update a deal in the portfolio book."""
        purchase_price = deal.target_purchase_price
        in_place_noi = deal.in_place_noi
        cap_rate = deal.in_place_cap_rate

        loan_amount = 0.0
        equity_amount = purchase_price
        dscr = 1.0
        debt_yield = 0.0
        levered_irr = 0.0

        if dcf_result is not None:
            loan_amount = dcf_result.financing.loan_amount
            equity_amount = dcf_result.metrics.equity_invested
            dscr = dcf_result.metrics.average_dscr
            debt_yield = in_place_noi / loan_amount if loan_amount > 0 else 0.0
            levered_irr = dcf_result.metrics.levered_irr
        else:
            # Standard conservative default sizing (65% LTV, 6.25% debt)
            loan_amount = purchase_price * 0.65
            equity_amount = purchase_price - loan_amount
            annual_ds = loan_amount * 0.0625
            dscr = in_place_noi / annual_ds if annual_ds > 0 else 1.0
            debt_yield = in_place_noi / loan_amount if loan_amount > 0 else 0.0

        item = DealRollupItem(
            deal_id=deal.id,
            title=deal.title,
            property_type=deal.property_type,
            state=deal.address.state.upper(),
            sponsor_name=deal.sponsor_name,
            purchase_price=purchase_price,
            in_place_noi=in_place_noi,
            cap_rate=cap_rate,
            loan_amount=loan_amount,
            equity_amount=equity_amount,
            dscr=dscr,
            debt_yield=debt_yield,
            levered_irr=levered_irr,
        )
        self._deals[deal.id] = item
        return item

    def remove_deal(self, deal_id: str) -> bool:
        """Remove a deal from the portfolio."""
        if deal_id in self._deals:
            del self._deals[deal_id]
            return True
        return False

    def get_deals(self) -> List[DealRollupItem]:
        """Return list of current deals in the portfolio."""
        return list(self._deals.values())

    def compute_portfolio_summary(self) -> PortfolioSummary:
        """Calculate consolidated value, debt, equity, and weighted metrics."""
        deals = list(self._deals.values())
        if not deals:
            return PortfolioSummary(
                property_count=0,
                total_purchase_price=0.0,
                total_equity=0.0,
                total_debt=0.0,
                total_noi=0.0,
                weighted_avg_cap_rate=0.0,
                weighted_avg_dscr=0.0,
                portfolio_debt_yield=0.0,
                portfolio_ltv=0.0,
            )

        total_basis = sum(d.purchase_price for d in deals)
        total_equity = sum(d.equity_amount for d in deals)
        total_debt = sum(d.loan_amount for d in deals)
        total_noi = sum(d.in_place_noi for d in deals)

        if total_basis > 0:
            weighted_cap_rate = sum(d.cap_rate * (d.purchase_price / total_basis) for d in deals)
            portfolio_ltv = total_debt / total_basis
        else:
            weighted_cap_rate = 0.0
            portfolio_ltv = 0.0

        if total_debt > 0:
            weighted_dscr = sum(d.dscr * (d.loan_amount / total_debt) for d in deals)
            portfolio_debt_yield = total_noi / total_debt
        else:
            weighted_dscr = 0.0
            portfolio_debt_yield = 0.0

        return PortfolioSummary(
            property_count=len(deals),
            total_purchase_price=round(total_basis, 2),
            total_equity=round(total_equity, 2),
            total_debt=round(total_debt, 2),
            total_noi=round(total_noi, 2),
            weighted_avg_cap_rate=round(weighted_cap_rate, 4),
            weighted_avg_dscr=round(weighted_dscr, 3),
            portfolio_debt_yield=round(portfolio_debt_yield, 4),
            portfolio_ltv=round(portfolio_ltv, 4),
        )

    def compute_concentration(self) -> ConcentrationMetrics:
        """Calculate diversification percentages across asset classes, states, and sponsors."""
        deals = list(self._deals.values())
        if not deals:
            return ConcentrationMetrics(
                by_property_type={},
                by_geography={},
                by_sponsor={},
                top_asset_concentration_pct=0.0,
            )

        total_basis = sum(d.purchase_price for d in deals)
        if total_basis == 0:
            return ConcentrationMetrics(
                by_property_type={},
                by_geography={},
                by_sponsor={},
                top_asset_concentration_pct=0.0,
            )

        by_type: Dict[str, float] = {}
        by_geo: Dict[str, float] = {}
        by_sponsor: Dict[str, float] = {}

        for d in deals:
            t_name = d.property_type.value
            by_type[t_name] = by_type.get(t_name, 0.0) + (d.purchase_price / total_basis)

            by_geo[d.state] = by_geo.get(d.state, 0.0) + (d.purchase_price / total_basis)

            by_sponsor[d.sponsor_name] = by_sponsor.get(d.sponsor_name, 0.0) + (
                d.purchase_price / total_basis
            )

        top_asset_pct = max(d.purchase_price / total_basis for d in deals)

        return ConcentrationMetrics(
            by_property_type={k: round(v, 4) for k, v in by_type.items()},
            by_geography={k: round(v, 4) for k, v in by_geo.items()},
            by_sponsor={k: round(v, 4) for k, v in by_sponsor.items()},
            top_asset_concentration_pct=round(top_asset_pct, 4),
        )

    def stress_portfolio(
        self,
        name: str,
        rent_shock_pct: float = -0.05,
        opex_shock_pct: float = 0.05,
        exit_cap_expansion_bps: int = 50,
        min_dscr_hurdle: float = 1.20,
    ) -> PortfolioStressImpact:
        """Simulate macro downturn across all portfolio assets."""
        deals = list(self._deals.values())
        if not deals:
            return PortfolioStressImpact(
                scenario_name=name,
                base_noi=0.0,
                stressed_noi=0.0,
                noi_drop_pct=0.0,
                stressed_dscr=0.0,
                covenant_breaches_count=0,
            )

        base_noi = sum(d.in_place_noi for d in deals)
        stressed_nois: List[float] = []
        breaches = 0

        total_stressed_debt_service = 0.0
        total_stressed_noi = 0.0

        for d in deals:
            # Estimate gross revenue and opex from NOI (assuming standard 40% opex ratio)
            est_rev = d.in_place_noi / 0.60
            est_opex = est_rev * 0.40

            stressed_rev = est_rev * (1.0 + rent_shock_pct)
            stressed_opex = est_opex * (1.0 + opex_shock_pct)
            deal_stressed_noi = max(0.0, stressed_rev - stressed_opex)
            stressed_nois.append(deal_stressed_noi)
            total_stressed_noi += deal_stressed_noi

            # Calculate deal stressed DSCR
            annual_ds = (d.loan_amount * 0.065) if d.loan_amount > 0 else 1.0
            total_stressed_debt_service += annual_ds
            deal_dscr = deal_stressed_noi / annual_ds if annual_ds > 0 else 2.0
            if deal_dscr < min_dscr_hurdle:
                breaches += 1

        noi_drop = (base_noi - total_stressed_noi) / base_noi if base_noi > 0 else 0.0
        overall_stressed_dscr = (
            total_stressed_noi / total_stressed_debt_service
            if total_stressed_debt_service > 0
            else 0.0
        )

        return PortfolioStressImpact(
            scenario_name=name,
            base_noi=round(base_noi, 2),
            stressed_noi=round(total_stressed_noi, 2),
            noi_drop_pct=round(noi_drop, 4),
            stressed_dscr=round(overall_stressed_dscr, 3),
            covenant_breaches_count=breaches,
        )

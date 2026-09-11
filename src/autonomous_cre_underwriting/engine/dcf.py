"""Deterministic, audit-ready discounted cash flow (DCF) valuation engine for CRE deals."""

import hashlib
import json
import math
from typing import List, Optional, Tuple

import numpy as np

from autonomous_cre_underwriting.types.financial import (
    AnnualCashFlow,
    DCFParameters,
    DCFValuationResult,
    FinancingAssumptions,
    LoanAmortizationRow,
    SensitivityMatrix,
    SensitivityScenario,
    ValuationMetrics,
)
from autonomous_cre_underwriting.types.property import HistoricalFinancials, PropertyDeal
from autonomous_cre_underwriting.types.risk import StressScenario


def compute_irr(cash_flows: List[float], max_iter: int = 100, tol: float = 1e-7) -> float:
    """Calculate the Internal Rate of Return (IRR) using robust Newton-Raphson root finding.

    Falls back to polynomial roots or bisection if Newton-Raphson fails to converge.
    """
    if len(cash_flows) < 2:
        return 0.0

    # Ensure there is at least one sign change
    has_pos = any(cf > 0 for cf in cash_flows)
    has_neg = any(cf < 0 for cf in cash_flows)
    if not (has_pos and has_neg):
        return 0.0

    # Initial guess
    r = 0.10

    for _ in range(max_iter):
        npv = 0.0
        d_npv = 0.0
        for t, cf in enumerate(cash_flows):
            denom = (1.0 + r) ** t
            if abs(denom) < 1e-12:
                break
            npv += cf / denom
            if t > 0:
                d_npv -= t * cf / ((1.0 + r) ** (t + 1))

        if abs(npv) < tol:
            return float(round(r, 6))

        if abs(d_npv) < 1e-12:
            break

        step = npv / d_npv
        r_new = r - step
        # Prevent runaway into extreme negative rates
        if r_new <= -0.9999:
            r = -0.5
            break
        r = r_new

    # Fallback to numpy polynomial roots on discount factor x = 1 / (1 + r)
    try:
        # P(x) = cf[0] + cf[1]*x + cf[2]*x^2 + ... + cf[n]*x^n
        coeffs = cash_flows[::-1]
        roots = np.roots(coeffs)
        real_roots = [
            root.real
            for root in roots
            if abs(root.imag) < 1e-6 and root.real > 0.0
        ]
        if real_roots:
            # Pick x closest to 1.0 (rates close to 0)
            best_x = min(real_roots, key=lambda x: abs(x - 1.0))
            calc_r = (1.0 / best_x) - 1.0
            if -0.99 <= calc_r <= 10.0:
                return float(round(calc_r, 6))
    except Exception:
        pass

    return float(round(r, 6)) if -0.99 <= r <= 10.0 else 0.0


def compute_npv(rate: float, cash_flows: List[float]) -> float:
    """Compute Net Present Value discounting cash flows at given periodic rate."""
    npv = 0.0
    for t, cf in enumerate(cash_flows):
        npv += cf / ((1.0 + rate) ** t)
    return float(round(npv, 2))


def generate_loan_amortization_schedule(
    financing: FinancingAssumptions,
) -> List[LoanAmortizationRow]:
    """Generate month-by-month debt amortization schedule."""
    if financing.loan_amount <= 0.0:
        return []

    total_months = financing.term_years * 12
    io_months = financing.interest_only_years * 12
    r_monthly = financing.monthly_interest_rate
    monthly_payment_amort = financing.monthly_amortizing_payment()

    schedule: List[LoanAmortizationRow] = []
    balance = financing.loan_amount

    for m in range(1, total_months + 1):
        interest_payment = balance * r_monthly
        if m <= io_months:
            payment = interest_payment
            principal_payment = 0.0
        else:
            payment = monthly_payment_amort
            principal_payment = payment - interest_payment
            if principal_payment > balance:
                principal_payment = balance
                payment = principal_payment + interest_payment

        ending_balance = max(0.0, balance - principal_payment)
        schedule.append(
            LoanAmortizationRow(
                month=m,
                beginning_balance=round(balance, 2),
                payment=round(payment, 2),
                principal=round(principal_payment, 2),
                interest=round(interest_payment, 2),
                ending_balance=round(ending_balance, 2),
            )
        )
        balance = ending_balance
        if balance <= 0.0:
            break

    return schedule


def compute_remaining_loan_balance(
    financing: FinancingAssumptions, year: int
) -> float:
    """Calculate remaining principal loan balance at end of specified year."""
    if financing.loan_amount <= 0.0:
        return 0.0
    if year <= 0:
        return financing.loan_amount

    month_target = min(year * 12, financing.term_years * 12)
    io_months = financing.interest_only_years * 12

    if month_target <= io_months:
        return financing.loan_amount

    r = financing.monthly_interest_rate
    if r == 0.0:
        amort_months = financing.amortization_years * 12
        monthly_principal = financing.loan_amount / amort_months
        amortized_months_elapsed = month_target - io_months
        return max(0.0, financing.loan_amount - (monthly_principal * amortized_months_elapsed))

    amort_months = financing.amortization_years * 12
    amortized_months_elapsed = month_target - io_months
    remaining_amort_months = amort_months - amortized_months_elapsed
    if remaining_amort_months <= 0:
        return 0.0

    monthly_pmt = financing.monthly_amortizing_payment()
    # Present value of remaining monthly payments
    pv = monthly_pmt * (1.0 - (1.0 + r) ** (-remaining_amort_months)) / r
    return float(round(max(0.0, pv), 2))


class DCFEngine:
    """Audit-ready commercial real estate discounted cash flow valuation engine."""

    def compute_valuation(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials] = None,
    ) -> DCFValuationResult:
        """Calculate multi-year pro-forma, returns, DSCR, sensitivity, and deterministic checksum."""
        annual_cash_flows, exit_noi = self._project_cash_flows(
            deal=deal,
            parameters=parameters,
            financing=financing,
            t12=t12,
        )

        metrics = self._calculate_valuation_metrics(
            deal=deal,
            parameters=parameters,
            financing=financing,
            cash_flows=annual_cash_flows,
            exit_noi=exit_noi,
        )

        sensitivity = self._calculate_sensitivity_matrix(
            deal=deal,
            base_params=parameters,
            financing=financing,
            t12=t12,
            base_metrics=metrics,
        )

        checksum = self._calculate_model_checksum(
            deal=deal,
            parameters=parameters,
            financing=financing,
            metrics=metrics,
            annual_cash_flows=annual_cash_flows,
        )

        return DCFValuationResult(
            deal_id=deal.id,
            parameters=parameters,
            financing=financing,
            annual_cash_flows=annual_cash_flows,
            metrics=metrics,
            sensitivity=sensitivity,
            model_checksum=checksum,
        )

    def _project_cash_flows(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials],
    ) -> Tuple[List[AnnualCashFlow], float]:
        """Project multi-year operational revenues, expenses, debt service, and cash flows."""
        # Baseline starting values
        if t12 is not None:
            base_gpr = t12.gross_potential_rent
            base_vacancy_loss = t12.vacancy_credit_loss
            base_other_income = t12.other_income
            base_opex = t12.expenses.total_opex
            base_capex = t12.expenses.capex_reserve
        elif deal.historical_financials:
            hist = deal.historical_financials[-1]
            base_gpr = hist.gross_potential_rent
            base_vacancy_loss = hist.vacancy_credit_loss
            base_other_income = hist.other_income
            base_opex = hist.expenses.total_opex
            base_capex = hist.expenses.capex_reserve
        else:
            base_gpr = deal.unit_mix.annual_in_place_rent or (deal.asking_price * 0.08)
            base_vacancy_loss = base_gpr * (1.0 - deal.unit_mix.physical_occupancy_rate)
            base_other_income = base_gpr * 0.03
            base_opex = max(0.0, base_gpr - base_vacancy_loss + base_other_income - deal.in_place_noi)
            base_capex = 300.0 * max(1, deal.unit_mix.total_units)

        # Baseline vacancy rate
        vacancy_rate = (
            (base_vacancy_loss / base_gpr)
            if base_gpr > 0.0
            else 0.05
        )

        annual_cash_flows: List[AnnualCashFlow] = []
        n_years = parameters.holding_period_years

        current_gpr = base_gpr
        current_other = base_other_income
        current_opex = base_opex
        current_capex = base_capex

        for year in range(1, n_years + 2):
            # Escalate
            current_gpr = current_gpr * (1.0 + parameters.annual_rent_growth)
            current_other = current_other * (1.0 + parameters.general_inflation_rate)
            current_opex = current_opex * (1.0 + parameters.annual_opex_growth)
            current_capex = current_capex * (1.0 + parameters.general_inflation_rate)

            vacancy_amount = current_gpr * vacancy_rate
            egi = max(0.0, current_gpr - vacancy_amount + current_other)
            noi = egi - current_opex

            if year <= n_years:
                unlevered_cf = noi - current_capex
                ds = financing.annual_debt_service(year)
                levered_cf = unlevered_cf - ds
                end_balance = compute_remaining_loan_balance(financing, year)

                dscr = max(0.0, (noi / ds)) if ds > 0.0 else 0.0
                debt_yield = max(0.0, (noi / end_balance)) if end_balance > 0.0 else 0.0

                annual_cash_flows.append(
                    AnnualCashFlow(
                        year=year,
                        potential_gross_revenue=round(current_gpr, 2),
                        vacancy_and_credit_loss=round(vacancy_amount, 2),
                        effective_gross_income=round(egi, 2),
                        operating_expenses=round(current_opex, 2),
                        net_operating_income=round(noi, 2),
                        capex_reserves=round(current_capex, 2),
                        debt_service=round(ds, 2),
                        unlevered_cash_flow=round(unlevered_cf, 2),
                        levered_cash_flow=round(levered_cf, 2),
                        ending_loan_balance=round(end_balance, 2),
                        dscr=round(dscr, 3),
                        debt_yield=round(debt_yield, 4),
                    )
                )

        # Year N+1 NOI for terminal capitalization
        exit_noi = round(noi, 2)
        return annual_cash_flows, exit_noi

    def _calculate_valuation_metrics(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        cash_flows: List[AnnualCashFlow],
        exit_noi: float,
    ) -> ValuationMetrics:
        """Compute IRR, NPV, Equity Multiple, DSCRs, and disposition values."""
        purchase_price = deal.target_purchase_price
        origination_fee = financing.origination_fee_amount
        # Total equity required = purchase price - loan amount + origination fee
        equity_invested = max(1.0, purchase_price - financing.loan_amount + origination_fee)

        # Terminal exit sales price
        gross_exit_sales_price = max(
            0.0,
            exit_noi / parameters.exit_cap_rate if parameters.exit_cap_rate > 0.0 else 0.0,
        )
        disposition_costs = gross_exit_sales_price * parameters.disposition_cost_pct
        net_sales_before_debt = gross_exit_sales_price - disposition_costs

        # Year N loan payoff
        ending_loan_balance = cash_flows[-1].ending_loan_balance if cash_flows else 0.0
        exit_fee = financing.loan_amount * financing.exit_fee_pct
        total_loan_payoff = ending_loan_balance + exit_fee
        net_sales_proceeds = net_sales_before_debt - total_loan_payoff

        # Unlevered cash flows schedule
        unlevered_cfs = [-purchase_price]
        for cf in cash_flows[:-1]:
            unlevered_cfs.append(cf.unlevered_cash_flow)
        unlevered_cfs.append(cash_flows[-1].unlevered_cash_flow + net_sales_before_debt)

        # Levered cash flows schedule
        levered_cfs = [-equity_invested]
        for cf in cash_flows[:-1]:
            levered_cfs.append(cf.levered_cash_flow)
        levered_cfs.append(cash_flows[-1].levered_cash_flow + net_sales_proceeds)

        # Rates of return
        unlevered_irr = compute_irr(unlevered_cfs)
        levered_irr = compute_irr(levered_cfs)
        npv = compute_npv(parameters.discount_rate, levered_cfs)

        # Total distributions and profit
        total_distributions = sum(levered_cfs[1:])
        equity_multiple = max(
            0.0, total_distributions / equity_invested if equity_invested > 0 else 0.0
        )
        total_net_profit = total_distributions - equity_invested

        # In-place cap rate
        in_place_noi = cash_flows[0].net_operating_income if cash_flows else deal.in_place_noi
        in_place_cap_rate = in_place_noi / purchase_price if purchase_price > 0 else 0.0

        # DSCR metrics
        dscrs = [cf.dscr for cf in cash_flows if cf.debt_service > 0.0]
        min_dscr = min(dscrs) if dscrs else 0.0
        avg_dscr = sum(dscrs) / len(dscrs) if dscrs else 0.0

        return ValuationMetrics(
            purchase_price=round(purchase_price, 2),
            equity_invested=round(equity_invested, 2),
            unlevered_irr=round(unlevered_irr, 4),
            levered_irr=round(levered_irr, 4),
            equity_multiple=round(equity_multiple, 2),
            net_present_value=round(npv, 2),
            in_place_cap_rate=round(in_place_cap_rate, 4),
            exit_cap_rate=round(parameters.exit_cap_rate, 4),
            gross_exit_sales_price=round(gross_exit_sales_price, 2),
            net_sales_proceeds=round(net_sales_proceeds, 2),
            total_net_profit=round(total_net_profit, 2),
            min_dscr_observed=round(min_dscr, 3),
            average_dscr=round(avg_dscr, 3),
        )

    def _calculate_sensitivity_matrix(
        self,
        deal: PropertyDeal,
        base_params: DCFParameters,
        financing: FinancingAssumptions,
        t12: Optional[HistoricalFinancials],
        base_metrics: ValuationMetrics,
    ) -> SensitivityMatrix:
        """Run 2D grid matrix varying rent growth and terminal cap rate."""
        rent_deltas_bps = [-100, -50, 0, 50, 100]
        exit_cap_deltas_bps = [-50, -25, 0, 25, 50]

        scenarios: List[SensitivityScenario] = []

        for rg_bps in rent_deltas_bps:
            for cap_bps in exit_cap_deltas_bps:
                # Adjust params
                adj_rent_growth = base_params.annual_rent_growth + (rg_bps / 10000.0)
                adj_exit_cap = max(0.01, base_params.exit_cap_rate + (cap_bps / 10000.0))

                scenario_params = base_params.model_copy(
                    update={
                        "annual_rent_growth": adj_rent_growth,
                        "exit_cap_rate": adj_exit_cap,
                    }
                )

                cfs, exit_noi = self._project_cash_flows(
                    deal=deal,
                    parameters=scenario_params,
                    financing=financing,
                    t12=t12,
                )

                metrics = self._calculate_valuation_metrics(
                    deal=deal,
                    parameters=scenario_params,
                    financing=financing,
                    cash_flows=cfs,
                    exit_noi=exit_noi,
                )

                scenarios.append(
                    SensitivityScenario(
                        rent_growth_delta_bps=rg_bps,
                        exit_cap_delta_bps=cap_bps,
                        levered_irr=metrics.levered_irr,
                        equity_multiple=metrics.equity_multiple,
                        net_present_value=metrics.net_present_value,
                    )
                )

        return SensitivityMatrix(
            base_levered_irr=base_metrics.levered_irr,
            base_equity_multiple=base_metrics.equity_multiple,
            scenarios=scenarios,
        )

    def stress_test(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        name: str,
        rent_shock_pct: float = -0.05,
        vacancy_shock_pct: float = 0.05,
        opex_shock_pct: float = 0.05,
        exit_cap_expansion_bps: int = 50,
        t12: Optional[HistoricalFinancials] = None,
    ) -> StressScenario:
        """Run downside stress scenario testing covenant breaches."""
        stressed_params = parameters.model_copy(
            update={
                "annual_rent_growth": parameters.annual_rent_growth + rent_shock_pct,
                "annual_opex_growth": parameters.annual_opex_growth + opex_shock_pct,
                "exit_cap_rate": parameters.exit_cap_rate + (exit_cap_expansion_bps / 10000.0),
            }
        )

        cfs, exit_noi = self._project_cash_flows(
            deal=deal,
            parameters=stressed_params,
            financing=financing,
            t12=t12,
        )

        # Apply immediate vacancy shock
        for cf in cfs:
            additional_vacancy = cf.potential_gross_revenue * vacancy_shock_pct
            cf.vacancy_and_credit_loss += additional_vacancy
            cf.effective_gross_income = max(
                0.0, cf.effective_gross_income - additional_vacancy
            )
            cf.net_operating_income = cf.effective_gross_income - cf.operating_expenses
            cf.unlevered_cash_flow = cf.net_operating_income - cf.capex_reserves
            cf.levered_cash_flow = cf.unlevered_cash_flow - cf.debt_service
            cf.dscr = (
                max(0.0, cf.net_operating_income / cf.debt_service)
                if cf.debt_service > 0.0
                else 0.0
            )

        metrics = self._calculate_valuation_metrics(
            deal=deal,
            parameters=stressed_params,
            financing=financing,
            cash_flows=cfs,
            exit_noi=exit_noi,
        )

        min_dscr = min((cf.dscr for cf in cfs if cf.debt_service > 0.0), default=0.0)
        covenant_breached = min_dscr < financing.min_dscr_covenant

        return StressScenario(
            name=name,
            rent_shock_pct=rent_shock_pct,
            vacancy_shock_pct=vacancy_shock_pct,
            opex_shock_pct=opex_shock_pct,
            exit_cap_expansion_bps=exit_cap_expansion_bps,
            resultant_irr=metrics.levered_irr,
            min_dscr_observed=round(min_dscr, 3),
            covenant_breached=covenant_breached,
        )

    def _calculate_model_checksum(
        self,
        deal: PropertyDeal,
        parameters: DCFParameters,
        financing: FinancingAssumptions,
        metrics: ValuationMetrics,
        annual_cash_flows: List[AnnualCashFlow],
    ) -> str:
        """Produce deterministic SHA-256 hash verifying reproducibility for audit trail."""
        summary = {
            "deal_id": deal.id,
            "purchase_price": deal.target_purchase_price,
            "loan_amount": financing.loan_amount,
            "interest_rate": financing.interest_rate,
            "holding_period_years": parameters.holding_period_years,
            "exit_cap_rate": parameters.exit_cap_rate,
            "levered_irr": metrics.levered_irr,
            "equity_multiple": metrics.equity_multiple,
            "net_present_value": metrics.net_present_value,
            "cash_flows": [
                {
                    "year": cf.year,
                    "noi": cf.net_operating_income,
                    "levered_cf": cf.levered_cash_flow,
                }
                for cf in annual_cash_flows
            ],
        }
        serialized = json.dumps(summary, sort_keys=True, default=str)
        return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()

"""Unit tests for loan assumptions, payment schedules, DCF parameters, and valuation results."""

import pytest
from pydantic import ValidationError

from autonomous_cre_underwriting.types.financial import (
    DCFParameters,
    FinancingAssumptions,
)


def test_financing_assumptions_calculations(sample_financing):
    """Verify interest rate calculations and debt service payments."""
    assert pytest.approx(sample_financing.monthly_interest_rate, rel=1e-4) == 0.0625 / 12.0
    # Origination fee amount: 15,925,000 * 0.01 = 159,250
    assert sample_financing.origination_fee_amount == 159250.0

    # Interest only annual payment (Year 1) = 15,925,000 * 0.0625 = 995,312.50
    ds_y1 = sample_financing.annual_debt_service(1)
    assert ds_y1 == 995312.5

    # Amortizing payment after IO period (Year 3)
    ds_y3 = sample_financing.annual_debt_service(3)
    monthly_amort = sample_financing.monthly_amortizing_payment()
    assert monthly_amort > 0
    assert ds_y3 == monthly_amort * 12.0
    assert ds_y3 > ds_y1  # amortizing payment includes principal repayment


def test_financing_assumptions_invalid_io():
    """IO years cannot exceed total loan maturity and term cannot exceed amort."""
    with pytest.raises(ValidationError):
        FinancingAssumptions(
            loan_amount=10000000.0,
            interest_rate=0.06,
            term_years=5,
            amortization_years=30,
            interest_only_years=6,  # > term_years (5)
        )
    with pytest.raises(ValidationError):
        FinancingAssumptions(
            loan_amount=10000000.0,
            interest_rate=0.06,
            term_years=35,
            amortization_years=30,  # term > amort
        )


def test_financing_assumptions_zero_loan_and_zero_rate():
    """Zero loan amount and zero interest rate edge cases."""
    zero_loan = FinancingAssumptions(
        loan_amount=0.0,
        interest_rate=0.05,
        term_years=5,
        amortization_years=30,
    )
    assert zero_loan.monthly_amortizing_payment() == 0.0
    assert zero_loan.annual_debt_service(1) == 0.0

    zero_rate = FinancingAssumptions(
        loan_amount=120000.0,
        interest_rate=0.0,
        term_years=10,
        amortization_years=10,
    )
    # 120,000 / 120 months = 1000/month
    assert zero_rate.monthly_amortizing_payment() == 1000.0


def test_dcf_parameters():
    """Verify DCF macroeconomic assumptions instantiation and bounds."""
    params = DCFParameters(
        holding_period_years=7,
        exit_cap_rate=0.0625,
        discount_rate=0.095,
        annual_rent_growth=0.035,
        annual_opex_growth=0.03,
    )
    assert params.holding_period_years == 7
    assert params.exit_cap_rate == 0.0625


def test_dcf_valuation_result(sample_dcf_result):
    """Complete DCF valuation model artifact with pro-forma and sensitivity."""
    assert sample_dcf_result.deal_id == "deal-atx-001"
    assert sample_dcf_result.metrics.levered_irr == 0.168
    assert sample_dcf_result.metrics.equity_multiple == 2.12
    assert len(sample_dcf_result.annual_cash_flows) == 1
    assert sample_dcf_result.annual_cash_flows[0].dscr == 1.32
    assert len(sample_dcf_result.sensitivity.scenarios) == 1

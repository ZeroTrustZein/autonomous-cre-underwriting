"""Unit tests for CRE property domain models, calculations, and constraints."""

import pytest
from pydantic import ValidationError

from autonomous_cre_underwriting.types.property import (
    DealStatus,
    PropertyAddress,
    PropertyPhysical,
    PropertyType,
    UnitSpec,
)


def test_property_address_normalization():
    """State abbreviation must be uppercase and full address should format correctly."""
    addr = PropertyAddress(
        street="100 Main St",
        unit_or_suite="Apt 4B",
        city="Dallas",
        state="tx",
        postal_code="75201",
        county="Dallas",
        apn="12345678",
        latitude=32.7767,
        longitude=-96.7970,
    )
    assert addr.state == "TX"
    assert addr.full_address == "100 Main St Apt 4B, Dallas, TX 75201"


def test_property_address_invalid_state():
    """State must be exactly 2 letters."""
    with pytest.raises(ValidationError):
        PropertyAddress(
            street="100 Main St",
            city="Dallas",
            state="TEXAS",
            postal_code="75201",
            county="Dallas",
            apn="12345678",
        )


def test_unit_spec_calculations():
    """Test occupancy, rents per sqft, and loss to lease calculations."""
    spec = UnitSpec(
        unit_type="1B/1B",
        count=50,
        square_feet=700.0,
        in_place_rent=1400.0,
        market_rent=1600.0,
        vacant_units=5,
    )
    assert spec.occupied_units == 45
    assert pytest.approx(spec.in_place_rent_psf, rel=1e-3) == 2.0
    assert pytest.approx(spec.market_rent_psf, rel=1e-3) == 1600.0 / 700.0
    # Monthly loss to lease = (1600 - 1400) * 45 = 9000
    assert spec.monthly_loss_to_lease == 9000.0


def test_unit_spec_vacancy_exceeds_count():
    """Vacant units cannot exceed total count."""
    with pytest.raises(ValidationError):
        UnitSpec(
            unit_type="Studio",
            count=10,
            square_feet=500.0,
            in_place_rent=1200.0,
            market_rent=1300.0,
            vacant_units=12,
        )


def test_unit_mix_aggregations(sample_unit_mix):
    """Aggregate metrics across mix must match sums."""
    assert sample_unit_mix.total_units == 100
    assert sample_unit_mix.total_vacant_units == 5
    assert pytest.approx(sample_unit_mix.physical_occupancy_rate, rel=1e-3) == 0.95
    # Total sqft = 60*750 + 40*1100 = 45000 + 44000 = 89000
    assert sample_unit_mix.total_rentable_sqft == 89000.0
    # In-place monthly: 57*1600 + 38*2200 = 91200 + 83600 = 174800
    assert sample_unit_mix.total_in_place_monthly_rent == 174800.0
    # Market monthly: 60*1800 + 40*2450 = 108000 + 98000 = 206000
    assert sample_unit_mix.total_market_monthly_rent == 206000.0
    assert sample_unit_mix.annual_in_place_rent == 174800.0 * 12
    assert sample_unit_mix.annual_market_rent == 206000.0 * 12
    assert sample_unit_mix.weighted_average_rent_psf > 0.0


def test_property_physical_validation():
    """Rentable square feet cannot exceed gross building area."""
    with pytest.raises(ValidationError):
        PropertyPhysical(
            gross_square_feet=50000.0,
            rentable_square_feet=60000.0,
            year_built=2020,
            site_area_acres=1.0,
        )


def test_property_physical_renovation_precedes_built():
    """Year renovated cannot precede year built."""
    with pytest.raises(ValidationError):
        PropertyPhysical(
            gross_square_feet=50000.0,
            rentable_square_feet=45000.0,
            year_built=2020,
            year_renovated=2010,
            site_area_acres=1.0,
        )


def test_operating_expenses_calculation(sample_operating_expenses):
    """Total opex and expense ratio should compute accurately."""
    total = sample_operating_expenses.total_opex
    assert total == (280000 + 95000 + 110000 + 85000 + 75000 + 130000 + 25000 + 35000 + 35000)
    assert total == 870000.0
    assert pytest.approx(sample_operating_expenses.opex_ratio(2000000.0), rel=1e-3) == 0.435


def test_historical_financials_noi(sample_historical_financials):
    """EGI and NOI calculations should reflect standard accounting math."""
    # gross potential 2,200,000 - vacancy 110,000 - concessions 25,000 + other 85,000 = 2,150,000
    assert sample_historical_financials.effective_gross_income == 2150000.0
    # NOI = 2,150,000 - 870,000 = 1,280,000
    assert sample_historical_financials.net_operating_income == 1280000.0


def test_property_deal_metrics(sample_deal):
    """Cap rate and unit basis calculations on Deal object."""
    # Target cap rate = 1,280,000 / 24,500,000 ~= 0.05224
    assert pytest.approx(sample_deal.target_cap_rate, rel=1e-3) == 0.05224
    # Asking cap rate = 1,280,000 / 26,000,000 ~= 0.04923
    assert pytest.approx(sample_deal.asking_cap_rate, rel=1e-3) == 0.04923
    # Price per unit = 24,500,000 / 100 = 245,000
    assert sample_deal.price_per_unit == 245000.0
    # Price per sqft = 24,500,000 / 89,000 ~= 275.28
    assert pytest.approx(sample_deal.price_per_sqft, rel=1e-2) == 275.28
    assert sample_deal.status == DealStatus.UNDERWRITING
    assert sample_deal.property_type == PropertyType.MULTIFAMILY


def test_property_edge_cases_zero_divisions(sample_operating_expenses):
    """Division by zero safeguards across property models."""
    assert sample_operating_expenses.opex_ratio(0.0) == 0.0
    assert sample_operating_expenses.opex_ratio(-100.0) == 0.0

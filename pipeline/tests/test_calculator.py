"""Calculadora: casos feitos à mão e propriedades (SPEC §6.4, testes obrigatórios)."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipeline.transform.calculator import Baseline, Params, calculate, present_value, sensitivity

B = Baseline(hospital_cost=100_000.0, hospital_days=1_000.0, school_days=200.0, daily_income=50.0)


def test_hand_calculated_basic():
    # B = 100.000 (hospital) + 1.000 dias × R$ 50 = 150.000; r = 50% → 75.000/ano
    # VP (3 anos, 10%) = 75.000 × (1/1,1 + 1/1,21 + 1/1,331) = 186.513,90
    r = calculate(B, Params(reduction_pct=50, horizon_years=3, discount_rate=0.10))
    assert r.components == {"hospital": 100_000.0, "productivity": 50_000.0}
    assert r.annual_base == 150_000.0
    assert r.annual_saving == 75_000.0
    assert r.pv_saving == pytest.approx(186_513.899, abs=0.01)
    assert r.school_days_avoided == 100.0


def test_hand_calculated_sroi():
    # ajuste = (1 − 0,10) × 0,80 = 0,72 → 54.000 no ano 1, com drop-off de 5%:
    # 54.000 × (1/1,1 + 0,95/1,21 + 0,9025/1,331) = 128.102,93; SROI = 1,281
    p = Params(
        reduction_pct=50,
        horizon_years=3,
        discount_rate=0.10,
        investment=100_000,
        deadweight=0.10,
        attribution=0.80,
        drop_off=0.05,
    )
    r = calculate(B, p)
    assert r.sroi_pv == pytest.approx(128_102.93, abs=0.01)
    assert r.sroi_ratio == pytest.approx(1.2810293, abs=1e-6)


def test_missing_components_are_reported_not_zeroed():
    b = Baseline(hospital_cost=None, hospital_days=10.0, school_days=None, daily_income=None)
    r = calculate(b, Params())
    assert r.missing == ["hospital", "productivity"]
    assert r.components == {}
    assert r.school_days_avoided is None


def test_outpatient_requires_multiplier():
    r = calculate(B, Params(use_outpatient=True, outpatient_multiplier=0.0))
    assert "outpatient" in r.missing


def test_invalid_params():
    with pytest.raises(ValueError):
        calculate(B, Params(reduction_pct=120))
    with pytest.raises(ValueError):
        calculate(B, Params(horizon_years=0))


money = st.floats(min_value=0, max_value=1e9, allow_nan=False)
pct = st.floats(min_value=0, max_value=100, allow_nan=False)


@given(money, st.floats(min_value=0, max_value=1e6), pct, pct, st.integers(1, 30))
def test_monotonic_in_reduction(cost, days, r1, r2, h):
    b = Baseline(cost, days, None, 40.0)
    lo, hi = sorted((r1, r2))
    assert (
        calculate(b, Params(reduction_pct=lo, horizon_years=h)).pv_saving
        <= calculate(b, Params(reduction_pct=hi, horizon_years=h)).pv_saving
    )


@given(money, st.integers(1, 30), st.floats(0, 0.5))
def test_zero_reduction_gives_zero(cost, h, rate):
    r = calculate(Baseline(cost, 10.0, 5.0, 40.0), Params(reduction_pct=0, horizon_years=h, discount_rate=rate))
    assert r.pv_saving == 0.0 and r.annual_saving == 0.0


@given(st.floats(1, 1e8), st.integers(1, 30))
def test_converges_to_sum_when_rate_goes_to_zero(annual, h):
    assert present_value(annual, h, 0.0) == pytest.approx(annual * h, rel=1e-12)
    assert present_value(annual, h, 1e-9) == pytest.approx(annual * h, rel=1e-6)


@given(st.floats(1, 1e8), st.integers(1, 30), st.floats(0, 0.3), st.floats(0, 0.3))
def test_pv_decreases_with_rate(annual, h, a, b):
    lo, hi = sorted((a, b))
    assert present_value(annual, h, hi) <= present_value(annual, h, lo) * (1 + 1e-12)


def test_sensitivity_brackets_central_value():
    p = Params(reduction_pct=50, horizon_years=10, discount_rate=0.085)
    lo, hi = sensitivity(B, p, {"discount_rate": (0.04, 0.12)})
    central = calculate(B, p).pv_saving
    assert lo <= central <= hi
    p2 = Params(investment=1e6, deadweight=0.1, attribution=0.8, drop_off=0.05)
    lo2, hi2 = sensitivity(
        B,
        p2,
        {
            "discount_rate": (0.04, 0.12),
            "deadweight": (0, 0.3),
            "attribution": (0.5, 1.0),
            "drop_off": (0, 0.15),
        },
    )
    c2 = calculate(B, p2).sroi_pv
    assert lo2 <= c2 <= hi2 and not math.isclose(lo2, hi2)

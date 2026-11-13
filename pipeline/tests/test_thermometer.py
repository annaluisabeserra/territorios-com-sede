from pipeline.transform.thermometer import compute


def test_reached_and_flag_when_single_year():
    t = compute("agua", {2021: 99.2, 2022: 99.5})
    assert t.status == "atingida" and not t.uncertain
    t = compute("agua", {2022: 99.85})  # caso Abaíra: um só ano, já na meta
    assert t.status == "atingida" and t.uncertain and "confirmar" in t.reason


def test_not_enough_points():
    t = compute("esgoto", {2021: 40.0, 2022: 45.0})
    assert t.status == "sem_dados" and t.current == 45.0


def test_no_data():
    assert compute("agua", {2022: None}).status == "sem_dados"


def test_on_track_linear():
    t = compute("esgoto", {2018: 40.0, 2019: 45.0, 2020: 50.0, 2021: 55.0, 2022: 60.0})
    assert t.status == "no_ritmo"
    assert abs(t.slope - 5.0) < 1e-9
    assert t.projected_year == 2028
    assert not t.uncertain


def test_late_when_flat_or_falling():
    t = compute("agua", {2018: 80.0, 2019: 79.0, 2020: 80.0, 2021: 79.5, 2022: 79.0})
    assert t.status == "atrasado"


def test_stale_series_is_not_projected():
    # último dado de 2010 com referência 2022: sem dados suficientes (revisão M2, caso Tanque Novo)
    t = compute("esgoto", {2008: 98.0, 2009: 99.0, 2010: 99.21}, ref_year=2022)
    assert t.status == "sem_dados" and "2010" in t.reason


def test_projection_never_in_the_past():
    # último dado 2020, referência 2022 (caso Gandu): projeção não pode cair antes de 2023
    t = compute("agua", {2016: 70.0, 2017: 75.0, 2018: 80.0, 2019: 85.0, 2020: 90.0}, ref_year=2022)
    assert t.projected_year is None or t.projected_year >= 2023


def test_only_recent_window_is_used():
    series = {y: 10.0 + y - 2010 for y in range(2005, 2023)}
    t = compute("esgoto", series, ref_year=2022)
    assert t.n_points == 8 and min(t.years) == 2015


def test_uncertain_flag():
    # inclinação positiva, mas muito ruidosa: IC inclui zero
    t = compute("esgoto", {2017: 20.0, 2018: 55.0, 2019: 15.0, 2020: 60.0, 2021: 25.0, 2022: 62.0})
    assert t.slope > 0 and t.slope_low <= 0 and t.uncertain


def test_projection_starts_at_last_observed_year():
    # série 2014–2020, inclinação 10, último valor 70 em 2020, ref 2022 → 70 + 10×2 = 90 em 2022 → max(2023, 2022) = 2023
    t = compute("esgoto", {2014 + i: 10.0 + 10 * i for i in range(7)}, ref_year=2022)
    assert t.projected_year == 2023


def test_ci_matches_reference_regression():
    # valores de referência calculados com mínimos quadrados e t(3) = 3,182
    t = compute("agua", {2018: 50.0, 2019: 52.0, 2020: 53.0, 2021: 57.0, 2022: 58.0})
    assert abs(t.slope - 2.1) < 1e-9
    se = (sum(r * r for r in [0.2, 0.1, -1.0, 0.9, -0.2]) / 3 / 10) ** 0.5
    assert abs(t.slope_low - (2.1 - 3.182 * se)) < 1e-9

from pipeline.transform.thermometer import compute


def test_reached_needs_two_consecutive_years():
    assert compute("agua", {2021: 99.2, 2022: 99.5}).status == "atingida"
    t = compute("agua", {2018: 95.0, 2019: 96.0, 2020: 97.0, 2021: 98.0, 2022: 99.5})
    assert t.status == "no_ritmo" and t.projected_year == 2023  # só o último ano acima: ainda não "atingida"


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
    t = compute("esgoto", {2018: 20.0, 2019: 50.0, 2020: 10.0, 2021: 60.0, 2022: 30.0})
    assert t.uncertain or t.status == "atrasado"

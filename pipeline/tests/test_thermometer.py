from pipeline.transform.thermometer import compute


def test_reached():
    t = compute("agua", {2020: 98.0, 2021: 99.5})
    assert t.status == "atingida" and t.gap == 0.0


def test_not_enough_points():
    t = compute("esgoto", {2021: 40.0, 2022: 45.0})
    assert t.status == "sem_dados" and t.current == 45.0


def test_no_data():
    assert compute("agua", {2022: None}).status == "sem_dados"


def test_on_track_linear():
    # +5 p.p./ano a partir de 60% em 2022 → 90% em 2028
    t = compute("esgoto", {2018: 40.0, 2019: 45.0, 2020: 50.0, 2021: 55.0, 2022: 60.0})
    assert t.status == "no_ritmo"
    assert abs(t.slope - 5.0) < 1e-9
    assert t.projected_year == 2028


def test_late_when_flat_or_falling():
    t = compute("agua", {2018: 80.0, 2019: 79.0, 2020: 80.0, 2021: 79.5, 2022: 79.0})
    assert t.status == "atrasado"


def test_uses_at_most_8_points():
    series = {y: 10.0 + y - 2010 for y in range(2010, 2023)}
    assert compute("esgoto", series).n_points == 8

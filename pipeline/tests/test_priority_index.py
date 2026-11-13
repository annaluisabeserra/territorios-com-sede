from pipeline.transform.priority_index import dimension_scores, percentile_ranks, rank, weighted_index


def test_percentiles_ties_and_missing():
    p = percentile_ranks({"a": 1.0, "b": 2.0, "c": 2.0, "d": 3.0, "e": None})
    assert p["a"] == 0.0 and p["d"] == 100.0
    assert p["b"] == p["c"] == 50.0
    assert p["e"] is None


def test_percentile_direction():
    p = percentile_ranks({"a": 1.0, "b": 2.0}, higher_is_worse=False)
    assert p["a"] == 100.0 and p["b"] == 0.0


def test_missing_component_reweights_within_dimension():
    s = dimension_scores({"x": 80.0, "y": None}, {"acesso": ["x", "y"]})
    assert s["acesso"] == 80.0


def test_missing_dimension_reweights_and_never_imputes_zero():
    w = {"a": 0.5, "b": 0.3, "c": 0.2}
    idx, cov = weighted_index({"a": 100.0, "b": None, "c": 50.0}, w, min_dims=2)
    assert idx == (100 * 0.5 + 50 * 0.2) / 0.7
    assert abs(cov - 0.7) < 1e-12
    idx2, _ = weighted_index({"a": 100.0, "b": None, "c": None}, w, min_dims=2)
    assert idx2 is None


def test_rank_competition():
    assert rank({"a": 90.0, "b": 90.0, "c": 10.0, "d": None}) == {"a": 1, "b": 1, "c": 3, "d": None}

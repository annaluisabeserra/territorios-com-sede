from hypothesis import given
from hypothesis import strategies as st

from pipeline.transform.priority_index import dimension_scores, percentile_ranks, rank, weighted_index


def test_percentiles_ties_and_missing():
    p = percentile_ranks({"a": 1.0, "b": 2.0, "c": 2.0, "d": 3.0, "e": None})
    assert p["a"] == 0.0 and p["d"] == 100.0
    assert p["b"] == p["c"] and abs(p["b"] - 100 / 3) < 1e-9  # 1 de 3 outros está estritamente melhor
    assert p["e"] is None


def test_mass_of_zeros_is_best_situation():
    vals = {str(i): 0.0 for i in range(7)} | {"x": 1.0, "y": 2.0, "z": 3.0}
    p = percentile_ranks(vals)
    assert all(p[str(i)] == 0.0 for i in range(7))


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


def test_required_dimensions():
    w = {"acesso": 0.3, "saude": 0.25, "vulnerabilidade": 0.2}
    assert (
        weighted_index({"acesso": 50.0, "saude": None, "vulnerabilidade": 10.0}, w, 2, ("acesso", "saude"))[0] is None
    )


score = st.one_of(st.none(), st.floats(0, 100))


@given(st.dictionaries(st.sampled_from("abcde"), score, min_size=1), st.floats(0.1, 10))
def test_index_invariant_to_weight_scale(ds, k):
    w = {"a": 0.3, "b": 0.25, "c": 0.2, "d": 0.15, "e": 0.1}
    i1, _ = weighted_index(ds, w, 1)
    i2, _ = weighted_index(ds, {d: v * k for d, v in w.items()}, 1)
    assert (i1 is None and i2 is None) or abs(i1 - i2) < 1e-9


@given(st.dictionaries(st.sampled_from("abcde"), st.floats(0, 90), min_size=3), st.sampled_from("abcde"))
def test_worse_component_never_lowers_index(ds, d):
    w = {"a": 0.3, "b": 0.25, "c": 0.2, "d": 0.15, "e": 0.1}
    before, _ = weighted_index(ds, w, 1)
    after, _ = weighted_index({**ds, d: ds.get(d, 0) + 10} if d in ds else ds, w, 1)
    assert after >= before - 1e-9


def test_full_dimensions_equals_weighted_mean():
    w = {"a": 0.5, "b": 0.3, "c": 0.2}
    assert abs(weighted_index({"a": 10.0, "b": 20.0, "c": 30.0}, w, 3)[0] - 17.0) < 1e-12

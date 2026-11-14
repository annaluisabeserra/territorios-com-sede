"""Ranking provisório (ADR-015): só quando uma dimensão obrigatória falta para a UF inteira."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.transform.build import compute_index


def tab(n=30, saude=None, seed=1):
    rng = np.random.default_rng(seed)
    t = pd.DataFrame(
        {
            "censo_sem_agua_rede_pct": rng.uniform(0, 60, n),
            "censo_sem_esgoto_adequado_pct": rng.uniform(0, 90, n),
            "renda_domiciliar_pc": rng.uniform(300, 2000, n),
            "pct_pop_quilombola_indigena": rng.uniform(0, 30, n),
        },
        index=[f"29{i:05d}" for i in range(n)],
    )
    if saude is not None:
        t["drsai_taxa_10mil"] = saude
    return t


def test_missing_health_for_whole_state_gives_labelled_provisional_ranking():
    out, info = compute_index(tab(), set())
    assert info["provisional"] is True
    assert info["provisional_without"] == ["saude"]
    assert info["required_dimensions"] == ["acesso"]
    assert info["ranked"] == 30
    ranks = out["indice_rank"].dropna().astype(int)
    assert len(ranks) == 30 and ranks.min() == 1  # empates recebem a mesma posição


def test_health_present_for_some_keeps_official_rule_and_excludes_missing():
    saude = [np.nan] * 10 + list(np.linspace(1, 50, 20))
    out, info = compute_index(tab(saude=saude), set())
    assert info["provisional"] is False
    assert info["required_dimensions"] == ["acesso", "saude"]
    assert info["ranked"] == 20  # quem não tem saúde fica fora, sem exclusão escondida
    assert out["indice_prioridade"].iloc[:10].isna().all()


def test_without_access_no_municipality_is_ranked():
    t = tab()
    t["censo_sem_agua_rede_pct"] = np.nan
    t["censo_sem_esgoto_adequado_pct"] = np.nan
    _, info = compute_index(t, set())
    assert info["ranked"] == 0


def test_municipality_without_score_never_gets_a_position():
    from pipeline.transform import priority_index as pidx

    r = pidx.rank({"a": 90.0, "b": float("nan"), "c": 80.0, "d": None})
    assert r == {"a": 1, "b": None, "c": 2, "d": None}
    t = tab()
    t.iloc[:3, :2] = np.nan  # três municípios sem acesso (obrigatória)
    out, info = compute_index(t, set())
    assert info["ranked"] == 27
    assert out["indice_rank"].iloc[:3].isna().all()
    assert int(out["indice_rank"].max()) <= 27

"""Conta de impacto (ADR-013): fórmulas, faixas e ausência ≠ zero."""

from __future__ import annotations

import pandas as pd
import pytest

from pipeline import config
from pipeline.transform import impact

CFG = config.load("impacto")


def snis_row(**kw):
    base = {
        "cod_ibge7": "2312403",
        "year": 2022,
        "volume_agua_produzido": 422.69,
        "volume_agua_tratada_importado": 1066.07,
        "volume_agua_tratada_exportado": 0.0,
        "volume_agua_consumido": 777.08,
        "volume_servico_agua": 15.48,
        "volume_agua_faturado": 1184.93,
        "volume_esgoto_faturado": 1427.1,
        "despesa_exploracao": 12088912.34,
        "despesa_energia": 1492416.89,
        "despesa_produto_quimico": 620860.61,
        "snis_perdas_pct": 47.26,
    }
    base.update(kw)
    return base


def test_water_losses_reproduce_in049_and_band():
    w = impact.water_losses(pd.DataFrame([snis_row()]), {2022: 1.0}, 10).loc["2312403"]
    assert w["perda_m3"] == pytest.approx(696_200, rel=1e-6)  # 422,69 + 1.066,07 − 777,08 − 15,48 mil m³
    assert w["custo_m3_baixo"] == pytest.approx((1492416.89 + 620860.61) / 1_488_760, rel=1e-9)
    assert w["custo_m3_alto"] == pytest.approx(12088912.34 / 2_612_030, rel=1e-9)  # IN026
    assert w["valor_baixo"] < w["valor_alto"]


def test_exported_water_is_not_subtracted_twice():
    # AG010 já inclui a água exportada: o índice de perdas de Fortaleza 2022 (36,62%) tem de ser reproduzido
    row = snis_row(
        cod_ibge7="2304400",
        volume_agua_produzido=261483.39,
        volume_agua_tratada_importado=0.0,
        volume_agua_tratada_exportado=55857.49,
        volume_agua_consumido=153541.47,
        volume_servico_agua=19234.91,
        snis_perdas_pct=36.62,
    )
    w = impact.water_losses(pd.DataFrame([row]), {2022: 1.0}, 10)
    assert w.loc["2304400", "perda_m3"] == pytest.approx(88_707_010, rel=1e-6)


def test_volume_inconsistent_with_declared_loss_index_becomes_missing():
    w = impact.water_losses(pd.DataFrame([snis_row(snis_perdas_pct=10.0)]), {2022: 1.0}, 10)
    assert w.empty or pd.isna(w.loc["2312403", "perda_m3"])


def test_deflator_applies_to_money_not_volume():
    a = impact.water_losses(pd.DataFrame([snis_row()]), {2022: 1.0}, 10).loc["2312403"]
    b = impact.water_losses(pd.DataFrame([snis_row()]), {2022: 1.2}, 10).loc["2312403"]
    assert b["perda_m3"] == a["perda_m3"]
    assert b["valor_baixo"] == pytest.approx(a["valor_baixo"] * 1.2)


def test_account_never_turns_missing_into_zero():
    acc = impact.account(None, None, None, None, None, 1000, CFG, None, 2023)
    assert acc["total"]["baixo"] is None
    assert set(acc["total"]["faltando"]) == {"saude_sus", "trabalho", "agua_perdida", "vidas"}
    assert all(c["baixo"] is None for c in acc["camadas"].values())


def test_account_sums_available_layers_and_flags_partial_high():
    water = {"year": 2022, "perda_m3": 1000.0, "valor_baixo": 500.0, "valor_alto": None}
    acc = impact.account(2000.0, 10.0, 3.0, 50.0, water, 100, CFG, "média 2020–2024", 2024)
    c = acc["camadas"]
    assert c["saude_sus"]["baixo"] == 2000.0 and c["trabalho"]["baixo"] == 500.0  # 10 dias × R$ 50
    assert c["escola"]["unidade"] == "dias"  # não monetizado, fora do total
    assert acc["total"]["baixo"] == 3000.0
    assert acc["total"]["alto"] == 3000.0  # alto ausente entra pelo baixo
    assert acc["total"]["alto_parcial"] == ["agua_perdida"]
    assert acc["total"]["por_pessoa_baixo"] == 30.0

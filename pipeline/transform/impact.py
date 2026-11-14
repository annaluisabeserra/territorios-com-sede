"""Conta de impacto potencial por município (inspirada na metodologia True Value; ADR-013).

Mostra, em camadas separadas, quanto a falta de saneamento custa por ano. Cada camada traz valor ou faixa
(baixo–alto), ano/período, fonte e premissa. Camada sem dado fica `None` e entra em `faltando`, nunca como zero.
"""

from __future__ import annotations

import math

import pandas as pd

from pipeline.transform.calculator import Baseline, Params, components

VOL = {
    "produzido": "volume_agua_produzido",
    "importado": "volume_agua_tratada_importado",
    "exportado": "volume_agua_tratada_exportado",
    "consumido": "volume_agua_consumido",
    "servico": "volume_servico_agua",
    "fat_agua": "volume_agua_faturado",
    "fat_esgoto": "volume_esgoto_faturado",
}
COST = {"dex": "despesa_exploracao", "energia": "despesa_energia", "quimico": "despesa_produto_quimico"}


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def water_losses(snis: pd.DataFrame, deflator: dict[int, float], outlier_mult: float) -> pd.DataFrame:
    """Por município: m³ perdidos/ano e custo baixo/alto em R$ do ano-base, no último ano com dado completo.

    Volumes do SNIS estão em 1.000 m³/ano; despesas em R$ nominais do ano de referência.
    """
    need = [*VOL.values(), *COST.values()]
    if snis is None or not set(need[:4]) <= set(snis.columns):
        return pd.DataFrame()
    d = snis.dropna(subset=[VOL["produzido"], VOL["consumido"]]).copy()
    for c in need:
        if c not in d:
            d[c] = float("nan")
    # Fórmula do numerador do IN049: AG006 + AG018 − AG010 − AG024. O AG010 (consumido) já inclui a água
    # tratada exportada, por isso a exportação NÃO é descontada de novo.
    disp = d[VOL["produzido"]] + d[VOL["importado"]].fillna(0) - d[VOL["servico"]].fillna(0)
    lost_k = disp - d[VOL["consumido"]]
    d["perda_m3"] = (lost_k * 1000).where(lost_k >= 0)
    # Checagem: o volume perdido precisa reproduzir o índice de perdas declarado (IN049) com folga de 2 pontos.
    if "snis_perdas_pct" in d:
        share = 100 * lost_k / disp.where(disp > 0)
        bad = d["snis_perdas_pct"].notna() & ((share - d["snis_perdas_pct"]).abs() > 2)
        d.loc[bad, "perda_m3"] = float("nan")
    produced_m3 = (d[VOL["produzido"]] + d[VOL["importado"]].fillna(0)) * 1000
    billed_m3 = (d[VOL["fat_agua"]].fillna(0) + d[VOL["fat_esgoto"]].fillna(0)) * 1000
    d["custo_m3_baixo"] = ((d[COST["energia"]] + d[COST["quimico"]]) / produced_m3).where(produced_m3 > 0)
    d["custo_m3_alto"] = (d[COST["dex"]] / billed_m3).where(billed_m3 > 0)
    for c in ("custo_m3_baixo", "custo_m3_alto"):
        med = d[c][d[c] > 0].median()
        d.loc[(d[c] <= 0) | (d[c] > outlier_mult * med), c] = float("nan")
    d = d.dropna(subset=["perda_m3"]).sort_values("year").groupby("cod_ibge7").tail(1)
    f = d["year"].map(lambda y: deflator.get(int(y)))
    d["valor_baixo"] = d["perda_m3"] * d["custo_m3_baixo"] * f
    d["valor_alto"] = d["perda_m3"] * d["custo_m3_alto"] * f
    # O alto nunca fica abaixo do baixo (custo médio inclui o custo marginal)
    d.loc[d["valor_alto"] < d["valor_baixo"], "valor_alto"] = d["valor_baixo"]
    # Sem custo marginal declarado não há cenário baixo: a camada fica sem dado (o alto sozinho não vira faixa)
    d.loc[d["valor_baixo"].isna(), "valor_alto"] = float("nan")
    return d.set_index("cod_ibge7")[
        ["year", "perda_m3", "custo_m3_baixo", "custo_m3_alto", "valor_baixo", "valor_alto"]
    ]


def account(
    hospital_cost: float | None,
    hospital_days: float | None,
    school_days: float | None,
    daily_income: float | None,
    water: dict | None,
    pop: float | None,
    cfg: dict,
    period: str | None,
    price_base: int | None,
) -> dict:
    cam = cfg["camadas"]
    b = Baseline(_num(hospital_cost), _num(hospital_days), _num(school_days), _num(daily_income))
    comp, _ = components(b, Params(reduction_pct=100, use_hospital=True, use_productivity=True))
    layers: dict[str, dict] = {}

    def layer(key: str, low, high, unit: str, ref: str | None, fonte: str) -> None:
        low, high = _num(low), _num(high)
        layers[key] = {
            "label": cam[key]["label"],
            "pergunta": cam[key]["pergunta"],
            "tipo": cam[key]["tipo"],
            "premissa": (cam[key].get("premissa") or "").strip() or None,
            "baixo": low,
            "alto": high,
            "unidade": unit,
            "referencia": ref,
            "fonte": fonte,
        }

    # Camadas observadas ou com valor único: baixo = alto
    h, pr = comp.get("hospital"), comp.get("productivity")
    layer("saude_sus", h, h, "brl", period, "DATASUS, SIH/SUS")
    layer("trabalho", pr, pr, "brl", period, "DATASUS, SIH/SUS; IBGE, Censo 2022 (renda)")
    layer("escola", b.school_days, b.school_days, "dias", period, "DATASUS, SIH/SUS")
    w = water or {}
    layer(
        "agua_perdida",
        w.get("valor_baixo"),
        w.get("valor_alto"),
        "brl",
        str(int(w["year"])) if w.get("year") is not None and not pd.isna(w.get("year")) else None,
        "SNIS (volumes AG006, AG010, AG018, AG019, AG024; AG011, ES007; despesas FN011, FN013, FN015)",
    )
    if w.get("perda_m3") is not None and not pd.isna(w.get("perda_m3")):
        layers["agua_perdida"]["volume_m3"] = float(w["perda_m3"])
    money = [k for k, v in layers.items() if v["unidade"] == "brl"]
    have = [k for k in money if v_ok(layers[k]["baixo"])]
    total_low = sum(layers[k]["baixo"] for k in have) if have else None
    # Camada sem cenário alto entra no total alto pelo valor baixo (conservador), e isso fica registrado.
    total_high = (
        sum(layers[k]["alto"] if v_ok(layers[k]["alto"]) else layers[k]["baixo"] for k in have) if have else None
    )
    p = _num(pop)
    return {
        "camadas": layers,
        "total": {
            "baixo": total_low,
            "alto": total_high,
            "por_pessoa_baixo": total_low / p if total_low is not None and p else None,
            "por_pessoa_alto": total_high / p if total_high is not None and p else None,
            "inclui": have,
            "faltando": [k for k in money if k not in have],
            "alto_parcial": [k for k in have if not v_ok(layers[k]["alto"]) and layers[k]["tipo"] == "estimado"],
        },
        "price_base": price_base,
    }


def v_ok(v) -> bool:
    return _num(v) is not None and _num(v) >= 0

"""Índice de prioridade territorial (SPEC §6.6).

1. Cada componente vira percentil dentro da UF, orientado para 100 = pior situação.
2. Dimensão = média dos componentes presentes (reponderação dentro da dimensão).
3. Índice = soma ponderada das dimensões presentes, com os pesos renormalizados para somar 1.
4. Nunca imputar zero: componente ausente fica fora; município com menos de `min_dimensions_for_rank`
   dimensões é sinalizado e fica sem posição no ranking.

`weighted_index` é replicado em TypeScript (pesos ajustáveis no navegador).
"""

from __future__ import annotations

import math
from collections.abc import Mapping


def percentile_ranks(values: Mapping[str, float | None], higher_is_worse: bool = True) -> dict[str, float | None]:
    """Percentil (0–100) com empates pela média dos postos. Ausentes continuam ausentes."""
    present = [(k, v) for k, v in values.items() if v is not None and not math.isnan(v)]
    out: dict[str, float | None] = {k: None for k in values}
    n = len(present)
    if n == 0:
        return out
    if n == 1:
        out[present[0][0]] = 50.0
        return out
    ordered = sorted(present, key=lambda kv: kv[1])
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg_rank = (i + j) / 2  # posto de base 0
        pct = avg_rank / (n - 1) * 100
        for k in range(i, j + 1):
            out[ordered[k][0]] = pct if higher_is_worse else 100 - pct
        i = j + 1
    return out


def dimension_scores(
    component_pcts: Mapping[str, Mapping[str, float | None]], dims: Mapping[str, list[str]]
) -> dict[str, float | None]:
    """component_pcts[indicator] = percentil de um município; dims[dim] = lista de indicadores."""
    out: dict[str, float | None] = {}
    for dim, comps in dims.items():
        vals = [component_pcts[c] for c in comps if component_pcts.get(c) is not None]
        out[dim] = sum(vals) / len(vals) if vals else None  # type: ignore[arg-type]
    return out


def weighted_index(
    dim_scores: Mapping[str, float | None], weights: Mapping[str, float], min_dims: int
) -> tuple[float | None, float]:
    """Retorna (índice, cobertura de peso). Índice None se dimensões presentes < min_dims."""
    present = [(d, s) for d, s in dim_scores.items() if s is not None and weights.get(d, 0) > 0]
    total_w = 0.0
    for d, _ in present:
        total_w = total_w + weights[d]
    all_w = 0.0
    for d in dim_scores:
        all_w = all_w + weights.get(d, 0.0)
    coverage = total_w / all_w if all_w > 0 else 0.0
    if len(present) < min_dims or total_w <= 0:
        return None, coverage
    acc = 0.0
    for d, s in present:
        acc = acc + s * weights[d]
    return acc / total_w, coverage


def rank(scores: Mapping[str, float | None]) -> dict[str, int | None]:
    """Posição 1 = maior prioridade. Empates recebem a mesma posição (ranking de competição)."""
    present = sorted(((k, v) for k, v in scores.items() if v is not None), key=lambda kv: -kv[1])
    out: dict[str, int | None] = {k: None for k in scores}
    prev, pos = None, 0
    for i, (k, v) in enumerate(present, start=1):
        if v != prev:
            pos, prev = i, v
        out[k] = pos
    return out

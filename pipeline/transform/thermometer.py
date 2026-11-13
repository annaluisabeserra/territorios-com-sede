"""Termômetro 2033 (SPEC §6.5): distância até as metas do Marco Legal do Saneamento.

Lei 14.026/2020: 99% da população com água potável e 90% com coleta e tratamento de esgoto até 31/12/2033.
Projeção linear (mínimos quadrados) sobre os últimos 5 a 8 anos disponíveis, mínimo de 3 pontos.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

TARGET_YEAR = 2033
TARGETS = {"agua": 99.0, "esgoto": 90.0}
MIN_POINTS = 3
MAX_POINTS = 8
T_CRIT_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447}  # t de Student bicaudal


@dataclass
class Thermometer:
    service: str
    target: float
    status: str  # atingida | no_ritmo | atrasado | sem_dados
    current: float | None
    current_year: int | None
    gap: float | None  # pontos percentuais até a meta (0 se atingida)
    slope: float | None  # pontos percentuais por ano
    slope_low: float | None
    slope_high: float | None
    projected_year: int | None  # ano projetado de atingimento (None = não atinge com a tendência)
    projected_year_low: int | None  # cenário otimista (inclinação no limite superior do IC 95%)
    projected_year_high: int | None  # cenário pessimista (None = não atinge)
    n_points: int
    years: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


def _year_to_reach(current: float, current_year: int, slope: float, target: float) -> int | None:
    if current >= target:
        return current_year
    if slope <= 0:
        return None
    return current_year + math.ceil((target - current) / slope)


def compute(service: str, series: dict[int, float | None]) -> Thermometer:
    target = TARGETS[service]
    pts = sorted((y, v) for y, v in series.items() if v is not None and not math.isnan(v))
    pts = pts[-MAX_POINTS:]
    years = [y for y, _ in pts]
    if not pts:
        return Thermometer(
            service, target, "sem_dados", None, None, None, None, None, None, None, None, None, 0, []
        )
    cur_year, cur = pts[-1]
    cur = min(cur, 100.0)
    gap = max(0.0, target - cur)
    if cur >= target:
        return Thermometer(
            service,
            target,
            "atingida",
            cur,
            cur_year,
            0.0,
            None,
            None,
            None,
            cur_year,
            cur_year,
            cur_year,
            len(pts),
            years,
        )
    if len(pts) < MIN_POINTS:
        return Thermometer(
            service,
            target,
            "sem_dados",
            cur,
            cur_year,
            gap,
            None,
            None,
            None,
            None,
            None,
            None,
            len(pts),
            years,
        )
    n = len(pts)
    mx = sum(y for y, _ in pts) / n
    my = sum(v for _, v in pts) / n
    sxx = sum((y - mx) ** 2 for y, _ in pts)
    sxy = sum((y - mx) * (v - my) for y, v in pts)
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [v - (intercept + slope * y) for y, v in pts]
    dof = n - 2
    if dof > 0:
        se = math.sqrt(sum(r * r for r in resid) / dof / sxx)
        t = T_CRIT_95.get(dof, 1.96)
        lo, hi = slope - t * se, slope + t * se
    else:
        lo = hi = slope
    # A projeção parte do valor ajustado no último ano (menos sensível a um ponto isolado).
    fitted_now = min(100.0, intercept + slope * cur_year)
    proj = _year_to_reach(fitted_now, cur_year, slope, target)
    proj_opt = _year_to_reach(fitted_now, cur_year, hi, target)
    proj_pes = _year_to_reach(fitted_now, cur_year, lo, target)
    status = "no_ritmo" if proj is not None and proj <= TARGET_YEAR else "atrasado"
    return Thermometer(
        service, target, status, cur, cur_year, gap, slope, lo, hi, proj, proj_opt, proj_pes, n, years
    )

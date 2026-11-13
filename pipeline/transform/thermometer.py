"""Termômetro 2033 (SPEC §6.5): distância até as metas do Marco Legal do Saneamento.

Lei 14.026/2020: 99% da população com água potável e 90% com coleta e tratamento de esgoto até 31/12/2033.

Regras (revisão M2):
- só entram pontos de uma janela recente: [ano_ref − 7, ano_ref], onde ano_ref é o último ano do SNIS na UF;
- o último ponto do município precisa ser de ano_ref − 2 ou mais recente; senão, "sem dados suficientes";
- regressão linear (mínimos quadrados) sobre 3 a 8 pontos;
- "meta atingida" exige os dois últimos anos disponíveis (consecutivos) acima da meta;
- a projeção parte do último valor observado, no ano em que foi observado, e nunca cai antes de ano_ref + 1;
  a faixa (otimista/pessimista) é a "faixa da tendência": usa o IC da inclinação, não é um intervalo de previsão;
- se o limite inferior do IC 95% da inclinação for ≤ 0, a projeção é marcada como incerta.
Esgoto usa "coleta com tratamento" (IN056 × IN016 / 100), porque a meta exige as duas coisas.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

TARGET_YEAR = 2033
TARGETS = {"agua": 99.0, "esgoto": 90.0}
MIN_POINTS = 3
WINDOW = 8  # anos na janela (ano_ref − 7 … ano_ref)
MAX_STALENESS = 2
# t de Student bicaudal 95% por graus de liberdade (n − 2). WINDOW = 8 ⇒ no máximo 6; a tabela vai até 10.
T_CRIT_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


@dataclass
class Thermometer:
    service: str
    target: float
    status: str  # atingida | no_ritmo | atrasado | sem_dados
    current: float | None
    current_year: int | None
    gap: float | None
    slope: float | None
    slope_low: float | None
    slope_high: float | None
    projected_year: int | None  # None = não atinge com a tendência
    projected_year_low: int | None  # cenário otimista
    projected_year_high: int | None  # cenário pessimista (None = não atinge)
    n_points: int
    years: list[int]
    uncertain: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _year_to_reach(current: float, cur_year: int, ref_year: int, slope: float, target: float) -> int | None:
    """Ano em que a tendência cruza a meta, a partir do ano do último dado; nunca antes de ref_year + 1."""
    if current >= target:
        return ref_year + 1
    if slope <= 0:
        return None
    return max(ref_year + 1, cur_year + math.ceil((target - current) / slope))


def _empty(service: str, target: float, reason: str, cur=None, cur_year=None, n=0, years=None) -> Thermometer:
    gap = None if cur is None else max(0.0, target - cur)
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
        n,
        years or [],
        False,
        reason,
    )


def compute(service: str, series: dict[int, float | None], ref_year: int | None = None) -> Thermometer:
    target = TARGETS[service]
    pts_all = sorted((int(y), float(v)) for y, v in series.items() if v is not None and not math.isnan(v))
    if not pts_all:
        return _empty(service, target, "sem dado no SNIS")
    ref = ref_year if ref_year is not None else pts_all[-1][0]
    pts = [(y, min(v, 100.0)) for y, v in pts_all if ref - WINDOW + 1 <= y <= ref]
    last_year, last_val = pts_all[-1][0], min(pts_all[-1][1], 100.0)
    if last_year < ref - MAX_STALENESS:
        return _empty(service, target, f"último dado é de {last_year}", last_val, last_year, 0, [])
    years = [y for y, _ in pts]
    cur_year, cur = pts[-1]
    if len(pts) >= 2 and pts[-1][1] >= target and pts[-2][1] >= target and pts[-1][0] - pts[-2][0] == 1:
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
        return _empty(service, target, f"só {len(pts)} ano(s) recentes", cur, cur_year, len(pts), years)
    n = len(pts)
    mx = sum(y for y, _ in pts) / n
    my = sum(v for _, v in pts) / n
    sxx = sum((y - mx) ** 2 for y, _ in pts)
    sxy = sum((y - mx) * (v - my) for y, v in pts)
    slope = sxy / sxx
    intercept = my - slope * mx
    dof = n - 2
    if dof > 0:
        resid = [v - (intercept + slope * y) for y, v in pts]
        se = math.sqrt(sum(r * r for r in resid) / dof / sxx)
        if dof not in T_CRIT_95:
            raise ValueError(f"t crítico não tabelado para {dof} graus de liberdade (aumente T_CRIT_95)")
        t = T_CRIT_95[dof]
        lo, hi = slope - t * se, slope + t * se
    else:
        lo = hi = slope
    proj = _year_to_reach(cur, cur_year, ref, slope, target)
    proj_opt = _year_to_reach(cur, cur_year, ref, hi, target)
    proj_pes = _year_to_reach(cur, cur_year, ref, lo, target)
    status = "no_ritmo" if proj is not None and proj <= TARGET_YEAR else "atrasado"
    uncertain = lo <= 0 < slope
    reason = "tendência incerta: o intervalo de confiança inclui estagnação" if uncertain else ""
    return Thermometer(
        service,
        target,
        status,
        cur,
        cur_year,
        max(0.0, target - cur),
        slope,
        lo,
        hi,
        proj,
        proj_opt,
        proj_pes,
        n,
        years,
        uncertain,
        reason,
    )

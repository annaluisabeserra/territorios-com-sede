"""Calculadora de economia / SROI (SPEC §6.4).

Implementação de referência. A versão TypeScript (`site/src/lib/calculator.ts`) replica exatamente a mesma
sequência de operações em ponto flutuante; a paridade é verificada por casos gerados aqui
(`pipeline/tests/test_calculator_parity.py` grava `site/src/lib/calculator.parity.json`).

Regras para manter a paridade bit a bit:
- nada de `**`/`Math.pow`: fatores de desconto e de drop-off são acumulados por multiplicação iterativa;
- mesma ordem de operações e de somatórios nas duas linguagens;
- nenhum arredondamento interno (arredondar só na exibição).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Baseline:
    """Benefício anual base de um município (valores médios anuais, R$ do ano-base)."""

    hospital_cost: float | None  # valor pago SIH, média anual corrigida
    hospital_days: float | None  # dias de permanência, média anual (todas as idades)
    school_days: float | None  # dias de internação de 6 a 17 anos, média anual
    daily_income: float | None  # renda diária de referência (R$/dia)
    deaths: float | None = None  # óbitos por DRSAI, média anual (SIM)
    productive_years_lost: float | None = None  # anos produtivos perdidos por óbito (média, inteiro ≥ 0)


@dataclass(frozen=True)
class Params:
    reduction_pct: float = 50.0
    horizon_years: int = 10
    discount_rate: float = 0.085
    use_hospital: bool = True
    use_productivity: bool = True
    use_outpatient: bool = False
    outpatient_multiplier: float = 0.0
    use_deaths: bool = False
    # Modo SROI
    investment: float | None = None
    deadweight: float = 0.0
    attribution: float = 1.0
    drop_off: float = 0.0


@dataclass
class Result:
    annual_base: float  # B: benefício anual base (soma dos componentes ligados)
    components: dict[str, float]  # B por componente
    annual_saving: float  # B × r (sem ajustes SROI)
    pv_saving: float  # valor presente no horizonte (sem ajustes SROI)
    school_days_avoided: float | None  # indicador não monetizado
    sroi_pv: float | None = None
    sroi_ratio: float | None = None
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def is_num(v: float | None) -> bool:
    """Mesmo critério do TypeScript: None e NaN contam como ausentes."""
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _validate(p: Params) -> None:
    if not 0 <= p.reduction_pct <= 100:
        raise ValueError("reduction_pct deve estar entre 0 e 100")
    if not isinstance(p.horizon_years, int) or isinstance(p.horizon_years, bool) or not 1 <= p.horizon_years <= 30:
        raise ValueError("horizon_years deve ser inteiro entre 1 e 30")
    if p.outpatient_multiplier < 0:
        raise ValueError("outpatient_multiplier não pode ser negativo")
    if p.investment is not None and p.investment < 0:
        raise ValueError("investment não pode ser negativo")
    if p.discount_rate < 0:
        raise ValueError("discount_rate não pode ser negativa")
    for name in ("deadweight", "attribution", "drop_off"):
        v = getattr(p, name)
        if not 0 <= v <= 1:
            raise ValueError(f"{name} deve estar entre 0 e 1")


def _nonneg(v: float | None) -> bool:
    return is_num(v) and v >= 0  # type: ignore[operator]


def annuity_factor(years: float, rate: float) -> float:
    """Σ_{k=1..anos} 1/(1+taxa)^k, iterativo (anos é arredondado para baixo)."""
    total = 0.0
    disc = 1.0
    growth = 1.0 + rate
    for _ in range(int(years)):
        disc = disc * growth
        total = total + 1.0 / disc
    return total


def components(b: Baseline, p: Params) -> tuple[dict[str, float], list[str]]:
    """Componentes do benefício anual. Valores ausentes, NaN ou negativos ficam fora (listados em `missing`)."""
    comp: dict[str, float] = {}
    missing: list[str] = []
    if p.use_hospital:
        if not _nonneg(b.hospital_cost):
            missing.append("hospital")
        else:
            comp["hospital"] = b.hospital_cost  # type: ignore[assignment]
    if p.use_productivity:
        # Dias de internação × renda diária. Para menores de 14 anos o dia conta como um dia de
        # acompanhante adulto, então todos os dias entram com a mesma renda de referência.
        if not _nonneg(b.hospital_days) or not _nonneg(b.daily_income):
            missing.append("productivity")
        else:
            comp["productivity"] = b.hospital_days * b.daily_income  # type: ignore[operator]
    if p.use_outpatient:
        if not _nonneg(b.hospital_cost) or p.outpatient_multiplier <= 0:
            missing.append("outpatient")
        else:
            comp["outpatient"] = b.hospital_cost * p.outpatient_multiplier  # type: ignore[operator]
    if p.use_deaths:
        if not _nonneg(b.deaths) or not _nonneg(b.productive_years_lost) or not _nonneg(b.daily_income):
            missing.append("deaths")
        else:
            # Cada óbito evitado no ano vale o VALOR PRESENTE da renda dos anos produtivos perdidos
            # (anuidade descontada), não a soma sem desconto (revisão M3).
            annual_income = b.daily_income * 365.0  # type: ignore[operator]
            comp["deaths"] = b.deaths * annuity_factor(b.productive_years_lost, p.discount_rate) * annual_income  # type: ignore[operator]
    return comp, missing


def present_value(annual: float, horizon: int, rate: float, drop_off: float = 0.0, adjust: float = 1.0) -> float:
    """Σ_{t=1..H} annual × adjust × (1 − drop_off)^(t−1) / (1 + rate)^t, com fatores iterativos."""
    total = 0.0
    disc = 1.0
    keep = 1.0
    growth = 1.0 + rate
    retain = 1.0 - drop_off
    for _ in range(horizon):
        disc = disc * growth
        total = total + (annual * adjust * keep) / disc
        keep = keep * retain
    return total


def calculate(b: Baseline, p: Params) -> Result:
    _validate(p)
    comp, missing = components(b, p)
    base = 0.0
    for key in ("hospital", "productivity", "outpatient", "deaths"):
        if key in comp:
            base = base + comp[key]
    r = p.reduction_pct / 100.0
    annual_saving = base * r
    pv = present_value(annual_saving, p.horizon_years, p.discount_rate)
    school = b.school_days * r if _nonneg(b.school_days) else None  # type: ignore[operator]
    res = Result(
        annual_base=base,
        components=comp,
        annual_saving=annual_saving,
        pv_saving=pv,
        school_days_avoided=school,
        missing=missing,
    )
    if p.investment is not None and p.investment > 0:
        adjust = (1.0 - p.deadweight) * p.attribution
        res.sroi_pv = present_value(annual_saving, p.horizon_years, p.discount_rate, p.drop_off, adjust)
        res.sroi_ratio = res.sroi_pv / p.investment
    return res


def _span(lo: float, hi: float, v: float) -> tuple[float, float]:
    """Intervalo que sempre contém o valor escolhido pelo usuário (revisão M3)."""
    return (lo if lo < v else v, hi if hi > v else v)


def sensitivity(
    b: Baseline, p: Params, ranges: dict[str, tuple[float, float]]
) -> dict[str, tuple[float, float] | None]:
    """Faixas (mínimo, máximo) do VP simples e do VP SROI, variando as premissas principais.

    O VP é monotônico em cada premissa (decrescente na taxa, no deadweight e no drop-off; crescente na
    atribuição), então os extremos ficam nos cantos. Cada intervalo é estendido para incluir o valor
    escolhido pelo usuário, que portanto sempre está dentro da faixa.
    """
    lo_rate, hi_rate = _span(*ranges.get("discount_rate", (p.discount_rate, p.discount_rate)), p.discount_rate)
    pv = (
        calculate(b, _replace(p, discount_rate=hi_rate)).pv_saving,
        calculate(b, _replace(p, discount_rate=lo_rate)).pv_saving,
    )
    out: dict[str, tuple[float, float] | None] = {"pv": pv, "sroi_pv": None}
    if p.investment is not None and p.investment > 0:
        dw = _span(*ranges.get("deadweight", (p.deadweight, p.deadweight)), p.deadweight)
        at = _span(*ranges.get("attribution", (p.attribution, p.attribution)), p.attribution)
        do = _span(*ranges.get("drop_off", (p.drop_off, p.drop_off)), p.drop_off)
        worst_p = _replace(p, discount_rate=hi_rate, deadweight=dw[1], attribution=at[0], drop_off=do[1])
        best_p = _replace(p, discount_rate=lo_rate, deadweight=dw[0], attribution=at[1], drop_off=do[0])
        out["sroi_pv"] = (calculate(b, worst_p).sroi_pv or 0.0, calculate(b, best_p).sroi_pv or 0.0)
    return out


def _replace(p: Params, **kw) -> Params:
    d = asdict(p)
    d.update(kw)
    return Params(**d)

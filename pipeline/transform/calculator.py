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

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Baseline:
    """Benefício anual base de um município (valores médios anuais, R$ do ano-base)."""

    hospital_cost: float | None  # valor pago SIH, média anual corrigida
    hospital_days: float | None  # dias de permanência, média anual (todas as idades)
    school_days: float | None  # dias de internação de 6 a 17 anos, média anual
    daily_income: float | None  # renda diária de referência (R$/dia)
    deaths: float | None = None  # óbitos por DRSAI, média anual (SIM)
    productive_years_lost: float | None = None  # anos produtivos perdidos por óbito (média)


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


def _validate(p: Params) -> None:
    if not 0 <= p.reduction_pct <= 100:
        raise ValueError("reduction_pct deve estar entre 0 e 100")
    if not 1 <= p.horizon_years <= 30:
        raise ValueError("horizon_years deve estar entre 1 e 30")
    if p.discount_rate < 0:
        raise ValueError("discount_rate não pode ser negativa")
    for name in ("deadweight", "attribution", "drop_off"):
        v = getattr(p, name)
        if not 0 <= v <= 1:
            raise ValueError(f"{name} deve estar entre 0 e 1")


def components(b: Baseline, p: Params) -> tuple[dict[str, float], list[str]]:
    comp: dict[str, float] = {}
    missing: list[str] = []
    if p.use_hospital:
        if b.hospital_cost is None:
            missing.append("hospital")
        else:
            comp["hospital"] = b.hospital_cost
    if p.use_productivity:
        # Dias de internação × renda diária. Para menores de 14 anos o dia conta como um dia de
        # acompanhante adulto, então todos os dias entram com a mesma renda de referência.
        if b.hospital_days is None or b.daily_income is None:
            missing.append("productivity")
        else:
            comp["productivity"] = b.hospital_days * b.daily_income
    if p.use_outpatient:
        if b.hospital_cost is None or p.outpatient_multiplier <= 0:
            missing.append("outpatient")
        else:
            comp["outpatient"] = b.hospital_cost * p.outpatient_multiplier
    if p.use_deaths:
        if b.deaths is None or b.productive_years_lost is None or b.daily_income is None:
            missing.append("deaths")
        else:
            comp["deaths"] = b.deaths * b.productive_years_lost * (b.daily_income * 365.0)
    return comp, missing


def present_value(
    annual: float, horizon: int, rate: float, drop_off: float = 0.0, adjust: float = 1.0
) -> float:
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
    school = None if b.school_days is None else b.school_days * r
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


def sensitivity(b: Baseline, p: Params, ranges: dict[str, tuple[float, float]]) -> tuple[float, float]:
    """Faixa (mínimo, máximo) do valor presente variando as premissas principais nos seus intervalos.

    O VP é monotônico em cada premissa (decrescente na taxa, no deadweight e no drop-off; crescente na
    atribuição), então os extremos ficam nos cantos do intervalo.
    """
    lo_rate, hi_rate = ranges.get("discount_rate", (p.discount_rate, p.discount_rate))
    sroi = p.investment is not None and p.investment > 0
    if not sroi:
        worst = calculate(b, _replace(p, discount_rate=hi_rate)).pv_saving
        best = calculate(b, _replace(p, discount_rate=lo_rate)).pv_saving
        return worst, best
    dw = ranges.get("deadweight", (p.deadweight, p.deadweight))
    at = ranges.get("attribution", (p.attribution, p.attribution))
    do = ranges.get("drop_off", (p.drop_off, p.drop_off))
    worst_p = _replace(p, discount_rate=hi_rate, deadweight=dw[1], attribution=at[0], drop_off=do[1])
    best_p = _replace(p, discount_rate=lo_rate, deadweight=dw[0], attribution=at[1], drop_off=do[0])
    return calculate(b, worst_p).sroi_pv or 0.0, calculate(b, best_p).sroi_pv or 0.0


def _replace(p: Params, **kw) -> Params:
    d = asdict(p)
    d.update(kw)
    return Params(**d)

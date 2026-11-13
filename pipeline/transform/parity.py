"""Casos de paridade Python → TypeScript da calculadora.

Regenerar (depois de mudar a calculadora): `uv run python -m pipeline.transform.parity`
O teste `pipeline/tests/test_calculator_parity.py` falha se o arquivo versionado divergir do gerado, e o Vitest
(`site/src/lib/calculator.test.ts`) exige igualdade exata (===) do TypeScript com cada caso.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict

from pipeline.config import ROOT, load
from pipeline.transform.calculator import Baseline, Params, calculate, sensitivity

OUT = ROOT / "site" / "src" / "lib" / "calculator.parity.json"
OUT_INDEX = ROOT / "site" / "src" / "lib" / "priority.parity.json"


def index_cases() -> str:
    from pipeline.transform.priority_index import rank, weighted_index

    rng = random.Random(42)
    dims = ["acesso", "saude", "vulnerabilidade", "clima", "qualidade"]
    rows = []
    for _ in range(150):
        ds = {d: rng.choice([None, round(rng.uniform(0, 100), 6), 0.0, 100.0]) for d in dims}
        w = {d: rng.choice([0.0, rng.uniform(0, 1)]) for d in dims}
        md = rng.randint(1, 5)
        req = rng.choice([[], ["acesso", "saude"]])
        idx, cov = weighted_index(ds, w, md, tuple(req))
        rows.append({"dims": ds, "weights": w, "min_dims": md, "required": req, "index": idx, "coverage": cov})
    scores = {f"{i:07d}": rng.choice([None, float(rng.randint(0, 20))]) for i in range(60)}
    return (
        json.dumps(
            {"cases": rows, "rank": {"scores": scores, "expected": rank(scores)}},
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def ranges() -> dict[str, tuple[float, float]]:
    cfg = load("calculadora")
    s = cfg["sroi"]["sensitivity"]
    return {
        "discount_rate": tuple(cfg["discount_rate_sensitivity"]),
        "deadweight": tuple(s["deadweight"]),
        "attribution": tuple(s["attribution"]),
        "drop_off": tuple(s["drop_off"]),
    }


def _cases() -> list[tuple[Baseline, Params]]:
    rng = random.Random(20331231)
    out: list[tuple[Baseline, Params]] = [
        (Baseline(100_000.0, 1_000.0, 200.0, 50.0), Params(reduction_pct=50, horizon_years=3, discount_rate=0.10)),
        (Baseline(None, 10.0, None, None), Params()),
        (Baseline(0.0, 0.0, 0.0, 0.0), Params(reduction_pct=100, horizon_years=30, discount_rate=0.0)),
        (
            Baseline(1234567.89, 4321.5, 77.25, 31.7),
            Params(
                reduction_pct=92,
                horizon_years=20,
                discount_rate=0.085,
                investment=2_500_000,
                deadweight=0.1,
                attribution=0.8,
                drop_off=0.05,
            ),
        ),
        # bordas: taxa fora da faixa de sensibilidade, drop-off total, atribuição zero, negativos
        (
            Baseline(5e5, 2e3, 10.0, 40.0),
            Params(discount_rate=0.0, investment=1e6, deadweight=0.0, attribution=1.0, drop_off=1.0),
        ),
        (
            Baseline(5e5, 2e3, 10.0, 40.0),
            Params(discount_rate=0.2, investment=1e6, deadweight=0.6, attribution=0.0, drop_off=0.3),
        ),
        (Baseline(-10.0, -5.0, -1.0, 40.0), Params()),
        (
            Baseline(5e5, 2e3, 10.0, 40.0, deaths=3.0, productive_years_lost=30.0),
            Params(use_deaths=True, use_outpatient=True, outpatient_multiplier=1.5, horizon_years=30),
        ),
    ]
    for _ in range(240):
        b = Baseline(
            hospital_cost=rng.choice([None, rng.uniform(0, 5e7)]),
            hospital_days=rng.choice([None, rng.uniform(0, 5e5)]),
            school_days=rng.choice([None, rng.uniform(0, 1e4)]),
            daily_income=rng.choice([None, rng.uniform(5, 300)]),
            deaths=rng.choice([None, rng.uniform(0, 50)]),
            productive_years_lost=rng.choice([None, float(rng.randint(0, 45))]),
        )
        p = Params(
            reduction_pct=rng.choice([0, 25, 50, 92, 100, rng.uniform(0, 100)]),
            horizon_years=rng.randint(1, 30),
            discount_rate=rng.choice([0.0, 0.04, 0.085, 0.12, rng.uniform(0, 0.3)]),
            use_hospital=rng.random() > 0.2,
            use_productivity=rng.random() > 0.2,
            use_outpatient=rng.random() > 0.7,
            outpatient_multiplier=rng.choice([0.0, rng.uniform(0, 3)]),
            use_deaths=rng.random() > 0.7,
            investment=rng.choice([None, 0.0, rng.uniform(1e3, 1e8)]),
            deadweight=rng.uniform(0, 1),
            attribution=rng.uniform(0, 1),
            drop_off=rng.uniform(0, 1),
        )
        out.append((b, p))
    return out


def generate() -> list[dict]:
    rg = ranges()
    rows = []
    for b, p in _cases():
        r = calculate(b, p)
        sens = sensitivity(b, p, rg)
        rows.append(
            {
                "baseline": asdict(b),
                "params": asdict(p),
                "result": r.to_dict(),
                "sensitivity": {k: (list(v) if v else None) for k, v in sens.items()},
            }
        )
    return rows


def serialize(rows: list[dict]) -> str:
    return json.dumps({"ranges": ranges(), "cases": rows}, separators=(",", ":"), allow_nan=False) + "\n"


def main() -> None:
    OUT.write_text(serialize(generate()))
    OUT_INDEX.write_text(index_cases())
    print(f"escrito {OUT} e {OUT_INDEX}")


if __name__ == "__main__":
    main()

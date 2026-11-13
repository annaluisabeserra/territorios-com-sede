"""Gera os casos de paridade Python → TypeScript (site/src/lib/calculator.parity.json).

O Vitest (site/src/lib/calculator.test.ts) recalcula cada caso em TS e exige igualdade exata (===).
Rodar este teste regrava o arquivo; o CI falha se o arquivo versionado divergir do gerado.
"""

import json
import random
from dataclasses import asdict
from pathlib import Path

from pipeline.transform.calculator import Baseline, Params, calculate, sensitivity

OUT = Path(__file__).resolve().parents[2] / "site" / "src" / "lib" / "calculator.parity.json"


def cases() -> list[dict]:
    rng = random.Random(20331231)
    out = []
    fixed = [
        (Baseline(100_000.0, 1_000.0, 200.0, 50.0), Params(reduction_pct=50, horizon_years=3, discount_rate=0.10)),
        (Baseline(None, 10.0, None, None), Params()),
        (Baseline(0.0, 0.0, 0.0, 0.0), Params(reduction_pct=100, horizon_years=30, discount_rate=0.0)),
        (Baseline(1234567.89, 4321.5, 77.25, 31.7), Params(reduction_pct=92, horizon_years=20, discount_rate=0.085,
                                                            investment=2_500_000, deadweight=0.1, attribution=0.8,
                                                            drop_off=0.05)),
    ]
    for b, p in fixed:
        out.append((b, p))
    for _ in range(200):
        b = Baseline(
            hospital_cost=rng.choice([None, rng.uniform(0, 5e7)]),
            hospital_days=rng.choice([None, rng.uniform(0, 5e5)]),
            school_days=rng.choice([None, rng.uniform(0, 1e4)]),
            daily_income=rng.choice([None, rng.uniform(5, 300)]),
        )
        inv = rng.choice([None, rng.uniform(1e3, 1e8)])
        p = Params(
            reduction_pct=rng.choice([0, 25, 50, 92, 100, rng.uniform(0, 100)]),
            horizon_years=rng.randint(1, 30),
            discount_rate=rng.choice([0.0, 0.04, 0.085, 0.12, rng.uniform(0, 0.3)]),
            use_hospital=rng.random() > 0.2,
            use_productivity=rng.random() > 0.2,
            investment=inv,
            deadweight=rng.uniform(0, 0.5),
            attribution=rng.uniform(0.3, 1),
            drop_off=rng.uniform(0, 0.3),
        )
        out.append((b, p))
    rows = []
    ranges = {"discount_rate": (0.04, 0.12), "deadweight": (0.0, 0.3), "attribution": (0.5, 1.0), "drop_off": (0.0, 0.15)}
    for b, p in out:
        r = calculate(b, p)
        rows.append({"baseline": asdict(b), "params": asdict(p), "result": r.to_dict(),
                     "sensitivity": list(sensitivity(b, p, ranges))})
    return rows


def test_write_parity_cases():
    data = cases()
    text = json.dumps(data, indent=None, separators=(",", ":"), allow_nan=False)
    OUT.write_text(text + "\n")
    assert len(data) == 204

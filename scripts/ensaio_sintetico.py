"""Ensaio com dados SINTÉTICOS para ver as telas como ficarão quando todas as fontes entrarem.

NUNCA rode no repositório de verdade. Uso:

    rsync -a --exclude site/node_modules --exclude data/raw ./ /tmp/ensaio/
    ln -s "$PWD/site/node_modules" /tmp/ensaio/site/node_modules
    ln -s "$PWD/data/raw" /tmp/ensaio/data/raw
    uv run python scripts/ensaio_sintetico.py /tmp/ensaio
    cd /tmp/ensaio && uv run python -m pipeline.run --only-build && cd site && npm run build

O script se recusa a escrever se o destino for este repositório. Os valores são aleatórios (semente fixa), com
ordem de grandeza plausível, e cada arquivo leva "DADO SINTÉTICO" nos metadados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SYNTH = "DADO SINTÉTICO (ensaio de interface, não publicar)"


def meta(path: Path, source_id: str, period: str) -> None:
    m = {
        "output": path.name,
        "status": "ok",
        "status_reason": "",
        "sources": [
            {
                "source_id": source_id,
                "name": f"{source_id} — {SYNTH}",
                "url": "sintetico://",
                "url_kind": "official",
                "reference_period": period,
                "fetched_at": "2026-11-14T00:00:00Z",
                "sha256": "",
                "license": "",
                "notes": SYNTH,
            }
        ],
    }
    path.with_name(path.name + ".meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=2))


def write(df: pd.DataFrame, d: Path, name: str, source_id: str, period: str) -> None:
    p = d / f"{name}.parquet"
    df.to_parquet(p, index=False)
    meta(p, source_id, period)


def main(target: Path) -> None:
    if target.resolve() == REPO:
        sys.exit("recusado: o destino é o repositório de verdade")
    rng = np.random.default_rng(2033)
    ufs_dir = target / "data" / "processed"
    for d in sorted(p for p in ufs_dir.iterdir() if p.is_dir()):
        pop = pd.read_parquet(d / "populacao.parquet").set_index("cod_ibge7")["populacao"]
        mun = pop.index.tolist()
        # SIH: 2019–2023 (o IPCA da cópia pública vai até 07/2024)
        rows = []
        for c in mun:
            lam = max(pop[c] * 18 / 10_000 / 12, 0.05) * rng.uniform(0.3, 2.5)
            for y in range(2019, 2024):
                for m in range(1, 13):
                    for g, share in (("feco_oral", 0.8), ("contato_agua", 0.15), ("geo_helmintos", 0.05)):
                        n = int(rng.poisson(lam * share))
                        if n:
                            rows.append(
                                (
                                    c,
                                    y,
                                    m,
                                    g,
                                    n,
                                    n * rng.uniform(350, 650),
                                    n * rng.uniform(2.5, 4.5),
                                    int(rng.poisson(n * 0.004)),
                                    n * rng.uniform(0.3, 0.9),
                                    n * rng.uniform(0.8, 1.8),
                                    int(n * rng.uniform(0.2, 0.4)),
                                )
                            )
        cols = [
            "cod_ibge7",
            "year",
            "month",
            "group",
            "internacoes",
            "valor_nominal",
            "dias",
            "obitos",
            "dias_6_17",
            "dias_menor14",
            "internacoes_menor5",
        ]
        write(pd.DataFrame(rows, columns=cols), d, "sih_drsai", "datasus_sih", "2019–2023 (ano de processamento)")
        # SIM: óbitos por grupo e idade, 2019–2023
        rows = []
        for c in mun:
            lam = pop[c] * 4 / 100_000 * rng.uniform(0.3, 2.5)
            for y in range(2019, 2024):
                for _ in range(int(rng.poisson(lam))):
                    age = float(rng.choice([0, 1, 3, 25, 45, 62, 70, 80]))
                    rows.append((y, "feco_oral", age, 1, c))
        sim = pd.DataFrame(rows, columns=["year", "group", "age", "obitos", "cod_ibge7"])
        sim = sim.groupby(["cod_ibge7", "year", "group", "age"], as_index=False)["obitos"].sum()
        write(sim, d, "sim_drsai", "datasus_sim", "2019–2023")
        n = len(mun)
        write(
            pd.DataFrame(
                {
                    "cod_ibge7": mun,
                    "sisagua_amostras": rng.integers(50, 3000, n),
                    "sisagua_pct_fora_padrao": rng.gamma(2, 2.5, n).clip(0, 60),
                    "sisagua_ecoli_amostras": rng.integers(5, 400, n),
                    "sisagua_ecoli_pct_fora": rng.gamma(1, 1.5, n).clip(0, 40),
                }
            ),
            d,
            "sisagua",
            "sisagua",
            "2025",
        )
        write(
            pd.DataFrame(
                {
                    "cod_ibge7": mun,
                    "decretos_seca_5a": rng.poisson(2, n).astype(float),
                    "decretos_chuva_5a": rng.poisson(0.6, n).astype(float),
                }
            ),
            d,
            "s2id",
            "s2id",
            "2021–2025",
        )
        meses = rng.integers(0, 13, n).astype(float)
        write(
            pd.DataFrame(
                {
                    "cod_ibge7": mun,
                    "seca_meses_12m": meses,
                    "seca_classe_max_12m": np.where(meses > 0, rng.integers(0, 5, n), np.nan),
                }
            ),
            d,
            "monitor_secas",
            "monitor_secas",
            "2025-11 a 2026-10 (12 meses)",
        )
        esc = rng.integers(3, 120, n)
        write(
            pd.DataFrame(
                {
                    "cod_ibge7": mun,
                    "escolas_publicas": esc.astype(float),
                    "escolas_sem_agua_potavel_pct": rng.beta(1, 8, n) * 100,
                    "escolas_sem_banheiro_pct": rng.beta(1, 25, n) * 100,
                    "escolas_sem_esgoto_pct": rng.beta(1, 15, n) * 100,
                    "escolas_sem_agua_potavel_matriculas": (esc * rng.uniform(5, 60, n)).round(),
                    "escolas_sem_agua_potavel_n": (esc * rng.uniform(0, 0.25, n)).round(),
                    "escolas_sem_banheiro_matriculas": (esc * rng.uniform(0, 10, n)).round(),
                    "escolas_sem_esgoto_matriculas": (esc * rng.uniform(0, 20, n)).round(),
                }
            ),
            d,
            "censo_escolar",
            "censo_escolar",
            "2025",
        )
        desp = pop.values * rng.uniform(5, 120, n)
        desp[rng.random(n) < 0.1] = np.nan  # municípios sem declaração
        write(
            pd.DataFrame({"cod_ibge7": mun, "despesa_saneamento": desp, "despesa_saneamento_ano": 2025}),
            d,
            "siconfi",
            "siconfi",
            "2025",
        )
        print(f"{d.name}: {n} municípios com dados sintéticos")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))

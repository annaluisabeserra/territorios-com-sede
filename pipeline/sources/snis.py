"""SNIS — série histórica municipal de água e esgoto (anos de referência até 2022).

A partir do ano de referência 2023 o SNIS foi substituído pelo SINISA (coleta 2024). A transição está
documentada em docs/METODOLOGIA.md; enquanto não houver arquivo aberto estável do SINISA por município,
a série termina em 2022 e o .meta.json diz isso.
"""

from __future__ import annotations

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, fetch_one, make_meta, try_chain
from pipeline.sources.http import SourceURL

# Código SNIS → coluna na tabela br_mdr_snis.municipio_agua_esgoto (Base dos Dados) → nome interno.
INDICATORS = {
    "IN055": ("indice_atendimento_total_agua", "snis_agua_pct"),
    "IN056": ("indice_atendimento_esgoto_agua", "snis_esgoto_pct"),
    "IN046": ("indice_esgotamento_agua_consumida", "snis_tratamento_pct"),
    "IN049": ("indice_perda_distribuicao_agua", "snis_perdas_pct"),
    "IN015": ("indice_coleta_esgoto", "snis_coleta_esgoto_pct"),
    "IN016": ("indice_tratamento_esgoto", "snis_tratamento_coletado_pct"),
    "IN022": ("indice_consumo_agua_per_capita", "snis_consumo_lhabdia"),
}
EXTRA = {
    "populacao_atendida_agua": "snis_pop_atendida_agua",
    "populacao_atentida_esgoto": "snis_pop_atendida_esgoto",
}
PCT_CAP = {
    "snis_agua_pct",
    "snis_esgoto_pct",
    "snis_tratamento_pct",
    "snis_coleta_esgoto_pct",
    "snis_tratamento_coletado_pct",
}


def municipal_series(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("snis", src, "bd_snis_municipio_agua_esgoto.csv.gz", "national", max_age_days=60)
        cols = ["ano", "id_municipio"] + [c for c, _ in INDICATORS.values()] + list(EXTRA)
        df = pd.read_csv(f.path, dtype={"id_municipio": str}, usecols=lambda c: c in cols)
        df = df.rename(columns={"id_municipio": "cod_ibge7", "ano": "year"})
        df = df.rename(columns={c: n for c, n in INDICATORS.values()}).rename(columns=EXTRA)
        df = df[df["cod_ibge7"].str.startswith(uf.code)]
        # Uma linha por município-ano (a tabela já é agregada por município; garantimos)
        df = df.groupby(["cod_ibge7", "year"], as_index=False).first()
        flags = {}
        # Perdas fora de 0–100 são inconsistências de medição declaradas pelo prestador: viram ausentes.
        if "snis_perdas_pct" in df.columns:
            bad = (df["snis_perdas_pct"] < 0) | (df["snis_perdas_pct"] > 100)
            flags["snis_perdas_pct_invalid_to_null"] = int(bad.sum())
            df.loc[bad, "snis_perdas_pct"] = float("nan")
        for col in sorted(PCT_CAP & set(df.columns)):
            # Até 105%: diferença de denominador (população estimada), limitada a 100.
            # Acima de 105%: erro de declaração, vira ausente (ex.: IN046 de 633%).
            absurd = df[col] > 105
            over = (df[col] > 100) & ~absurd
            flags[f"{col}_capped"] = int(over.sum())
            flags[f"{col}_absurd_to_null"] = int(absurd.sum())
            df.loc[over, col] = 100.0
            df.loc[absurd, col] = float("nan")
        # Coleta com tratamento (proxy da meta do Marco Legal): IN056 × IN016 / 100
        if {"snis_esgoto_pct", "snis_tratamento_coletado_pct"} <= set(df.columns):
            df["snis_esgoto_tratado_pct"] = df["snis_esgoto_pct"] * df["snis_tratamento_coletado_pct"] / 100
        years = f"{int(df['year'].min())}–{int(df['year'].max())}" if len(df) else "sem dados"
        meta = make_meta(
            "snis",
            f,
            years,
            src.note
            + "; coberturas entre 100% e 105% limitadas a 100, acima de 105% e perdas fora de 0–100 tratadas como ausentes (ver flags)",
        )
        return SourceResult(df, meta, flags)

    return try_chain("snis", uf, {"mirror": mirror})

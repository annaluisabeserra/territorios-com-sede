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
        for col in PCT_CAP & set(df.columns):
            over = df[col] > 100
            flags[f"{col}_capped"] = int(over.sum())
            df.loc[over, col] = 100.0
        years = f"{int(df['year'].min())}–{int(df['year'].max())}" if len(df) else "sem dados"
        meta = make_meta("snis", f, years, src.note + "; valores acima de 100% limitados a 100 (ver flags)")
        return SourceResult(df, meta, flags)

    return try_chain("snis", uf, {"mirror": mirror})

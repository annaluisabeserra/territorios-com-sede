"""ANA — Atlas Esgotos (referência 2013): situação do esgotamento da população urbana por município."""

from __future__ import annotations

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, fetch_one, make_meta, try_chain
from pipeline.sources.http import SourceURL

COLS = {
    "indice_atendimento_com_coleta_com_tratamento": "ana_coleta_tratamento_pct",
    "indice_atendimento_com_coleta_sem_tratamento": "ana_coleta_sem_tratamento_pct",
    "indice_atendimento_solucao_individual": "ana_solucao_individual_pct",
    "indice_sem_atendimento_sem_coleta_sem_tratamento": "ana_sem_atendimento_pct",
}


def atlas_esgotos(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ana_atlas_esgotos", src, "bd_ana_atlas_esgotos.csv.gz", "national", max_age_days=180)
        df = pd.read_csv(f.path, dtype={"id_municipio": str}, usecols=["id_municipio", *COLS])
        df = df.rename(columns={"id_municipio": "cod_ibge7", **COLS})
        df = df[df["cod_ibge7"].str.startswith(uf.code)].copy()
        for c in COLS.values():  # frações 0–1 → percentuais 0–100
            df[c] = df[c] * 100
        return SourceResult(df, make_meta("ana_atlas_esgotos", f, "2013 (população urbana)", src.note))

    return try_chain("ana_atlas_esgotos", uf, {"mirror": mirror})

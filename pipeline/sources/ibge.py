"""IBGE: municípios, malhas, semiárido e tabelas do Censo 2022.

Oficial: APIs servicodados.ibge.gov.br. Espelhos: Base dos Dados (GCS público) e geobr (Ipea).
Todas as funções devolvem dados só da UF pedida, com `cod_ibge7` como chave (string de 7 dígitos).
"""

from __future__ import annotations

import json
import re
import unicodedata

import geopandas as gpd
import pandas as pd

from pipeline.config import UF
from pipeline.sources import sidra
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, try_chain
from pipeline.sources.http import SourceURL

CENSUS_PERIOD = "2022 (data de referência 01/08/2022)"


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm


def _only_census_2022(df: pd.DataFrame) -> pd.DataFrame:
    """Alguns espelhos trazem 2010 e 2022 na mesma tabela: fica só 2022 (falha se não houver)."""
    if "ano" not in df.columns:
        return df
    out = df[df["ano"] == 2022]
    if out.empty:
        raise SourceUnavailable("espelho sem linhas do Censo 2022")
    return out


def _uf_filter(df: pd.DataFrame, uf: UF, col: str = "cod_ibge7") -> pd.DataFrame:
    df[col] = df[col].astype(str).str.replace(r"\.0$", "", regex=True)
    return df[df[col].str.startswith(uf.code) & (df[col].str.len() == 7)].copy()


# --------------------------------------------------------------------------- municípios


def municipios(uf: UF) -> SourceResult:
    def official(src: SourceURL) -> SourceResult:
        f = fetch_one("ibge_municipios", src, f"municipios_{uf.sigla}.json", "ibge", max_age_days=30)
        rows = []
        for m in json.loads(f.path.read_text(encoding="utf-8")):
            ri = m.get("regiao-imediata") or {}
            rint = ri.get("regiao-intermediaria") or {}
            rows.append(
                {
                    "cod_ibge7": str(m["id"]),
                    "nome": m["nome"],
                    "regiao_imediata": ri.get("nome"),
                    "regiao_intermediaria": rint.get("nome"),
                    "microrregiao": (m.get("microrregiao") or {}).get("nome"),
                }
            )
        return SourceResult(_finish(pd.DataFrame(rows), uf), make_meta("ibge_municipios", f, "vigente"))

    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ibge_municipios", src, "bd_diretorio_municipio.csv.gz", "national", max_age_days=90)
        df = pd.read_csv(f.path, dtype=str)
        df = df.rename(
            columns={
                "id_municipio": "cod_ibge7",
                "nome_regiao_imediata": "regiao_imediata",
                "nome_regiao_intermediaria": "regiao_intermediaria",
                "nome_microrregiao": "microrregiao",
            }
        )
        df = _uf_filter(df, uf)[["cod_ibge7", "nome", "regiao_imediata", "regiao_intermediaria", "microrregiao"]]
        # O espelho traz o travessão dos nomes de regiões corrompido como "¿" (ex.: "Ilhéus ¿ Itabuna").
        # Restauramos o travessão usado pelo IBGE ("Ilhéus - Itabuna"). Correção só de grafia, registrada no meta.
        for c in ("regiao_imediata", "regiao_intermediaria", "microrregiao"):
            df[c] = df[c].str.replace(" ¿ ", " - ", regex=False)
        return SourceResult(
            _finish(df, uf),
            make_meta(
                "ibge_municipios", f, "vigente", src.note + "; caractere '¿' corrigido para '-' nos nomes de regiões"
            ),
        )

    return try_chain("ibge_municipios", uf, {"official": official, "mirror": mirror})


def _finish(df: pd.DataFrame, uf: UF) -> pd.DataFrame:
    df = df.sort_values("cod_ibge7").reset_index(drop=True)
    df["cod_ibge6"] = df["cod_ibge7"].str[:6]
    df["uf"] = uf.sigla
    df["slug"] = df["nome"].map(slugify)
    # Desambigua slugs repetidos dentro da UF (raro, mas possível)
    dup = df["slug"].duplicated(keep=False)
    df.loc[dup, "slug"] = df.loc[dup, "slug"] + "-" + df.loc[dup, "cod_ibge7"]
    return df


# --------------------------------------------------------------------------- malhas


def malhas(uf: UF) -> SourceResult:
    def official(src: SourceURL) -> SourceResult:
        f = fetch_one("ibge_malhas", src, f"malha_{uf.sigla}.geojson", "ibge", max_age_days=180)
        gdf = gpd.read_file(f.path)
        gdf = gdf.rename(columns={"codarea": "cod_ibge7"})[["cod_ibge7", "geometry"]]
        gdf["cod_ibge7"] = gdf["cod_ibge7"].astype(str)
        return SourceResult(gdf.set_crs(4674, allow_override=True), make_meta("ibge_malhas", f, "2022"))

    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ibge_malhas", src, "geobr_municipalities_2022_simplified.parquet", "national")
        gdf = gpd.read_parquet(f.path)
        gdf["cod_ibge7"] = gdf["code_muni"].astype("Int64").astype(str)
        gdf = _uf_filter(gdf, uf)[["cod_ibge7", "geometry"]]
        return SourceResult(gdf, make_meta("ibge_malhas", f, "2022", src.note))

    return try_chain("ibge_malhas", uf, {"official": official, "mirror": mirror})


def semiarido(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ibge_semiarido", src, "geobr_semiarid_2022_simplified.parquet", "national")
        gdf = gpd.read_parquet(f.path)
        gdf["cod_ibge7"] = gdf["code_muni"].astype("Int64").astype(str)
        df = _uf_filter(pd.DataFrame(gdf.drop(columns="geometry")), uf)[["cod_ibge7"]]
        df["semiarido"] = True
        return SourceResult(df, make_meta("ibge_semiarido", f, "2022", src.note))

    return try_chain("ibge_semiarido", uf, {"mirror": mirror})


# --------------------------------------------------------------------------- Censo 2022


def populacao(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("censo_populacao", src, "bd_censo2022_populacao_idade_sexo.csv.gz", "national")
        df = pd.read_csv(f.path, dtype={"id_municipio": str}, usecols=["id_municipio", "populacao"])
        df = df.rename(columns={"id_municipio": "cod_ibge7"})
        df = _uf_filter(df, uf).groupby("cod_ibge7", as_index=False)["populacao"].sum()
        df["populacao"] = df["populacao"].round().astype("int64")
        return SourceResult(df, make_meta("censo_populacao", f, CENSUS_PERIOD, src.note))

    return _sidra_first("censo_populacao", uf, {"mirror": mirror}, value_name="populacao")


def quilombola(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("censo_quilombola", src, "bd_censo2022_quilombola.csv.gz", "national")
        df = _only_census_2022(pd.read_csv(f.path, dtype={"id_municipio": str}))
        df = df.rename(columns={"id_municipio": "cod_ibge7"})
        df = _uf_filter(df, uf)
        em = df["localizacao_domicilio"].str.startswith("Em")
        g = pd.DataFrame(
            {
                # min_count=1: se todas as células estão sob sigilo, o total é desconhecido (None), não zero
                "pop_quilombola": df.groupby("cod_ibge7")["populacao_quilombola"].sum(min_count=1),
                "pop_quilombola_em_territorio": df[em].groupby("cod_ibge7")["populacao_quilombola"].sum(min_count=1),
                "cells_total": df.groupby("cod_ibge7")["populacao_quilombola"].size(),
                "cells_suppressed": df.groupby("cod_ibge7")["populacao_quilombola"].apply(
                    lambda x: int(x.isna().sum())
                ),
            }
        )
        g["pct_cells_suppressed"] = g["cells_suppressed"] / g["cells_total"] * 100
        g = g.reset_index()
        meta = make_meta(
            "censo_quilombola",
            f,
            CENSUS_PERIOD,
            src.note + ". Valores são soma de células por idade e sexo: mínimo garantido, não total exato; "
            "município com todas as células sob sigilo fica sem dado.",
        )
        return SourceResult(g, meta, {"lower_bound": True})

    return _sidra_first("censo_quilombola", uf, {"mirror": mirror}, value_name="pop_quilombola")


def raca(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("censo_raca", src, "bd_censo2022_raca.csv.gz", "national")
        df = _only_census_2022(pd.read_csv(f.path, dtype={"id_municipio": str}))
        df = df.rename(columns={"id_municipio": "cod_ibge7"})
        df = _uf_filter(df, uf)
        piv = df.pivot_table(index="cod_ibge7", columns="cor_raca", values="populacao", aggfunc="sum")
        out = pd.DataFrame({"cod_ibge7": piv.index})
        out["pop_cor_indigena"] = piv.get("Indígena", pd.Series(index=piv.index, dtype=float)).values
        out["pop_cor_preta_parda"] = (piv.get("Preta", 0) + piv.get("Parda", 0)).values
        out["pop_soma_cor_raca"] = piv.sum(axis=1).values
        return SourceResult(out, make_meta("censo_raca", f, CENSUS_PERIOD, src.note))

    return try_chain("censo_raca", uf, {"mirror": mirror})


LIXO_COLETADO = "Coletado"
LIXO_PARTES_COLETADO = {
    "Coletado no domicílio por serviço de limpeza",
    "Depositado em caçamba de serviço de limpeza",
}


def lixo(uf: UF) -> SourceResult:
    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("censo_lixo", src, "bd_censo2022_destino_lixo.csv.gz", "national")
        df = pd.read_csv(
            f.path, dtype={"id_municipio": str}, usecols=["ano", "id_municipio", "tipo_destino_lixo", "populacao"]
        )
        df = _only_census_2022(df).rename(columns={"id_municipio": "cod_ibge7"})
        df = _uf_filter(df, uf)
        # "Coletado" é subtotal das duas formas de coleta: exclui as partes para não contar em dobro.
        df = df[~df["tipo_destino_lixo"].isin(LIXO_PARTES_COLETADO)]
        piv = df.pivot_table(index="cod_ibge7", columns="tipo_destino_lixo", values="populacao", aggfunc="sum")
        total = piv.sum(axis=1)
        out = pd.DataFrame(
            {
                "cod_ibge7": piv.index,
                "moradores_dpp": total.values,
                "censo_lixo_coletado_pct": (piv[LIXO_COLETADO] / total * 100).values,
            }
        )
        return SourceResult(out, make_meta("censo_lixo", f, CENSUS_PERIOD, src.note))

    return try_chain("censo_lixo", uf, {"mirror": mirror})


def agua(uf: UF) -> SourceResult:
    return sidra.share_from_catalog("censo_agua", uf, "censo_agua_rede_pct")


def esgoto(uf: UF) -> SourceResult:
    return sidra.share_from_catalog(
        "censo_esgoto", uf, "censo_esgoto_adequado_pct", absolute_name="censo_com_esgoto_adequado_pessoas"
    )


def _sidra_first(source_id: str, uf: UF, handlers: dict, value_name: str) -> SourceResult:
    """Tenta a API oficial do SIDRA (descoberta por catálogo); se falhar, usa a cadeia de espelhos."""
    try:
        return sidra.total_from_catalog(source_id, uf, value_name)
    except Exception as exc:  # noqa: BLE001
        sidra_error = f"{type(exc).__name__}: {exc}"
    try:
        res = try_chain(source_id, uf, handlers)
    except SourceUnavailable as exc:
        raise SourceUnavailable(f"SIDRA: {sidra_error}\n{exc}") from exc
    res.meta.notes = (res.meta.notes + f" | SIDRA oficial indisponível: {sidra_error[:200]}").strip(" |")
    return res

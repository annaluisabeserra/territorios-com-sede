"""Checagens automáticas (SPEC §9). Erros derrubam o pipeline da UF; avisos vão para o relatório.

Saída: data/processed/{uf}/_validation.json (lido pelo VALIDATION_REPORT e pelo site).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa

from pipeline import config
from pipeline.sources.meta import read_meta
from pipeline.transform.geo_keys import ibge_check_digit

log = logging.getLogger(__name__)
JUMP_THRESHOLD = 0.5  # variação relativa anual acima disto gera aviso


class ValidationError(RuntimeError):
    pass


@dataclass
class Report:
    uf: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def check(self, cond: bool, msg: str) -> None:
        if not cond:
            self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


CODE = pa.Column(str, pa.Check.str_matches(r"^\d{7}$"), unique=True)
MUNICIPIOS = pa.DataFrameSchema(
    {"cod_ibge7": CODE, "nome": pa.Column(str), "slug": pa.Column(str, unique=True), "uf": pa.Column(str)}
)
POPULACAO = pa.DataFrameSchema({"cod_ibge7": CODE, "populacao": pa.Column(int, pa.Check.gt(0))})
PCT = pa.Check.in_range(0, 100)


def _read(uf: config.UF, name: str) -> pd.DataFrame | None:
    p = config.PROCESSED_DIR / uf.slug / f"{name}.parquet"
    meta = read_meta(p)
    if not p.exists() or (meta and meta.get("status") == "unavailable"):
        return None
    if name in {"malhas", "terras_indigenas"}:
        return gpd.read_parquet(p)
    return pd.read_parquet(p)


def check_municipios(uf: config.UF, rep: Report) -> pd.DataFrame:
    mun = _read(uf, "municipios")
    if mun is None:
        raise ValidationError(f"{uf.sigla}: lista de municípios indisponível")
    try:
        MUNICIPIOS.validate(mun, lazy=True)
    except pa.errors.SchemaErrors as exc:
        rep.errors.append(f"schema municípios: {exc.failure_cases.head(10).to_dict('records')}")
    rep.check(
        len(mun) == uf.expected_municipalities,
        f"{len(mun)} municípios, esperado {uf.expected_municipalities} (ufs.yaml)",
    )
    rep.check(mun["cod_ibge7"].str.startswith(uf.code).all(), "códigos fora da UF")
    bad_dv = [c for c in mun["cod_ibge7"] if ibge_check_digit(c[:6]) != int(c[6])]
    if bad_dv:
        rep.warn(f"códigos com dígito verificador fora da regra módulo 10 (exceções históricas do IBGE): {bad_dv}")
    rep.info["municipios"] = len(mun)
    return mun


def check_malhas(uf: config.UF, mun: pd.DataFrame, rep: Report) -> None:
    g = _read(uf, "malhas")
    if g is None:
        rep.errors.append("malha municipal indisponível")
        return
    a, b = set(g["cod_ibge7"]), set(mun["cod_ibge7"])
    rep.check(a == b, f"malha × lista: faltam {sorted(b - a)[:10]}, sobram {sorted(a - b)[:10]}")
    rep.check(bool(g.geometry.notna().all()), "geometrias nulas na malha")


def check_populacao(uf: config.UF, mun: pd.DataFrame, rep: Report) -> None:
    pop = _read(uf, "populacao")
    if pop is None:
        rep.errors.append("população indisponível")
        return
    try:
        POPULACAO.validate(pop, lazy=True)
    except pa.errors.SchemaErrors as exc:
        rep.errors.append(f"schema população: {exc.failure_cases.head(10).to_dict('records')}")
    rep.check(set(pop["cod_ibge7"]) == set(mun["cod_ibge7"]), "população não cobre exatamente os municípios")
    total = int(pop["populacao"].sum())
    rep.check(
        total == uf.census2022_population,
        f"soma da população {total:,} ≠ total oficial do Censo 2022 {uf.census2022_population:,} (tolerância zero)",
    )
    rep.info["populacao_total"] = total


def check_percentages(uf: config.UF, rep: Report) -> None:
    for name in ["censo_agua", "censo_esgoto", "censo_lixo", "snis", "ana_atlas"]:
        df = _read(uf, name)
        if df is None:
            rep.info.setdefault("fontes_indisponiveis", []).append(name)
            continue
        for col in [c for c in df.columns if c.endswith("_pct")]:
            s = df[col].dropna()
            bad = s[(s < 0) | (s > 100)]
            rep.check(bad.empty, f"{name}.{col}: {len(bad)} valores fora de 0–100 (ex.: {bad.head(3).tolist()})")


def check_census_consistency(uf: config.UF, rep: Report) -> None:
    pop = _read(uf, "populacao")
    raca = _read(uf, "censo_raca")
    if pop is not None and raca is not None and "pop_soma_cor_raca" in raca:
        m = raca.merge(pop, on="cod_ibge7")
        over = m[m["pop_soma_cor_raca"] > m["populacao"] * 1.001]
        # Muitos municípios = erro sistemático (ex.: Censos 2010 e 2022 somados): derruba a UF.
        # Um ou outro = inconsistência pontual da fonte: o build descarta a cor ou raça só desses municípios.
        systematic = len(over) > max(2, 0.01 * len(m))
        rep.check(
            not systematic, f"soma por cor ou raça maior que a população em {len(over)} municípios (anos misturados?)"
        )
        if len(over) and not systematic:
            rep.warn(
                f"cor ou raça descartada em {len(over)} município(s) com soma maior que a população: "
                f"{', '.join(over['cod_ibge7'].tolist())}"
            )
    q = _read(uf, "censo_quilombola")
    if pop is not None and q is not None:
        m = q.merge(pop, on="cod_ibge7")
        rep.check(not (m["pop_quilombola"] > m["populacao"]).any(), "população quilombola maior que a população")


def check_money(uf: config.UF, rep: Report) -> None:
    sih = _read(uf, "sih_drsai")
    if sih is None:
        rep.info.setdefault("fontes_indisponiveis", []).append("sih_drsai")
        return
    rep.check((sih["valor_nominal"] >= 0).all(), "valores monetários negativos no SIH")
    rep.check((sih["internacoes"] >= 0).all(), "contagens negativas no SIH")


def check_sih_crosswalk(uf: config.UF, rep: Report) -> None:
    p = config.PROCESSED_DIR / uf.slug / "sih_crosswalk_report.json"
    if not p.exists() or _read(uf, "sih_drsai") is None:
        return
    r = json.loads(p.read_text())
    # Códigos "ignorado" do DATASUS terminam em 0000 (ex.: 290000) e não são municípios.
    real_unmapped = [c for c in r["unmapped_codes"] if not c.endswith("0000")]
    rep.check(not real_unmapped, f"de-para 6→7 não cobre códigos do SIH: {real_unmapped}")
    if r["unmapped_rows"]:
        rep.warn(f"SIH: {r['unmapped_rows']} AIHs com município de residência ignorado ({r['unmapped_codes']})")
    if r.get("missing_files"):
        rep.warn(f"SIH: {len(r['missing_files'])} arquivos ausentes no FTP (ex.: {r['missing_files'][:5]})")


def check_series_jumps(uf: config.UF, rep: Report) -> None:
    snis = _read(uf, "snis")
    if snis is None:
        return
    jumps = []
    ref = int(snis["year"].max())
    for col in ["snis_agua_pct", "snis_esgoto_pct"]:
        # Variação entre anos PRESENTES (atravessa lacunas), normalizada pelo intervalo em anos.
        d = snis[["cod_ibge7", "year", col]].dropna().sort_values(["cod_ibge7", "year"])
        d = d[d["year"] >= ref - 7]
        d["prev"] = d.groupby("cod_ibge7")[col].shift()
        d["gap"] = d["year"] - d.groupby("cod_ibge7")["year"].shift()
        d["rel"] = ((d[col] - d["prev"]).abs() / d["prev"].where(d["prev"] > 0)) / d["gap"]
        for r in d[d["rel"] > JUMP_THRESHOLD].itertuples():
            jumps.append(
                {
                    "cod_ibge7": r.cod_ibge7,
                    "indicador": col,
                    "ano": int(r.year),
                    "variacao_anual": round(float(r.rel), 3),
                }
            )
    if jumps:
        rep.warn(f"{len(jumps)} saltos > {JUMP_THRESHOLD:.0%} ao ano nas séries SNIS (últimos 8 anos)")
    rep.info["saltos_series"] = jumps


def run_all(uf: config.UF) -> Report:
    rep = Report(uf=uf.sigla)
    mun = check_municipios(uf, rep)
    check_malhas(uf, mun, rep)
    check_populacao(uf, mun, rep)
    check_percentages(uf, rep)
    check_census_consistency(uf, rep)
    check_money(uf, rep)
    check_sih_crosswalk(uf, rep)
    check_series_jumps(uf, rep)
    out = config.PROCESSED_DIR / uf.slug / "_validation.json"
    out.write_text(json.dumps(rep.__dict__, ensure_ascii=False, indent=2, default=str))
    for w in rep.warnings:
        log.warning("[%s] %s", uf.sigla, w[:300])
    if rep.errors:
        raise ValidationError(f"{uf.sigla}: {len(rep.errors)} erro(s) de validação:\n- " + "\n- ".join(rep.errors))
    log.info("[%s] validação ok (%d avisos)", uf.sigla, len(rep.warnings))
    return rep

"""Transformação: data/processed/{uf} → indicadores, termômetro, índice e arquivos públicos.

Saídas (data/public/{uf}/):
  resumo.json                 visão da UF (mapa, rankings, perguntas guiadas, home)
  municipios/{slug}.json      ficha completa de cada município
  indice_sensibilidade.json   análise de sensibilidade dos pesos do índice
  terras_indigenas.geojson    polígonos oficiais (nível de território)
  malha.geojson               malha municipal (o site simplifica para a web)
  dados/                      downloads abertos (CSV + Parquet)
"""

from __future__ import annotations

import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline import config
from pipeline.sources.meta import read_meta
from pipeline.transform import act, summary, thermometer
from pipeline.transform import priority_index as pidx
from pipeline.transform.calculator import Baseline
from pipeline.transform.cid import core_groups

log = logging.getLogger(__name__)
SNIS_SERIES = ["snis_agua_pct", "snis_esgoto_pct", "snis_tratamento_pct", "snis_perdas_pct", "snis_coleta_esgoto_pct"]
DIVERGENCE_PP = 15.0
# Nome legível das etapas (quando a fonte está indisponível, o .meta.json não traz o nome)
SOURCE_NAMES = {
    "censo_agua": "IBGE — Censo 2022, abastecimento de água",
    "censo_esgoto": "IBGE — Censo 2022, esgotamento sanitário",
    "sih_drsai": "DATASUS — SIH/SUS, internações por DRSAI",
    "censo_quilombola": "IBGE — Censo 2022, pessoas quilombolas",
    "censo_raca": "IBGE — Censo 2022, cor ou raça",
    "terras_indigenas": "FUNAI — Terras indígenas",
}


# --------------------------------------------------------------------------- utilidades


def clean(v):
    """Converte para JSON: NaN/inf → None; numpy → nativo; arredonda floats para 4 casas."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    return v


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


class Inputs:
    """Leitura tolerante dos arquivos processados (None quando a fonte está indisponível)."""

    def __init__(self, uf: config.UF):
        self.uf = uf
        self.dir = config.PROCESSED_DIR / uf.slug

    def meta(self, name: str) -> dict | None:
        return read_meta(self.dir / f"{name}.parquet")

    def get(self, name: str) -> pd.DataFrame | None:
        p = self.dir / f"{name}.parquet"
        m = self.meta(name)
        if not p.exists() or (m and m.get("status") == "unavailable"):
            return None
        if name in {"malhas", "terras_indigenas"}:
            return gpd.read_parquet(p)
        return pd.read_parquet(p)

    def source_status(self) -> dict:
        out = {}
        for p in sorted(self.dir.glob("*.parquet.meta.json")):
            m = json.loads(p.read_text())
            name = p.name.replace(".parquet.meta.json", "")
            src = (m.get("sources") or [{}])[0]
            out[name] = {
                "status": m.get("status"),
                "status_reason": (m.get("status_reason") or "")[:300],
                "name": src.get("name") or SOURCE_NAMES.get(name, name),
                "url": src.get("url"),
                "url_kind": src.get("url_kind"),
                "reference_period": src.get("reference_period"),
                "fetched_at": src.get("fetched_at"),
                "license": src.get("license"),
                "notes": src.get("notes"),
            }
        return out


# --------------------------------------------------------------------------- saúde (SIH)


def health_tables(inp: Inputs, pop: pd.Series) -> tuple[pd.DataFrame | None, dict]:
    """Médias anuais DRSAI por município (núcleo e com vetores), deflacionadas pelo IPCA."""
    sih = inp.get("sih_drsai")
    ipca = inp.get("ipca")
    info: dict = {}
    if sih is None or sih.empty:
        return None, info
    years = sorted(sih["year"].unique())
    from pipeline.sources.ipca import annual_deflator, last_complete_year

    base_year = min(last_complete_year(ipca), int(max(years))) if ipca is not None else None
    defl = annual_deflator(ipca, base_year) if base_year else {}
    sih = sih.copy()
    sih["factor"] = sih["year"].map(defl)
    sih["valor_real"] = sih["valor_nominal"] * sih["factor"]
    info = {
        "years": [int(y) for y in years],
        "price_base": base_year,
        "years_without_deflator": [int(y) for y in years if y not in defl],
    }
    core = core_groups()

    def layer_avg(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
        per_year = df.groupby(["cod_ibge7", "year"], as_index=False)[
            ["internacoes", "valor_real", "dias", "obitos", "dias_6_17", "internacoes_menor5"]
        ].sum(min_count=1)
        # Média sobre todos os anos do período (anos sem internação valem zero de fato: o arquivo existe).
        full = pd.MultiIndex.from_product([pop.index, years], names=["cod_ibge7", "year"])
        per_year = per_year.set_index(["cod_ibge7", "year"]).reindex(full)
        cnt = per_year[["internacoes", "dias", "obitos", "dias_6_17", "internacoes_menor5"]].fillna(0)
        per_year[cnt.columns] = cnt
        # valor_real fica NaN se o ano não tem deflator; média só sobre anos com deflator
        per_year["valor_real"] = per_year["valor_real"].where(per_year.index.get_level_values("year").isin(list(defl)))
        per_year.loc[
            per_year["valor_real"].isna() & per_year.index.get_level_values("year").isin(list(defl)), "valor_real"
        ] = 0.0
        avg = per_year.groupby(level="cod_ibge7").mean()
        avg.columns = [f"{c}{suffix}" for c in avg.columns]
        return avg

    core_avg = layer_avg(sih[sih["group"].isin(core)], "")
    all_avg = layer_avg(sih, "_vet")
    out = core_avg.join(all_avg, how="outer")
    out["drsai_internacoes"] = out["internacoes"]
    out["drsai_valor_anual"] = out["valor_real"]
    out["drsai_dias_anual"] = out["dias"]
    out["drsai_taxa_10mil"] = out["internacoes"] / pop * 10_000
    out["drsai_custo_per_capita"] = out["valor_real"] / pop
    by_year = sih[sih["group"].isin(core)].groupby(["cod_ibge7", "year"])[["internacoes", "valor_real"]].sum()
    by_group = sih.groupby(["cod_ibge7", "group"])[["internacoes", "valor_real"]].sum() / len(years)
    info["by_year"] = by_year
    info["by_group"] = by_group
    return out, info


# --------------------------------------------------------------------------- tabela de indicadores


def indicator_table(inp: Inputs) -> tuple[pd.DataFrame, dict]:
    mun = inp.get("municipios")
    base = mun.set_index("cod_ibge7")[["nome", "slug", "uf", "regiao_imediata", "regiao_intermediaria"]].copy()
    pop = inp.get("populacao").set_index("cod_ibge7")["populacao"]
    base["populacao"] = pop
    ctx: dict = {"flags": {}}

    for name, cols in {
        "censo_agua": ["censo_agua_rede_pct"],
        "censo_esgoto": ["censo_esgoto_adequado_pct", "censo_com_esgoto_adequado_pessoas"],
        "censo_lixo": ["censo_lixo_coletado_pct"],
        "ana_atlas": ["ana_coleta_tratamento_pct", "ana_solucao_individual_pct", "ana_sem_atendimento_pct"],
    }.items():
        df = inp.get(name)
        if df is not None:
            base = base.join(df.set_index("cod_ibge7")[[c for c in cols if c in df.columns]])
    if "censo_agua_rede_pct" in base:
        base["censo_sem_agua_rede_pct"] = 100 - base["censo_agua_rede_pct"]
    if "censo_esgoto_adequado_pct" in base:
        base["censo_sem_esgoto_adequado_pct"] = 100 - base["censo_esgoto_adequado_pct"]
        moradores = inp.get("censo_esgoto").set_index("cod_ibge7").get("moradores_total_sidra")
        if moradores is not None:
            base["censo_sem_esgoto_pessoas"] = moradores - base["censo_com_esgoto_adequado_pessoas"]

    q = inp.get("censo_quilombola")
    if q is not None:
        base = base.join(q.set_index("cod_ibge7")[["pop_quilombola", "pop_quilombola_em_territorio"]])
        ctx["flags"]["pop_quilombola_lower_bound"] = "lower_bound" in (inp.meta("censo_quilombola") or {}).get(
            "status_reason", ""
        )
    r = inp.get("censo_raca")
    if r is not None:
        base = base.join(r.set_index("cod_ibge7")[["pop_cor_indigena"]])
    if "pop_quilombola" in base or "pop_cor_indigena" in base:
        pq = base.get("pop_quilombola", pd.Series(0, index=base.index)).fillna(0)
        pi = base.get("pop_cor_indigena", pd.Series(0, index=base.index)).fillna(0)
        base["pct_pop_quilombola_indigena"] = (pq + pi) / base["populacao"] * 100

    semi = inp.get("semiarido")
    base["semiarido"] = base.index.isin(semi["cod_ibge7"]) if semi is not None else None
    ctx["semiarido_available"] = semi is not None

    # SNIS: último ano disponível de cada indicador + séries
    snis = inp.get("snis")
    ctx["snis_series"] = {}
    if snis is not None:
        snis = snis.sort_values("year")
        ctx["snis_year_max"] = int(snis["year"].max())
        for col in SNIS_SERIES + ["snis_consumo_lhabdia"]:
            if col not in snis:
                continue
            valid = snis.dropna(subset=[col])
            last = valid.groupby("cod_ibge7").tail(1).set_index("cod_ibge7")
            base[col] = last[col]
            base[f"{col}__ano"] = last["year"]
        for col in SNIS_SERIES:
            if col in snis:
                ctx["snis_series"][col] = snis.pivot_table(index="cod_ibge7", columns="year", values=col)
        base["snis_sem_agua_pct"] = 100 - base["snis_agua_pct"]
        base["snis_sem_esgoto_pct"] = 100 - base["snis_esgoto_pct"]

    health, hinfo = health_tables(inp, pop)
    ctx["health"] = hinfo
    if health is not None:
        base = base.join(health)
    return base, ctx


# --------------------------------------------------------------------------- índice


def compute_index(tab: pd.DataFrame, available: set[str]) -> tuple[pd.DataFrame, dict]:
    cfg = config.load("pesos_indice")
    fallbacks = cfg.get("fallbacks", {})
    dims: dict[str, list[str]] = {}
    used_fallbacks = {}
    pct_cols = {}
    for dim, d in cfg["dimensions"].items():
        comps = []
        for c in d["components"]:
            ind = c["indicator"]
            if ind not in tab.columns or tab[ind].notna().sum() == 0:
                fb = fallbacks.get(ind)
                if fb and fb in tab.columns and tab[fb].notna().sum() > 0:
                    used_fallbacks[ind] = fb
                    ind = fb
                else:
                    continue
            hw = c["direction"] != "lower_is_worse"
            pct_cols[ind] = pidx.percentile_ranks(tab[ind].to_dict(), higher_is_worse=hw)
            comps.append(ind)
        dims[dim] = comps
    weights = {k: v["weight"] for k, v in cfg["dimensions"].items()}
    rows = {}
    for code in tab.index:
        comp = {ind: pct_cols[ind][code] for ind in pct_cols}
        ds = pidx.dimension_scores(comp, dims)
        score, coverage = pidx.weighted_index(ds, weights, cfg["min_dimensions_for_rank"])
        rows[code] = {
            "indice_prioridade": score,
            "indice_cobertura": coverage,
            **{f"dim_{k}": v for k, v in ds.items()},
            **{f"pct__{k}": v for k, v in comp.items()},
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    out["indice_rank"] = pd.Series(pidx.rank(out["indice_prioridade"].to_dict()))
    dims_available = [d for d, c in dims.items() if c]
    info = {
        "weights": weights,
        "dimensions": {
            k: {"label": v["label"], "weight": v["weight"], "components": dims[k]} for k, v in cfg["dimensions"].items()
        },
        "dims_available": dims_available,
        "dims_missing": [d for d in dims if not dims[d]],
        "fallbacks_used": used_fallbacks,
        "min_dimensions_for_rank": cfg["min_dimensions_for_rank"],
        "ranked": int(out["indice_prioridade"].notna().sum()),
    }
    return out, info


def sensitivity(tab_idx: pd.DataFrame, info: dict) -> dict:
    """Quanto o top N muda variando cada peso ±delta p.p. (os demais renormalizados)."""
    cfg = config.load("pesos_indice")["sensitivity"]
    delta, n = cfg["delta_points"] / 100, cfg["top_n"]
    base_w = info["weights"]
    dims = info["dims_available"]
    min_dims = info["min_dimensions_for_rank"]
    if info["ranked"] == 0:
        return {"status": "sem_ranking", "reason": "dimensões insuficientes para ranquear", "scenarios": []}

    def top(weights: dict) -> list[str]:
        scores = {}
        for code, row in tab_idx.iterrows():
            ds = {d: row.get(f"dim_{d}") for d in base_w}
            ds = {d: (None if v is None or (isinstance(v, float) and math.isnan(v)) else v) for d, v in ds.items()}
            s, _ = pidx.weighted_index(ds, weights, min_dims)
            scores[code] = s
        ranked = sorted((k for k, v in scores.items() if v is not None), key=lambda k: -scores[k])
        return ranked[:n]

    ref = top(base_w)
    scenarios = []
    for d in dims:
        for sign in (+1, -1):
            w = dict(base_w)
            w[d] = max(0.0, w[d] + sign * delta)
            others = [k for k in w if k != d]
            rest = sum(base_w[k] for k in others)
            target_rest = 1 - w[d]
            for k in others:
                w[k] = base_w[k] / rest * target_rest if rest > 0 else 0
            t = top(w)
            scenarios.append(
                {
                    "dimension": d,
                    "delta_pp": sign * cfg["delta_points"],
                    "overlap": len(set(t) & set(ref)),
                    "entered": [c for c in t if c not in ref],
                    "left": [c for c in ref if c not in t],
                }
            )
    overlaps = [s["overlap"] for s in scenarios]
    return {
        "status": "ok",
        "top_n": n,
        "reference_top": ref,
        "scenarios": scenarios,
        "min_overlap": min(overlaps),
        "mean_overlap": sum(overlaps) / len(overlaps),
    }


# --------------------------------------------------------------------------- comunidades


def communities(inp: Inputs) -> tuple[dict[str, list[dict]], gpd.GeoDataFrame | None]:
    tis = inp.get("terras_indigenas")
    malha = inp.get("malhas")
    if tis is None or malha is None or tis.empty:
        return {}, None
    m = malha.to_crs(5880)  # SIRGAS 2000 / Brazil Polyconic: áreas em m²
    t = tis.to_crs(5880).reset_index(drop=True)
    t["ti_id"] = t.index
    t["ti_area"] = t.geometry.area
    inter = gpd.overlay(
        t[["ti_id", "ti_area", "geometry"]], m[["cod_ibge7", "geometry"]], how="intersection", keep_geom_type=True
    )
    inter["a"] = inter.geometry.area
    inter = inter[inter["a"] > 1e4]  # ignora toques de borda (< 1 ha)
    by_mun: dict[str, list[dict]] = {}
    for _, r in inter.iterrows():
        ti = t.loc[r["ti_id"]]
        by_mun.setdefault(r["cod_ibge7"], []).append(
            {
                "nome": ti.get("nome"),
                "etnia": ti.get("etnia"),
                "fase": ti.get("fase"),
                "modalidade": ti.get("modalidade"),
                "area_ha_total": ti.get("area_ha"),
                "pct_da_ti_no_municipio": r["a"] / ti["ti_area"] * 100,
            }
        )
    keep = t[t["ti_id"].isin(inter["ti_id"])].to_crs(4326)
    keep = keep[[c for c in ["nome", "etnia", "fase", "modalidade", "area_ha", "geometry"] if c in keep.columns]]
    return by_mun, keep


def neighbors(inp: Inputs) -> dict[str, list[str]]:
    g = inp.get("malhas").to_crs(5880)
    g["geometry"] = g.geometry.buffer(50)
    j = gpd.sjoin(g[["cod_ibge7", "geometry"]], g[["cod_ibge7", "geometry"]], predicate="intersects")
    j = j[j["cod_ibge7_left"] != j["cod_ibge7_right"]]
    return j.groupby("cod_ibge7_left")["cod_ibge7_right"].apply(lambda s: sorted(set(s))).to_dict()


# --------------------------------------------------------------------------- estatísticas de comparação


def national_medians() -> dict[str, float]:
    """Medianas Brasil a partir de arquivos nacionais já em cache (espelhos nacionais). Pode ser vazio."""
    out: dict[str, float] = {}
    snis_path = config.RAW_DIR / "national" / "bd_snis_municipio_agua_esgoto.csv.gz"
    if snis_path.exists():
        from pipeline.sources.snis import INDICATORS

        cols = {c: n for c, n in INDICATORS.values()}
        df = pd.read_csv(snis_path, usecols=["ano", "id_municipio", *cols.keys()]).rename(columns=cols)
        y = int(df["ano"].max())
        last = df[df["ano"] == y]
        for n in cols.values():
            s = last[n].dropna()
            if n == "snis_perdas_pct":
                s = s[(s >= 0) & (s <= 100)]
            elif n.endswith("_pct"):
                s = s.clip(upper=100)
            if len(s):
                out[n] = float(s.median())
        out["_snis_year"] = y
    return out


# --------------------------------------------------------------------------- build principal


def thermo_for(code: str, ctx: dict) -> dict:
    out = {}
    for service, col in (("agua", "snis_agua_pct"), ("esgoto", "snis_esgoto_pct")):
        series = ctx["snis_series"].get(col)
        if series is None or code not in series.index:
            out[service] = thermometer.compute(service, {}).to_dict()
        else:
            row = series.loc[code]
            out[service] = thermometer.compute(
                service, {int(y): (None if pd.isna(v) else float(v)) for y, v in row.items()}
            ).to_dict()
    return out


def build_uf(uf: config.UF) -> None:
    inp = Inputs(uf)
    out_dir = config.PUBLIC_DIR / uf.slug
    tab, ctx = indicator_table(inp)
    status = inp.source_status()
    available = {k for k, v in status.items() if v["status"] in {"ok", "stale"}}
    idx, idx_info = compute_index(tab, available)
    tab = tab.join(idx)
    sens = sensitivity(idx, idx_info)
    nbrs = neighbors(inp)
    com_by_mun, tis_geo = communities(inp)
    br = national_medians()
    indicators_cfg = config.load("indicadores")["indicators"]
    calc_cfg = config.load("calculadora")
    hinfo = ctx.get("health", {})

    numeric = [
        c
        for c in tab.columns
        if c in indicators_cfg and pd.api.types.is_numeric_dtype(tab[c]) and not pd.api.types.is_bool_dtype(tab[c])
    ]
    stats = {
        c: {
            "median_uf": tab[c].median(),
            "min": tab[c].min(),
            "max": tab[c].max(),
            "n": int(tab[c].notna().sum()),
            "median_br": br.get(c),
        }
        for c in numeric
    }

    thermos = {code: thermo_for(code, ctx) for code in tab.index}
    sih_period = None
    if hinfo.get("years"):
        sih_period = f"média {hinfo['years'][0]}–{hinfo['years'][-1]}, em R$ de {hinfo['price_base']}"

    resumo_mun = []
    for code, row in tab.iterrows():
        ind = {c: row.get(c) for c in numeric}
        th = thermos[code]
        resumo_mun.append(
            {
                "cod": code,
                "nome": row["nome"],
                "slug": row["slug"],
                "ri": row["regiao_intermediaria"],
                "rim": row["regiao_imediata"],
                "semiarido": row["semiarido"],
                "ind": ind,
                "pct": {k.replace("pct__", ""): row[k] for k in tab.columns if k.startswith("pct__")},
                "dims": {k.replace("dim_", ""): row[k] for k in tab.columns if k.startswith("dim_")},
                "idx": row.get("indice_prioridade"),
                "rank": row.get("indice_rank"),
                "thermo": {
                    "agua": th["agua"]["status"],
                    "esgoto": th["esgoto"]["status"],
                    "agua_ano": th["agua"]["projected_year"],
                    "esgoto_ano": th["esgoto"]["projected_year"],
                },
            }
        )

    totals = {
        "populacao": int(tab["populacao"].sum()),
        "municipios": int(len(tab)),
        "pessoas_sem_esgoto_censo": tab["censo_sem_esgoto_pessoas"].sum(min_count=1)
        if "censo_sem_esgoto_pessoas" in tab
        else None,
        "drsai_valor_anual": tab["drsai_valor_anual"].sum(min_count=1) if "drsai_valor_anual" in tab else None,
        "drsai_internacoes": tab["drsai_internacoes"].sum(min_count=1) if "drsai_internacoes" in tab else None,
        "agua_atrasados": sum(1 for t in thermos.values() if t["agua"]["status"] == "atrasado"),
        "esgoto_atrasados": sum(1 for t in thermos.values() if t["esgoto"]["status"] == "atrasado"),
        "esgoto_no_ritmo": sum(1 for t in thermos.values() if t["esgoto"]["status"] in {"no_ritmo", "atingida"}),
        "esgoto_sem_dados": sum(1 for t in thermos.values() if t["esgoto"]["status"] == "sem_dados"),
        "semiarido": int(tab["semiarido"].sum()) if ctx.get("semiarido_available") else None,
        "pop_quilombola": tab["pop_quilombola"].sum(min_count=1) if "pop_quilombola" in tab else None,
        "terras_indigenas": int(len(tis_geo)) if tis_geo is not None else None,
    }
    if "snis_esgoto_pct" in tab and "snis_pop_atendida_esgoto" not in tab:
        pass

    generated = datetime.now(UTC).isoformat(timespec="seconds")
    resumo = {
        "uf": {"sigla": uf.sigla, "nome": uf.name, "code": uf.code, "slug": uf.slug, "region": uf.region},
        "generated_at": generated,
        "pipeline_version": config.PIPELINE_VERSION,
        "sources": status,
        "flags": ctx["flags"],
        "snis_year": ctx.get("snis_year_max"),
        "health": {"years": hinfo.get("years"), "price_base": hinfo.get("price_base"), "period_label": sih_period},
        "index": idx_info,
        "stats": stats,
        "totals": totals,
        "municipios": resumo_mun,
    }
    dump(resumo, out_dir / "resumo.json")
    dump(sens, out_dir / "indice_sensibilidade.json")

    # Fichas
    names = tab["nome"].to_dict()
    slugs = tab["slug"].to_dict()
    by_year = hinfo.get("by_year")
    by_group = hinfo.get("by_group")
    groups_cfg = config.load("cid_drsai")["groups"]
    for code, row in tab.iterrows():
        ind = {c: row.get(c) for c in numeric}
        years_of = {
            c: (None if pd.isna(row.get(f"{c}__ano")) else int(row.get(f"{c}__ano")))
            for c in SNIS_SERIES + ["snis_consumo_lhabdia"]
            if f"{c}__ano" in tab
        }
        series = {}
        for col, piv in ctx["snis_series"].items():
            if code in piv.index:
                s = piv.loc[code].dropna()
                series[col] = [[int(y), float(v)] for y, v in s.items()]
        div = {}
        for svc, (c_censo, c_snis) in {
            "agua": ("censo_agua_rede_pct", "snis_agua_pct"),
            "esgoto": ("censo_esgoto_adequado_pct", "snis_esgoto_pct"),
        }.items():
            a, b = ind.get(c_censo), ind.get(c_snis)
            if a is not None and b is not None and not (pd.isna(a) or pd.isna(b)):
                div[svc] = {"censo": a, "snis": b, "diff_pp": b - a, "flag": abs(b - a) > DIVERGENCE_PP}
        health = None
        baseline = Baseline(None, None, None, None)
        if "drsai_internacoes" in tab and not pd.isna(row.get("drsai_internacoes")):
            hy = []
            if by_year is not None and code in by_year.index.get_level_values(0):
                hy = [[int(y), int(r["internacoes"]), r["valor_real"]] for y, r in by_year.loc[code].iterrows()]
            hg = []
            if by_group is not None and code in by_group.index.get_level_values(0):
                for g, r in by_group.loc[code].iterrows():
                    hg.append(
                        {
                            "group": g,
                            "label": groups_cfg[g]["label"],
                            "layer": groups_cfg[g]["layer"],
                            "internacoes": r["internacoes"],
                            "valor": r["valor_real"],
                        }
                    )
            health = {
                "internacoes": row["drsai_internacoes"],
                "valor": row["drsai_valor_anual"],
                "dias": row["drsai_dias_anual"],
                "obitos": row.get("obitos"),
                "taxa_10mil": row["drsai_taxa_10mil"],
                "custo_per_capita": row["drsai_custo_per_capita"],
                "dias_6_17": row.get("dias_6_17"),
                "internacoes_menor5": row.get("internacoes_menor5"),
                "vetores": {
                    "internacoes": row.get("internacoes_vet"),
                    "valor": row.get("valor_real_vet"),
                    "dias": row.get("dias_vet"),
                    "dias_6_17": row.get("dias_6_17_vet"),
                },
                "by_year": hy,
                "by_group": hg,
                "period": sih_period,
            }
            baseline = Baseline(row["drsai_valor_anual"], row["drsai_dias_anual"], row.get("dias_6_17"), None)
        renda = ind.get("renda_domiciliar_pc")
        daily_income = renda / 30 if renda is not None and not pd.isna(renda) else None
        baseline_vet = None
        if health:
            baseline_vet = {
                "hospital_cost": row.get("valor_real_vet"),
                "hospital_days": row.get("dias_vet"),
                "school_days": row.get("dias_6_17_vet"),
                "daily_income": daily_income,
            }
        nb = [{"cod": c, "nome": names.get(c), "slug": slugs.get(c)} for c in nbrs.get(code, []) if c in names]
        th = thermos[code]
        extra = {
            "snis_year": years_of.get("snis_esgoto_pct") or years_of.get("snis_agua_pct"),
            "sih_period": sih_period,
        }
        ficha = {
            "cod": code,
            "nome": row["nome"],
            "slug": row["slug"],
            "uf": uf.sigla,
            "uf_nome": uf.name,
            "regiao_imediata": row["regiao_imediata"],
            "regiao_intermediaria": row["regiao_intermediaria"],
            "semiarido": row["semiarido"],
            "resumo": summary.municipal_summary(row["nome"], ind, th, extra),
            "ind": ind,
            "ind_ano": years_of,
            "series": series,
            "thermometer": th,
            "divergence": div,
            "health": health,
            "calculator": {
                "baseline": {
                    "hospital_cost": baseline.hospital_cost,
                    "hospital_days": baseline.hospital_days,
                    "school_days": baseline.school_days,
                    "daily_income": daily_income,
                    "deaths": None,
                    "productive_years_lost": None,
                },
                "baseline_vectors": baseline_vet,
                "defaults": {k: calc_cfg[k] for k in ("reduction_pct", "horizon_years", "discount_rate")},
            },
            "communities": {
                "pop_quilombola": ind.get("pop_quilombola"),
                "pop_quilombola_em_territorio": row.get("pop_quilombola_em_territorio"),
                "pop_quilombola_lower_bound": ctx["flags"].get("pop_quilombola_lower_bound", False),
                "pop_cor_indigena": ind.get("pop_cor_indigena"),
                "terras_indigenas": com_by_mun.get(code, []),
            },
            "index": {
                "score": row.get("indice_prioridade"),
                "rank": row.get("indice_rank"),
                "n_ranked": idx_info["ranked"],
                "coverage": row.get("indice_cobertura"),
                "dims": {d: row.get(f"dim_{d}") for d in idx_info["dimensions"]},
                "components": {k.replace("pct__", ""): row[k] for k in tab.columns if k.startswith("pct__")},
            },
            "suggestions": act.suggestions(ind, {"semiarido": row["semiarido"]}),
            "neighbors": nb,
            "generated_at": generated,
        }
        dump(ficha, out_dir / "municipios" / f"{row['slug']}.json")

    # Geodados
    malha = inp.get("malhas").merge(tab[["nome", "slug"]], left_on="cod_ibge7", right_index=True)
    (out_dir).mkdir(parents=True, exist_ok=True)
    malha.to_crs(4326).to_file(out_dir / "malha.geojson", driver="GeoJSON")
    if tis_geo is not None:
        tis_geo.to_file(out_dir / "terras_indigenas.geojson", driver="GeoJSON")

    write_downloads(uf, tab, ctx, out_dir, numeric)
    log.info("[%s] build ok: %d fichas, índice ranqueado: %d", uf.sigla, len(tab), idx_info["ranked"])


def write_downloads(uf: config.UF, tab: pd.DataFrame, ctx: dict, out_dir: Path, numeric: list[str]) -> None:
    d = out_dir / "dados"
    (d / "municipios").mkdir(parents=True, exist_ok=True)
    cols = (
        ["nome", "uf", "regiao_intermediaria", "regiao_imediata", "semiarido"]
        + numeric
        + ["indice_prioridade", "indice_rank"]
    )
    wide = tab[[c for c in cols if c in tab.columns]].copy()
    wide.index.name = "cod_ibge7"
    wide.to_csv(d / f"{uf.slug}_municipios.csv", encoding="utf-8")
    wide.reset_index().to_parquet(d / f"{uf.slug}_municipios.parquet", index=False)
    long = []
    for col, piv in ctx["snis_series"].items():
        m = piv.stack().rename("valor").reset_index()
        m["indicador"] = col
        long.append(m)
    if long:
        ser = pd.concat(long, ignore_index=True)[["cod_ibge7", "indicador", "year", "valor"]].rename(
            columns={"year": "ano"}
        )
        ser.to_csv(d / f"{uf.slug}_series_snis.csv", index=False)
        ser.to_parquet(d / f"{uf.slug}_series_snis.parquet", index=False)
    for code, r in wide.iterrows():
        r.to_frame("valor").to_csv(d / "municipios" / f"{tab.loc[code, 'slug']}.csv", encoding="utf-8")


def build_national_index(ufs: list[dict]) -> None:
    """Índice nacional mínimo: lista de UFs processadas + dicionário de dados (fonte: indicadores.yaml)."""
    out = config.PUBLIC_DIR
    processed = [u for u in ufs if (out / u["slug"] / "resumo.json").exists()]
    dump({"ufs": processed, "generated_at": datetime.now(UTC).isoformat(timespec="seconds")}, out / "index.json")
    ind = config.load("indicadores")["indicators"]
    dump(ind, out / "indicadores.json")
    rows = [
        {
            "id": k,
            "nome": v["label"],
            "unidade": v["unit"],
            "fonte": v["source"],
            "formula": v["formula"],
            "limitacoes": " | ".join(v["limitations"]),
        }
        for k, v in ind.items()
    ]
    pd.DataFrame(rows).to_csv(out / "dicionario_de_dados.csv", index=False)
    dump(config.load("calculadora"), out / "calculadora.json")
    dump(config.load("cid_drsai"), out / "cid_drsai.json")
    dump(config.load("pesos_indice"), out / "pesos_indice.json")

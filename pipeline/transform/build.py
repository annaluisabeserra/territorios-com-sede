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
SNIS_SERIES = [
    "snis_agua_pct",
    "snis_esgoto_pct",
    "snis_esgoto_tratado_pct",
    "snis_tratamento_coletado_pct",
    "snis_tratamento_pct",
    "snis_perdas_pct",
    "snis_coleta_esgoto_pct",
]
FRESH_YEARS = 2  # valor do SNIS mais antigo que ano_ref − 2 é tratado como desatualizado
DIVERGENCE_PP = 15.0
# Nome legível das etapas (quando a fonte está indisponível, o .meta.json não traz o nome)
SOURCE_NAMES = {
    "censo_agua": "IBGE — Censo 2022, abastecimento de água",
    "censo_esgoto": "IBGE — Censo 2022, esgotamento sanitário",
    "sih_drsai": "DATASUS — SIH/SUS, internações por DRSAI",
    "censo_quilombola": "IBGE — Censo 2022, pessoas quilombolas",
    "censo_raca": "IBGE — Censo 2022, cor ou raça",
    "terras_indigenas": "FUNAI — Terras indígenas",
    "censo_renda": "IBGE — Censo 2022, rendimento domiciliar per capita",
    "censo_indigenas": "IBGE — Censo 2022, pessoas indígenas",
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
        if name in {"malhas", "terras_indigenas", "ucs_uso_sustentavel"}:
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
                "name": src.get("name")
                or SOURCE_NAMES.get(name)
                or config.load("sources").get(name, {}).get("name", name),
                "url": src.get("url"),
                "url_kind": src.get("url_kind"),
                "reference_period": src.get("reference_period"),
                "fetched_at": src.get("fetched_at"),
                "license": src.get("license"),
                "notes": src.get("notes"),
            }
        return out


# --------------------------------------------------------------------------- saúde (SIH)


SMALL_CELL = 5  # contagens anuais médias < 5 de óbitos são suprimidas nas saídas públicas (LGPD)


def health_tables(inp: Inputs, pop: pd.Series) -> tuple[pd.DataFrame | None, dict]:
    """Médias anuais DRSAI por município (núcleo e com vetores), deflacionadas mês a mês pelo IPCA.

    Denominador único: os anos do período. Se algum mês não tiver deflator (IPCA ainda não publicado), o valor
    monetário daquele ano fica indisponível e o valor médio é calculado só se todos os anos tiverem deflator;
    caso contrário, `drsai_valor_anual` fica ausente (nunca uma média sobre menos anos escondida).
    """
    sih = inp.get("sih_drsai")
    ipca = inp.get("ipca")
    info: dict = {}
    if sih is None or sih.empty:
        return None, info
    years = sorted(int(y) for y in sih["year"].unique())
    from pipeline.sources.ipca import last_complete_year, monthly_deflator

    base_year = min(last_complete_year(ipca), max(years)) if ipca is not None else None
    defl = monthly_deflator(ipca, base_year) if base_year else {}
    sih = sih.copy()
    if "month" not in sih.columns:
        sih["month"] = 0
    sih["factor"] = [defl.get((int(y), int(m))) for y, m in zip(sih["year"], sih["month"], strict=True)]
    sih["valor_real"] = sih["valor_nominal"] * sih["factor"]
    years_missing_defl = sorted(
        {int(y) for y, f in zip(sih["year"], sih["factor"], strict=True) if f is None or pd.isna(f)}
    )
    info = {"years": years, "price_base": base_year, "years_without_deflator": years_missing_defl}
    core = core_groups()
    counts = ["internacoes", "dias", "obitos", "dias_6_17", "internacoes_menor5"]

    def layer_avg(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
        per_year = df.groupby(["cod_ibge7", "year"])[counts + ["valor_real"]].sum(min_count=1)
        full = pd.MultiIndex.from_product([pop.index, years], names=["cod_ibge7", "year"])
        per_year = per_year.reindex(full)
        # Arquivos existem para todos os anos: município sem AIH no ano tem zero de fato.
        per_year[counts] = per_year[counts].fillna(0)
        per_year["valor_real"] = per_year["valor_real"].fillna(0)
        avg = per_year.groupby(level="cod_ibge7").mean()
        if years_missing_defl:
            avg["valor_real"] = float("nan")
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
    for col in ("obitos", "obitos_vet"):
        out[col] = out[col].where(out[col] >= SMALL_CELL)  # suprimido: publicado como "menos de 5"
    by_year = (
        sih[sih["group"].isin(core)].groupby(["cod_ibge7", "year"])[["internacoes", "valor_real"]].sum(min_count=1)
    )
    if years_missing_defl:  # ano com algum mês sem deflator: valor anual indisponível (nunca soma parcial)
        miss = by_year.index.get_level_values("year").isin(years_missing_defl)
        by_year.loc[miss, "valor_real"] = float("nan")
    by_group = sih.groupby(["cod_ibge7", "group"])[["internacoes", "valor_real"]].sum() / len(years)
    if years_missing_defl:
        by_group["valor_real"] = float("nan")
    info["by_year"] = by_year
    info["by_group"] = by_group
    return out, info


def sim_table(inp: Inputs) -> tuple[pd.DataFrame | None, dict]:
    """Óbitos por DRSAI (núcleo conservador, causa básica): média anual, com supressão de contagens pequenas.

    Também devolve, por município, a distribuição média anual de idades, usada na camada "vidas" da conta de
    impacto. Município com média abaixo de SMALL_CELL fica sem valor e sem distribuição (ADR-011).
    """
    sim = inp.get("sim_drsai")
    if sim is None or sim.empty:
        return None, {}
    from pipeline.transform.cid import core_groups

    years = sorted(int(y) for y in sim["year"].unique())
    core = sim[sim["group"].isin(core_groups())]
    avg = core.groupby("cod_ibge7")["obitos"].sum() / len(years)
    small = avg < SMALL_CELL
    out = pd.DataFrame({"obitos_drsai_anual": avg.where(~small)})
    ages = (
        core[core["cod_ibge7"].isin(avg.index[~small])]
        .groupby(["cod_ibge7", "age"], dropna=False)["obitos"]
        .sum()
        .div(len(years))
    )
    info = {
        "years": years,
        "ages": {
            c: [(None if pd.isna(a) else float(a), float(n)) for (_, a), n in g.items()]
            for c, g in ages.groupby(level=0)
        },
        "suppressed": int(small.sum()),
    }
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
        "censo_esgoto": ["censo_esgoto_adequado_pct", "censo_com_esgoto_adequado_pessoas", "censo_esgoto_rede_pct"],
        "censo_lixo": ["censo_lixo_coletado_pct"],
        "ana_atlas": ["ana_coleta_tratamento_pct", "ana_solucao_individual_pct", "ana_sem_atendimento_pct"],
        "censo_renda": ["renda_domiciliar_pc"],
        "censo_indigenas": ["pop_indigena"],
        "sisagua": ["sisagua_pct_fora_padrao", "sisagua_ecoli_pct_fora", "sisagua_amostras"],
        "s2id": ["decretos_seca_5a", "decretos_chuva_5a"],
        "monitor_secas": ["seca_meses_12m", "seca_classe_max_12m"],
        "censo_escolar": [
            "escolas_publicas",
            "escolas_sem_agua_potavel_pct",
            "escolas_sem_banheiro_pct",
            "escolas_sem_esgoto_pct",
            "escolas_sem_agua_potavel_matriculas",
            "escolas_sem_banheiro_matriculas",
            "escolas_sem_esgoto_matriculas",
        ],
        "siconfi": ["despesa_saneamento", "despesa_saneamento_ano"],
    }.items():
        df = inp.get(name)
        if df is not None:
            base = base.join(df.set_index("cod_ibge7")[[c for c in cols if c in df.columns]])
    if "despesa_saneamento" in base:
        base["despesa_saneamento_pc"] = base["despesa_saneamento"] / base["populacao"]
        ctx["siconfi_ano"] = (
            int(base["despesa_saneamento_ano"].max()) if base["despesa_saneamento_ano"].notna().any() else None
        )
    sim_t, ctx["sim"] = sim_table(inp)
    if sim_t is not None:
        base = base.join(sim_t)
        base["obitos_drsai_100mil"] = base["obitos_drsai_anual"] / base["populacao"] * 100_000
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
    if "pop_quilombola" in base and "pop_cor_indigena" in base:
        # Limite inferior com as partes conhecidas (revisão M4: a presença indígena não pode sumir porque a
        # contagem quilombola está sob sigilo). Desconhecido só se as duas partes forem desconhecidas.
        both_null = base["pop_quilombola"].isna() & base["pop_cor_indigena"].isna()
        known = base["pop_quilombola"].fillna(0) + base["pop_cor_indigena"].fillna(0)
        base["pct_pop_quilombola_indigena"] = (known / base["populacao"] * 100).where(~both_null)
    if q is not None:
        base = base.join(
            q.set_index("cod_ibge7")[["pct_cells_suppressed"]].rename(
                columns={"pct_cells_suppressed": "quilombola_pct_celulas_sigilo"}
            )
        )

    semi = inp.get("semiarido")
    base["semiarido"] = base.index.isin(semi["cod_ibge7"]) if semi is not None else None
    ctx["semiarido_available"] = semi is not None

    # SNIS: último ano de cada indicador, só se recente (≥ ano_ref − FRESH_YEARS). Valor mais antigo vai para
    # `{col}__antigo` (exibido como "último dado: AAAA") e não entra no índice, no "Agir" nem nas medianas.
    snis = merge_snis_sinisa(inp.get("snis"), inp.get("sinisa"))
    ctx["snis_series"] = {}
    ctx["snis_ref_by_col"] = {}
    if snis is not None:
        snis = snis.sort_values("year")
        ref = int(snis["year"].max())
        ctx["snis_year_max"] = ref
        ctx["sinisa_years"] = sorted({int(y) for y in snis.loc[snis["_fonte"] == "sinisa", "year"]})
        for col in SNIS_SERIES + ["snis_consumo_lhabdia"]:
            if col not in snis:
                continue
            valid = snis.dropna(subset=[col])
            if valid.empty:
                continue
            # Ano de referência por indicador: se o SINISA não trouxer um indicador, ele não "envelhece"
            # artificialmente os dados do SNIS daquele indicador.
            ref = int(valid["year"].max())
            ctx["snis_ref_by_col"][col] = ref
            last = valid.groupby("cod_ibge7").tail(1).set_index("cod_ibge7")
            fresh = last["year"] >= ref - FRESH_YEARS
            base[col] = last[col].where(fresh)
            base[f"{col}__ano"] = last["year"].where(fresh)
            base[f"{col}__antigo"] = last[col].where(~fresh)
            base[f"{col}__antigo_ano"] = last["year"].where(~fresh)
        # Prestador de esgoto declarado em algum ano recente? (ausência ≠ zero, mas é informação)
        ref = ctx["snis_ref_by_col"].get("snis_esgoto_pct", ctx["snis_year_max"])
        recent = snis[snis["year"] >= ref - FRESH_YEARS]
        has_esg = recent.dropna(subset=["snis_esgoto_pct"]).groupby("cod_ibge7").size()
        base["snis_esgoto_sem_declaracao"] = ~base.index.isin(has_esg.index)
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


def merge_snis_sinisa(snis: pd.DataFrame | None, sinisa: pd.DataFrame | None) -> pd.DataFrame | None:
    """Série única: SNIS até o último ano dele; SINISA só para anos posteriores (nunca sobrescreve o SNIS)."""
    if snis is None and sinisa is None:
        return None
    parts = []
    last_snis = None
    if snis is not None:
        parts.append(snis.assign(_fonte="snis"))
        last_snis = int(snis["year"].max())
    if sinisa is not None and len(sinisa):
        s = sinisa if last_snis is None else sinisa[sinisa["year"] > last_snis]
        parts.append(s.assign(_fonte="sinisa"))
    return pd.concat(parts, ignore_index=True)


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
        score, coverage = pidx.weighted_index(
            ds, weights, cfg["min_dimensions_for_rank"], tuple(cfg.get("required_dimensions", []))
        )
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
        "required_dimensions": cfg.get("required_dimensions", []),
        "ranked": int(out["indice_prioridade"].notna().sum()),
    }
    return out, info


def sensitivity(tab_idx: pd.DataFrame, info: dict) -> dict:
    """Quanto o top N muda variando cada peso ±delta p.p.

    Revisão M3: só as dimensões disponíveis na UF entram (as ausentes não absorvem peso), o conjunto de
    municípios elegíveis é fixo (definido com os pesos padrão) e empates são desempatados pelo código.
    """
    cfg = config.load("pesos_indice")["sensitivity"]
    delta, n = cfg["delta_points"] / 100, cfg["top_n"]
    dims = info["dims_available"]
    if info["ranked"] == 0:
        return {"status": "sem_ranking", "reason": "dimensões insuficientes para ranquear", "scenarios": []}
    eligible = [c for c in tab_idx.index if not pd.isna(tab_idx.loc[c, "indice_prioridade"])]
    base_total = sum(info["weights"][d] for d in dims)
    base_w = {d: info["weights"][d] / base_total for d in dims}

    def top(weights: dict) -> list[str]:
        scores = {}
        for code in eligible:
            num = den = 0.0
            for d in dims:
                v = tab_idx.loc[code, f"dim_{d}"]
                if not pd.isna(v):
                    num += v * weights[d]
                    den += weights[d]
            scores[code] = num / den if den > 0 else 0.0
        return sorted(scores, key=lambda k: (-scores[k], k))[:n]

    ref = top(base_w)
    scenarios = []
    for d in dims:
        for sign in (+1, -1):
            w = dict(base_w)
            w[d] = min(1.0, max(0.0, base_w[d] + sign * delta))
            rest = 1 - base_w[d]
            for k in dims:
                if k != d:
                    w[k] = base_w[k] / rest * (1 - w[d]) if rest > 0 else 0.0
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
    # Ignora toques de borda produzidos por malhas simplificadas diferentes: a interseção precisa ter pelo menos
    # 1% da área da TI ou 0,5% da área do município.
    m_area = m.set_index("cod_ibge7").geometry.area
    inter = inter[(inter["a"] >= 0.01 * inter["ti_area"]) | (inter["a"] >= 0.005 * inter["cod_ibge7"].map(m_area))]
    by_mun: dict[str, list[dict]] = {}
    for _, r in inter.iterrows():
        ti = t.loc[r["ti_id"]]
        by_mun.setdefault(r["cod_ibge7"], []).append(
            {
                "codigo_funai": ti.get("codigo_funai"),
                "ufs": ti.get("ufs"),
                "data_ref": ti.get("data_ref"),
                "nome": ti.get("nome"),
                "etnia": ti.get("etnia"),
                "fase": ti.get("fase"),
                "modalidade": ti.get("modalidade"),
                "area_ha_total": ti.get("area_ha"),
                "pct_da_ti_no_municipio": r["a"] / ti["ti_area"] * 100,
            }
        )
    keep = t[t["ti_id"].isin(inter["ti_id"])].to_crs(4326)
    cols = ["codigo_funai", "nome", "etnia", "fase", "modalidade", "area_ha", "ufs", "data_ref", "geometry"]
    keep = keep[[c for c in cols if c in keep.columns]]
    return by_mun, keep


def ucs_by_municipality(inp: Inputs) -> tuple[dict[str, list[dict]], gpd.GeoDataFrame | None]:
    u = inp.get("ucs_uso_sustentavel")
    malha = inp.get("malhas")
    if u is None or malha is None or u.empty:
        return {}, None
    m = malha.to_crs(5880)
    t = u.to_crs(5880).reset_index(drop=True)
    t["uc_id"] = t.index
    t["uc_area"] = t.geometry.area
    inter = gpd.overlay(
        t[["uc_id", "uc_area", "geometry"]], m[["cod_ibge7", "geometry"]], how="intersection", keep_geom_type=True
    )
    inter["a"] = inter.geometry.area
    # UCs (inclusive marinhas, quase toda área no mar): basta 1 km² de interseção com o município (revisão M6)
    inter = inter[(inter["a"] >= 1e6) | (inter["a"] >= 0.01 * inter["uc_area"])]
    out: dict[str, list[dict]] = {}
    for _, r in inter.iterrows():
        uc = t.loc[r["uc_id"]]
        out.setdefault(r["cod_ibge7"], []).append(
            {
                "nome": uc["nome"],
                "categoria": uc["categoria"],
                "esfera": uc["esfera"],
                "ano_criacao": uc["ano_criacao"],
                "id_cnuc": uc["id_cnuc"],
            }
        )
    keep = t[t["uc_id"].isin(inter["uc_id"])].to_crs(4326)[
        ["id_cnuc", "nome", "categoria", "esfera", "ano_criacao", "geometry"]
    ]
    return out, keep


COMMUNITY_COLS = [
    "pop_quilombola",
    "pop_quilombola_em_territorio",
    "pop_cor_indigena",
    "pop_indigena",
    "pct_pop_quilombola_indigena",
    "quilombola_pct_celulas_sigilo",
]


def apply_withdrawals(tab: pd.DataFrame, tis_mun: dict, tis_geo, ucs_mun: dict, ucs_geo, cfg: dict):
    """Aplica os pedidos de retirada (retiradas.yaml) a todas as saídas. Devolve as estruturas filtradas."""
    ti_out = {str(c) for c in cfg.get("terras_indigenas") or []}
    uc_out = {str(c) for c in cfg.get("unidades_conservacao") or []}
    mun_out = {str(c) for c in cfg.get("contagens_por_municipio") or []}
    if ti_out:
        tis_mun = {k: [t for t in v if str(t.get("codigo_funai")) not in ti_out] for k, v in tis_mun.items()}
        if tis_geo is not None and "codigo_funai" in tis_geo:
            tis_geo = tis_geo[~tis_geo["codigo_funai"].astype(str).isin(ti_out)]
    if uc_out:
        ucs_mun = {k: [u for u in v if str(u.get("id_cnuc")) not in uc_out] for k, v in ucs_mun.items()}
        if ucs_geo is not None:
            ucs_geo = ucs_geo[~ucs_geo["id_cnuc"].astype(str).isin(uc_out)]
    if mun_out:
        idx = tab.index.isin(mun_out)
        for c in COMMUNITY_COLS:
            if c in tab:
                tab.loc[idx, c] = float("nan")
        for c in mun_out:
            tis_mun.pop(c, None)
            ucs_mun.pop(c, None)
    return tab, tis_mun, tis_geo, ucs_mun, ucs_geo, mun_out


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
    # Esgoto: coleta COM tratamento (IN056 × IN016), porque a meta do Marco Legal exige as duas coisas.
    for service, col in (("agua", "snis_agua_pct"), ("esgoto", "snis_esgoto_tratado_pct")):
        ref = ctx.get("snis_ref_by_col", {}).get(col, ctx.get("snis_year_max"))
        series = ctx["snis_series"].get(col)
        if series is None or code not in series.index:
            out[service] = thermometer.compute(service, {}, ref).to_dict()
        else:
            row = series.loc[code]
            out[service] = thermometer.compute(
                service, {int(y): (None if pd.isna(v) else float(v)) for y, v in row.items()}, ref
            ).to_dict()
        mark_series_break(out[service], ctx.get("sinisa_years") or [])
    return out


def mark_series_break(th: dict, sinisa_years: list[int]) -> None:
    """Tendência que mistura anos do SNIS e do SINISA: projeção incerta, com o motivo (ADR-012)."""
    years = th.get("years") or []
    if not sinisa_years or th.get("status") in ("sem_dados", "atingida"):
        return
    first = min(sinisa_years)
    if any(y < first for y in years) and any(y >= first for y in years):
        th["uncertain"] = True
        note = f"a tendência junta anos do SNIS e do SINISA (desde {first}), que mudou parte da metodologia"
        th["reason"] = f"{th['reason']}; {note}" if th.get("reason") else note


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
    ucs_mun, ucs_geo = ucs_by_municipality(inp)
    sdw_cfg = config.load("atuacao_sdw")
    sdw_by_mun: dict[str, list[dict]] = {}
    for loc in sdw_cfg.get("locais") or []:
        sdw_by_mun.setdefault(str(loc["municipio"]), []).append(
            {
                "localidade": loc.get("localidade"),
                "papel": loc.get("papel"),
                "descricao": loc.get("descricao"),
                "site": sdw_cfg.get("site"),
                "contato": sdw_cfg.get("contato"),
            }
        )
    tab, com_by_mun, tis_geo, ucs_mun, ucs_geo, withdrawn = apply_withdrawals(
        tab, com_by_mun, tis_geo, ucs_mun, ucs_geo, config.load("retiradas")
    )
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
            "N": int(len(tab)),
            "median_br": br.get(c),
        }
        for c in numeric
    }

    thermos = {code: thermo_for(code, ctx) for code in tab.index}

    # Conta de impacto (ADR-013): água perdida em R$ do mesmo ano-base do SIH (ou do último ano completo do IPCA)
    from pipeline.sources.ipca import annual_deflator, last_complete_year
    from pipeline.transform import impact

    imp_cfg = config.load("impacto")
    ipca = inp.get("ipca")
    imp_base = hinfo.get("price_base") or (last_complete_year(ipca) if ipca is not None else None)
    water = pd.DataFrame()
    if ipca is not None and imp_base:
        water = impact.water_losses(
            inp.get("snis"), annual_deflator(ipca, imp_base), imp_cfg["camadas"]["agua_perdida"]["outlier_mult"]
        )
    water = water.reindex(water.index.intersection(tab.index))
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
                "sdw": code in sdw_by_mun,
                "esgoto_sem_declaracao": bool(row.get("snis_esgoto_sem_declaracao")),
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
        # "Fora das estatísticas" = sem nenhum dado recente de esgoto tratado (não confundir com série curta)
        "esgoto_sem_dado_recente": sum(
            1
            for t in thermos.values()
            if t["esgoto"]["status"] == "sem_dados"
            and (t["esgoto"]["reason"].startswith("último") or t["esgoto"]["reason"] == "sem dado no SNIS")
        ),
        "semiarido": int(tab["semiarido"].sum()) if ctx.get("semiarido_available") else None,
        "pop_quilombola": tab["pop_quilombola"].sum(min_count=1) if "pop_quilombola" in tab else None,
        "terras_indigenas": int(len(tis_geo)) if tis_geo is not None else None,
        "ucs_uso_sustentavel": int(len(ucs_geo)) if ucs_geo is not None else None,
        "agua_perdida_m3": float(water["perda_m3"].sum()) if len(water) else None,
        "agua_perdida_baixo": float(water["valor_baixo"].sum(min_count=1)) if len(water) else None,
        # Município sem cenário alto entra pelo baixo (conservador)
        "agua_perdida_alto": float(water["valor_alto"].fillna(water["valor_baixo"]).sum(min_count=1))
        if len(water)
        else None,
        "agua_perdida_municipios": int(water["valor_baixo"].notna().sum()) if len(water) else 0,
        "agua_perdida_ano": int(water["year"].max()) if len(water) else None,
        "impacto_price_base": imp_base,
    }
    if "snis_esgoto_pct" in tab and "snis_pop_atendida_esgoto" not in tab:
        pass

    generated = datetime.now(UTC).isoformat(timespec="seconds")
    resumo = {
        "uf": {
            "sigla": uf.sigla,
            "nome": uf.name,
            "code": uf.code,
            "slug": uf.slug,
            "region": uf.region,
            "preposicao": uf.preposicao,
        },
        "generated_at": generated,
        "pipeline_version": config.PIPELINE_VERSION,
        "sources": status,
        "flags": ctx["flags"],
        "snis_year": ctx.get("snis_year_max"),
        "sinisa_years": ctx.get("sinisa_years", []),
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
            # IN056 mede coleta por rede: compara com a categoria "rede geral ou pluvial" do Censo, não com
            # "esgoto adequado" (que inclui fossa séptica e geraria divergência estrutural).
            "esgoto": ("censo_esgoto_rede_pct", "snis_esgoto_pct"),
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
            "years": years_of,
            "sih_period": sih_period,
            "esgoto_sem_declaracao": bool(row.get("snis_esgoto_sem_declaracao")),
        }
        ficha = {
            "cod": code,
            "nome": row["nome"],
            "slug": row["slug"],
            "uf": uf.sigla,
            "uf_nome": uf.name,
            "uf_preposicao": uf.preposicao,
            "regiao_imediata": row["regiao_imediata"],
            "regiao_intermediaria": row["regiao_intermediaria"],
            "semiarido": row["semiarido"],
            "resumo": summary.municipal_summary(row["nome"], ind, th, extra),
            "ind": ind,
            "ind_ano": years_of,
            "ind_antigo": {
                c: [row[f"{c}__antigo"], int(row[f"{c}__antigo_ano"])]
                for c in SNIS_SERIES + ["snis_consumo_lhabdia"]
                if f"{c}__antigo" in tab and not pd.isna(row.get(f"{c}__antigo"))
            },
            "esgoto_sem_declaracao": bool(row.get("snis_esgoto_sem_declaracao")),
            "series": series,
            "thermometer": th,
            "divergence": div,
            "health": health,
            "impacto": impact.account(
                baseline.hospital_cost,
                baseline.hospital_days,
                baseline.school_days,
                daily_income,
                water.loc[code].to_dict() if code in water.index else None,
                ind.get("populacao"),
                imp_cfg,
                sih_period,
                imp_base,
                impact.lives_value(
                    ctx.get("sim", {}).get("ages", {}).get(code, []),
                    daily_income,
                    float(calc_cfg["discount_rate"]),
                    int(imp_cfg["camadas"]["vidas"]["idade_inicio"]),
                    int(imp_cfg["camadas"]["vidas"]["idade_fim"]),
                )
                if code in ctx.get("sim", {}).get("ages", {})
                else None,
                f"média {ctx['sim']['years'][0]}–{ctx['sim']['years'][-1]}"
                if ctx.get("sim", {}).get("years")
                else None,
            ),
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
                "pop_indigena": ind.get("pop_indigena"),
                "retirado_a_pedido": code in withdrawn,
                "quilombola_pct_celulas_sigilo": row.get("quilombola_pct_celulas_sigilo"),
                "fonte_censo": "IBGE, Censo Demográfico 2022 (data de referência 01/08/2022)",
                "fonte_tis": "FUNAI, terras indígenas (polígonos oficiais); limites simplificados para a web",
                "nota_territorio": "“Em território quilombola” se refere a territórios delimitados pelo IBGE no Censo; "
                "zero ou vazio não significa ausência de território reivindicado.",
                "terras_indigenas": com_by_mun.get(code, []),
                "ucs_uso_sustentavel": ucs_mun.get(code, []),
            },
            "index": {
                "score": row.get("indice_prioridade"),
                "rank": row.get("indice_rank"),
                "n_ranked": idx_info["ranked"],
                "coverage": row.get("indice_cobertura"),
                "dims": {d: row.get(f"dim_{d}") for d in idx_info["dimensions"]},
                "components": {k.replace("pct__", ""): row[k] for k in tab.columns if k.startswith("pct__")},
            },
            "atuacao_sdw": sdw_by_mun.get(code, []),
            "suggestions": act.suggestions(
                ind,
                {"semiarido": row["semiarido"], "esgoto_sem_declaracao": bool(row.get("snis_esgoto_sem_declaracao"))},
            ),
            "neighbors": nb,
            "generated_at": generated,
        }
        dump(ficha, out_dir / "municipios" / f"{row['slug']}.json")

    # Geodados
    malha = inp.get("malhas").merge(tab[["nome", "slug"]], left_on="cod_ibge7", right_index=True)
    (out_dir).mkdir(parents=True, exist_ok=True)
    malha.to_crs(4326).to_file(out_dir / "malha.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    if tis_geo is not None:
        tis_geo.to_file(out_dir / "terras_indigenas.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    if ucs_geo is not None:
        ucs_geo.to_file(out_dir / "ucs_uso_sustentavel.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

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
    # Todas as UFs ativas com dados gerados, não só as da execução atual (rodar `--uf CE` não pode tirar a BA do site).
    from dataclasses import asdict

    processed = [asdict(u) for u in config.ufs() if (out / u.slug / "resumo.json").exists()]
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

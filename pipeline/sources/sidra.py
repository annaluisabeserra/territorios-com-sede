"""Cliente da API de agregados do IBGE (SIDRA v3) com descoberta por catálogo.

Os números de tabela do Censo 2022 citados em fontes secundárias divergem. Em vez de confiar num número,
o pipeline percorre o catálogo oficial, filtra os agregados do Censo Demográfico pelo nome, confere nos
metadados que existe o período 2022, o nível município (N6) e a variável/classificação esperadas, e só então
consulta os valores. Se nada casar, a fonte fica indisponível com o motivo (nunca um número chutado).
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, spec
from pipeline.sources.http import SourceURL, fetch
from pipeline.sources.meta import SourceMeta

API = "https://servicodados.ibge.gov.br/api/v3/agregados"
CENSUS_YEAR = "2022"
MISSING_TOKENS = {"-", "X", "..", "...", "", None}


def norm(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()


def _get_json(url: str, cache_name: str, max_age_days: float = 30) -> tuple[object, object]:
    f = fetch([SourceURL(url)], cache_name, subdir="sidra", max_age_days=max_age_days, retries=2, timeout=90)
    return json.loads(f.path.read_text(encoding="utf-8")), f


@dataclass
class TableChoice:
    table: int
    name: str
    variable: int
    variable_name: str
    classification: int | None
    categories: dict[int, str]


def parse_value(v) -> float | None:
    if v in MISSING_TOKENS:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def census_candidates(catalog: list[dict], keywords: list[str]) -> list[dict]:
    out = []
    for pesquisa in catalog:
        if "censo demografico" not in norm(pesquisa.get("nome", "")):
            continue
        for ag in pesquisa.get("agregados", []):
            name = norm(ag.get("nome", ""))
            if all(norm(k) in name for k in keywords):
                out.append({"id": int(ag["id"]), "nome": ag["nome"]})
    return out


def choose_table(
    metas: list[dict], variable_keywords: list[str], classification_keywords: list[str] | None
) -> TableChoice | None:
    """Escolhe, entre metadados candidatos, a tabela mais simples que atende aos requisitos."""
    ranked = []
    for m in metas:
        per = m.get("periodicidade", {})
        if not (int(per.get("inicio", 0)) <= int(CENSUS_YEAR) <= int(per.get("fim", 0))):
            continue
        levels = m.get("nivelTerritorial", {}).get("Administrativo", [])
        if "N6" not in levels:
            continue
        var = next(
            (v for v in m.get("variaveis", []) if all(norm(k) in norm(v["nome"]) for k in variable_keywords)),
            None,
        )
        if var is None or norm(var.get("unidade", "")) not in {"pessoas", "habitantes", "moradores"}:
            continue
        cls = None
        if classification_keywords:
            cls = next(
                (
                    c
                    for c in m.get("classificacoes", [])
                    if all(norm(k) in norm(c["nome"]) for k in classification_keywords)
                ),
                None,
            )
            if cls is None:
                continue
        n_cls = len(m.get("classificacoes", []))
        ranked.append((n_cls, int(m["id"]), m, var, cls))
    if not ranked:
        return None
    ranked.sort(key=lambda r: (r[0], r[1]))
    _, tid, m, var, cls = ranked[0]
    return TableChoice(
        table=tid,
        name=m["nome"],
        variable=int(var["id"]),
        variable_name=var["nome"],
        classification=int(cls["id"]) if cls else None,
        categories={int(c["id"]): c["nome"] for c in (cls or {}).get("categorias", [])},
    )


def parse_values(payload: list[dict]) -> pd.DataFrame:
    """Converte a resposta de /periodos/{p}/variaveis/{v} em linhas (cod_ibge7, categoria, valor)."""
    rows = []
    for var in payload:
        for res in var.get("resultados", []):
            cats = {}
            for c in res.get("classificacoes", []):
                cats.update(c.get("categoria", {}))
            cat_name = next(iter(cats.values()), "Total") if cats else "Total"
            cat_id = int(next(iter(cats.keys()))) if cats else None
            for s in res.get("series", []):
                rows.append(
                    {
                        "cod_ibge7": str(s["localidade"]["id"]),
                        "category_id": cat_id,
                        "category": cat_name,
                        "value": parse_value(s.get("serie", {}).get(CENSUS_YEAR)),
                    }
                )
    return pd.DataFrame(rows, columns=["cod_ibge7", "category_id", "category", "value"])


def _discover(source_id: str) -> TableChoice:
    cfg = spec(source_id)["sidra"]
    catalog, _ = _get_json(API, "catalogo_agregados.json", max_age_days=30)
    cands = census_candidates(catalog, cfg["keywords"])
    hint = cfg.get("table_hint")
    if hint and all(c["id"] != hint for c in cands):
        cands.insert(0, {"id": int(hint), "nome": "(dica do sources.yaml)"})
    metas = []
    for c in cands[:25]:
        try:
            m, _ = _get_json(f"{API}/{c['id']}/metadados", f"meta_{c['id']}.json", max_age_days=90)
            metas.append(m)
        except Exception:  # noqa: BLE001
            continue
    choice = choose_table(metas, cfg["variable_keywords"], cfg.get("classification_keywords"))
    if choice is None:
        raise SourceUnavailable(
            f"{source_id}: nenhuma tabela do Censo 2022 no catálogo SIDRA casou com {cfg} "
            f"({len(cands)} candidatas avaliadas)"
        )
    return choice


def _values(choice: TableChoice, uf: UF, all_categories: bool) -> tuple[pd.DataFrame, object, str]:
    url = f"{API}/{choice.table}/periodos/{CENSUS_YEAR}/variaveis/{choice.variable}?localidades=N6[N3[{uf.code}]]"
    if choice.classification is not None and all_categories:
        url += f"&classificacao={choice.classification}[all]"
    payload, f = _get_json(url, f"valores_{choice.table}_{choice.variable}_{uf.sigla}.json", max_age_days=60)
    return parse_values(payload), f, url


def _meta(source_id: str, choice: TableChoice, f, url: str) -> SourceMeta:
    s = spec(source_id)
    return SourceMeta(
        source_id=source_id,
        name=s["name"],
        url=url,
        url_kind="official",
        reference_period="2022 (data de referência 01/08/2022)",
        fetched_at=f.fetched_at,
        sha256=f.sha256,
        license=s.get("license", ""),
        notes=f"SIDRA tabela {choice.table} ({choice.name}); variável {choice.variable} ({choice.variable_name})",
    )


def total_from_catalog(source_id: str, uf: UF, value_name: str) -> SourceResult:
    choice = _discover(source_id)
    df, f, url = _values(choice, uf, all_categories=False)
    df = df.groupby("cod_ibge7", as_index=False)["value"].first().rename(columns={"value": value_name})
    return SourceResult(df, _meta(source_id, choice, f, url))


def share_from_catalog(source_id: str, uf: UF, pct_name: str, absolute_name: str | None = None) -> SourceResult:
    cfg = spec(source_id)["sidra"]
    choice = _discover(source_id)
    df, f, url = _values(choice, uf, all_categories=True)
    if df.empty:
        raise SourceUnavailable(f"{source_id}: resposta vazia de {url}")
    numer_keys = [norm(k) for k in cfg["numerator"]]
    df["is_total"] = df["category"].map(lambda c: norm(c) == "total")
    df["is_numer"] = df["category"].map(lambda c: any(k in norm(c) for k in numer_keys))
    total = df[df["is_total"]].groupby("cod_ibge7")["value"].sum(min_count=1)
    numer = df[df["is_numer"] & ~df["is_total"]].groupby("cod_ibge7")["value"].sum(min_count=1)
    out = pd.DataFrame({"total": total, "numer": numer}).reset_index()
    # Consistência: numerador ≤ total; soma das categorias-folha ≈ total (detecta subtotais misturados).
    if (out["numer"] > out["total"] * 1.0001).any():
        raise SourceUnavailable(f"{source_id}: numerador maior que o total (categorias hierárquicas?) em {url}")
    leaves = df[~df["is_total"]].groupby("cod_ibge7")["value"].sum(min_count=1)
    ratio = (leaves / total).dropna()
    if len(ratio) and (ratio > 1.02).mean() > 0.5:
        raise SourceUnavailable(f"{source_id}: soma das categorias excede o total (subtotais na tabela {choice.table})")
    suppressed = df[~df["is_total"] & df["value"].isna()].groupby("cod_ibge7").size()
    out[pct_name] = out["numer"] / out["total"] * 100
    cols = ["cod_ibge7", pct_name]
    for extra_name, keys in (cfg.get("extra_numerators") or {}).items():
        nk = [norm(k) for k in keys]
        sel = df[~df["is_total"] & df["category"].map(lambda c, nk=nk: any(k in norm(c) for k in nk))]
        en = sel.groupby("cod_ibge7")["value"].sum(min_count=1)
        out[extra_name] = out["cod_ibge7"].map(en) / out["total"] * 100
        cols.append(extra_name)
    out["categorias_sob_sigilo"] = out["cod_ibge7"].map(suppressed).fillna(0).astype(int)
    cols.append("categorias_sob_sigilo")
    if absolute_name:
        out[absolute_name] = out["numer"]
        cols.append(absolute_name)
    out["moradores_total_sidra"] = out["total"]
    meta = _meta(source_id, choice, f, url)
    matched = sorted({c for c in df.loc[df["is_numer"] & ~df["is_total"], "category"]})
    meta.notes += f"; categorias no numerador: {matched}"
    return SourceResult(out[cols + ["moradores_total_sidra"]], meta)

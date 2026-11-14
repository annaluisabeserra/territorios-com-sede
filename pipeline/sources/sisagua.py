"""Ministério da Saúde — SISAGUA, controle mensal de parâmetros básicos (qualidade da água distribuída).

Os arquivos anuais são listados pela API CKAN do OpenDataSUS (`sources.yaml → sisagua`). O leitor procura,
pelo nome, as colunas de município, parâmetro, amostras analisadas e amostras fora do padrão; usa o último ano
completo disponível. Indicador: % das amostras analisadas fora do padrão de potabilidade (todos os parâmetros
básicos) e, à parte, % das análises de E. coli com resultado fora do padrão.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL
from pipeline.sources.tabular import ckan_resources, find_col, iter_csv_chunks, to_ibge7, to_number, year_of

PAT = {
    "mun": (r"^codigo (do )?ibge|^cod(igo)? ibge|ibge|^codigo municipio|^cod municipio|^municipio cod",),
    "param": (r"^parametro$", r"parametro", r"^analise$"),
    "total": (r"(amostras|analises).*(analisad|realizad|total)", r"^total de amostras", r"numero de amostras$"),
    "fora": (r"fora (do )?padrao", r"insatisfator", r"nao conforme", r"em desacordo"),
}


def summarize(chunks, uf: UF, mun7: list[str]) -> tuple[pd.DataFrame, dict]:
    parts, cols = [], None
    for ch in chunks:
        if cols is None:
            cols = {k: find_col(ch.columns, *v) for k, v in PAT.items()}
        cod = to_ibge7(ch[cols["mun"]], mun7)
        ch = ch[cod.notna()]
        if ch.empty:
            continue
        parts.append(
            pd.DataFrame(
                {
                    "cod_ibge7": cod[cod.notna()],
                    "param": ch[cols["param"]].astype(str).str.lower(),
                    "total": to_number(ch[cols["total"]]),
                    "fora": to_number(ch[cols["fora"]]),
                }
            )
        )
    if not parts:
        raise SourceUnavailable(f"SISAGUA: nenhuma linha de município {uf.sigla}")
    d = pd.concat(parts, ignore_index=True)
    d = d[(d["total"] > 0) & (d["fora"] >= 0) & (d["fora"] <= d["total"])]
    g = d.groupby("cod_ibge7")[["total", "fora"]].sum()
    ec = d[d["param"].str.contains("coli", na=False) & ~d["param"].str.contains("totais", na=False)]
    ge = ec.groupby("cod_ibge7")[["total", "fora"]].sum()
    out = pd.DataFrame(
        {
            "sisagua_amostras": g["total"],
            "sisagua_pct_fora_padrao": 100 * g["fora"] / g["total"],
            "sisagua_ecoli_amostras": ge["total"],
            "sisagua_ecoli_pct_fora": 100 * ge["fora"] / ge["total"],
        }
    ).reset_index()
    return out, {"colunas": {k: str(v) for k, v in cols.items()}}


def municipal_quality(uf: UF, mun7: list[str]) -> SourceResult:
    s = spec("sisagua")
    res = ckan_resources("sisagua", s["ckan_api"], s["ckan_package"], "sisagua")
    csvs = [r for r in res if r["format"] in ("csv", "zip") or r["url"].lower().endswith((".csv", ".zip"))]
    last_full = dt.date.today().year - 1
    by_year = sorted(((year_of(r["name"] + " " + r["url"]) or 0, r) for r in csvs), key=lambda x: -x[0])
    errors = []
    for year, r in by_year:
        if not year or year > last_full:
            continue
        try:
            ext = ".zip" if r["url"].lower().endswith(".zip") else ".csv"
            f = fetch_one(
                "sisagua", SourceURL(r["url"], "official"), f"sisagua_{year}{ext}", "national", max_age_days=120
            )
            out, info = summarize(iter_csv_chunks(f.path), uf, mun7)
        except Exception as exc:  # noqa: BLE001 - tenta o ano anterior
            errors.append(f"{year}: {type(exc).__name__}: {str(exc)[:300]}")
            continue
        meta = make_meta(
            "sisagua", f, str(year), f"controle mensal, parâmetros básicos; colunas usadas: {info['colunas']}"
        )
        return SourceResult(out, meta, {"ano": year, **info, "avisos": errors})
    raise SourceUnavailable("SISAGUA: nenhum ano completo legível.\n" + "\n".join(errors[:5]))

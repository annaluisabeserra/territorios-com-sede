"""MIDR — S2ID: reconhecimentos federais de situação de emergência e calamidade pública.

Arquivo listado pela API CKAN do portal de dados abertos do MIDR (`sources.yaml → s2id`). Conta, por
município, os reconhecimentos dos últimos 5 anos completos por seca/estiagem e por chuvas (inundação,
enxurrada, alagamento, chuvas intensas), pelo texto do tipo de desastre ou pelo código COBRADE.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL
from pipeline.sources.tabular import ckan_resources, find_col, norm, read_table, to_ibge7

YEARS = 5


def classify(text: pd.Series) -> pd.Series:
    t = text.astype(str).map(norm)
    seca = t.str.contains(r"estiagem|\bseca\b|1 4 1", regex=True)
    chuva = t.str.contains(
        r"inunda|enxurr|alagament|chuvas? intensa|tempestade|1 2 1|1 2 2|1 2 3|1 3 2 1 4", regex=True
    )
    return pd.Series(pd.NA, index=text.index, dtype="object").mask(chuva, "chuva").mask(seca, "seca")


def count_decrees(df: pd.DataFrame, uf: UF, mun7: list[str], today: dt.date | None = None) -> tuple[pd.DataFrame, dict]:
    today = today or dt.date.today()
    c_mun = find_col(df.columns, r"ibge", r"cod(igo)? (do )?municipio")
    c_type = find_col(df.columns, r"cobrade", r"tipolog", r"desastre", r"evento")
    c_date = find_col(df.columns, r"data (do |de )?reconhec", r"data (da |de )?publica", r"^data", r"^ano$", r"data")
    cod = to_ibge7(df[c_mun], mun7)
    dates = pd.to_datetime(df[c_date], errors="coerce", dayfirst=True)
    year = dates.dt.year.where(dates.notna(), pd.to_numeric(df[c_date], errors="coerce"))
    last = today.year - 1
    keep = cod.notna() & year.between(last - YEARS + 1, last)
    d = pd.DataFrame({"cod_ibge7": cod[keep], "tipo": classify(df.loc[keep, c_type])})
    # Arquivo com mais de uma linha por reconhecimento (ex.: uma por dano): conta portarias/protocolos distintos
    c_id = find_col(df.columns, r"portaria", r"protocolo", r"^n(umero|o)? (do )?(decreto|processo)", required=False)
    if c_id is not None:
        d["id"] = df.loc[keep, c_id].astype(str).str.strip()
        d = d.drop_duplicates(subset=["cod_ibge7", "tipo", "id"])
    out = pd.DataFrame(index=pd.Index(sorted(set(mun7)), name="cod_ibge7"))
    for k in ("seca", "chuva"):
        out[f"decretos_{k}_5a"] = d[d["tipo"] == k].groupby("cod_ibge7").size()
    # Ausência de reconhecimento é informação (zero), mas só para municípios da UF quando o arquivo cobre a UF
    if d.empty:
        raise SourceUnavailable(f"S2ID: nenhum reconhecimento de {uf.sigla} em {last - YEARS + 1}–{last}")
    out = out.fillna(0).reset_index()
    return out, {"periodo": f"{last - YEARS + 1}–{last}", "colunas": [str(c_mun), str(c_type), str(c_date), str(c_id)]}


def municipal_decrees(uf: UF, mun7: list[str]) -> SourceResult:
    s = spec("s2id")
    res = ckan_resources("s2id", s["ckan_api"], s["ckan_package"], "s2id")
    cand = [
        r
        for r in res
        if "reconhec" in norm(r["name"] + " " + r["url"])
        and r["url"].lower().endswith((".csv", ".xlsx", ".xls", ".zip"))
    ]
    cand += [r for r in res if r not in cand and r["url"].lower().endswith((".csv", ".xlsx", ".xls"))]
    errors = []
    for i, r in enumerate(cand[:6]):
        ext = "." + r["url"].lower().rsplit(".", 1)[-1]
        try:
            f = fetch_one("s2id", SourceURL(r["url"], "official"), f"s2id_{i}{ext}", "national", max_age_days=30)
            out, info = count_decrees(read_table(f.path), uf, mun7)
        except Exception as exc:  # noqa: BLE001 - próximo recurso
            errors.append(f"{r['name']}: {type(exc).__name__}: {str(exc)[:300]}")
            continue
        meta = make_meta("s2id", f, info["periodo"], f"recurso '{r['name']}'; colunas: {info['colunas']}")
        return SourceResult(out, meta, {**info, "avisos": errors})
    raise SourceUnavailable("S2ID: nenhum recurso legível.\n" + "\n".join(errors[:5]))

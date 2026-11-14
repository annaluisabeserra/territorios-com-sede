"""INEP — Censo Escolar (microdados da educação básica): escolas públicas sem água potável, banheiro ou esgoto.

Usa o arquivo `microdados_censo_escolar_{ano}.zip` mais recente publicado (`sources.yaml → censo_escolar`),
tabela de escolas (`microdados_ed_basica_{ano}.csv`). Só escolas públicas (federal, estadual, municipal) em
atividade. Indicadores por município: % sem água potável, % sem banheiro, % sem esgoto e matrículas nelas.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL
from pipeline.sources.tabular import iter_csv_chunks, to_ibge7

COLS = [
    "CO_MUNICIPIO",
    "TP_SITUACAO_FUNCIONAMENTO",
    "TP_DEPENDENCIA",
    "IN_AGUA_POTAVEL",
    "IN_BANHEIRO",
    "IN_ESGOTO_INEXISTENTE",
    "QT_MAT_BAS",
]
FLAGS = {  # coluna → (nome interno, valor que indica a falta)
    "IN_AGUA_POTAVEL": ("escolas_sem_agua_potavel", "0"),
    "IN_BANHEIRO": ("escolas_sem_banheiro", "0"),
    "IN_ESGOTO_INEXISTENTE": ("escolas_sem_esgoto", "1"),
}


def summarize(chunks, mun7: list[str]) -> pd.DataFrame:
    parts = []
    for ch in chunks:
        missing = [c for c in COLS if c not in ch.columns]
        if missing:
            raise KeyError(f"colunas ausentes no Censo Escolar: {missing}")
        cod = to_ibge7(ch["CO_MUNICIPIO"], mun7)
        ch = ch[
            cod.notna()
            & (ch["TP_SITUACAO_FUNCIONAMENTO"].str.strip() == "1")
            & ch["TP_DEPENDENCIA"].str.strip().isin(["1", "2", "3"])
        ]
        if ch.empty:
            continue
        p = pd.DataFrame(
            {
                "cod_ibge7": cod[ch.index],
                "escolas": 1,
                "mat": pd.to_numeric(ch["QT_MAT_BAS"], errors="coerce").fillna(0),
            }
        )
        for col, (name, bad) in FLAGS.items():
            v = ch[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            known = v.isin(["0", "1"])
            p[f"{name}_n"] = (v == bad).astype(float).where(known)
            p[f"{name}_mat"] = p["mat"].where(v == bad, 0.0).where(known)
            p[f"{name}_known"] = known.astype(float)
        parts.append(p)
    if not parts:
        raise SourceUnavailable("Censo Escolar: nenhuma escola pública em atividade na UF")
    g = pd.concat(parts).groupby("cod_ibge7").sum(min_count=1)
    out = pd.DataFrame({"escolas_publicas": g["escolas"]})
    for _, (name, _) in FLAGS.items():
        out[f"{name}_pct"] = 100 * g[f"{name}_n"] / g[f"{name}_known"].where(g[f"{name}_known"] > 0)
        out[f"{name}_matriculas"] = g[f"{name}_mat"]
    return out.reset_index()


def municipal_schools(uf: UF, mun7: list[str]) -> SourceResult:
    s = spec("censo_escolar")
    errors = []
    for year in range(dt.date.today().year - 1, dt.date.today().year - 5, -1):
        url = s["url_template"].format(ano=year)
        try:
            f = fetch_one(
                "censo_escolar", SourceURL(url, "official"), f"censo_escolar_{year}.zip", "national", max_age_days=365
            )
            chunks = iter_csv_chunks(
                f.path, usecols=lambda c: c in COLS, member_pattern=r"microdados_ed_basica_\d{4}\.csv$"
            )
            out = summarize(chunks, mun7)
        except Exception as exc:  # noqa: BLE001 - ano ainda não publicado ou layout diferente
            errors.append(f"{year}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        meta = make_meta("censo_escolar", f, str(year), "escolas públicas em atividade (federal, estadual, municipal)")
        return SourceResult(out, meta, {"ano": year, "avisos": errors})
    raise SourceUnavailable("Censo Escolar: nenhum ano legível.\n" + "\n".join(errors))

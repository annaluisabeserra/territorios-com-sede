"""DATASUS — SIM (Sistema de Informações sobre Mortalidade): óbitos por DRSAI, por município de residência.

Arquivos anuais DO{UF}{AAAA}.dbc na pasta DORES (por UF de residência). Só a causa básica (CAUSABAS) entra;
grupos de CID iguais aos do SIH (`cid_drsai.yaml`). Saída longa por município, ano, grupo e idade, para que o
build calcule médias, suprima contagens pequenas (ADR-011) e estime anos produtivos perdidos.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from pipeline.config import RAW_DIR, UF, load
from pipeline.sources.catalog import SourceResult, SourceUnavailable, make_meta
from pipeline.sources.http import Fetched
from pipeline.sources.sih import NotPublished, _download
from pipeline.transform.cid import code_to_group

COLUMNS = ["CODMUNRES", "CAUSABAS", "IDADE", "DTOBITO"]


def file_url(uf: str, year: int) -> str:
    return load("sources")["datasus_sim"]["url_template"].format(uf=uf, yyyy=year)


def age_from_idade(idade: pd.Series) -> pd.Series:
    """IDADE do SIM: 1º dígito = unidade (0–3: minutos, horas, dias, meses ⇒ menos de 1 ano; 4 = anos; 5 = 100+)."""
    s = idade.astype(str).str.strip().str.zfill(3)
    unit, val = s.str[0], pd.to_numeric(s.str[1:], errors="coerce")
    out = pd.Series(float("nan"), index=idade.index)
    out[unit.isin(["0", "1", "2", "3"])] = 0.0
    out[unit == "4"] = val[unit == "4"]
    out[unit == "5"] = 100 + val[unit == "5"]
    return out


def reduce_do(df: pd.DataFrame, year: int) -> pd.DataFrame:
    mapping = code_to_group()
    cid3 = df["CAUSABAS"].astype(str).str.strip().str.upper().str[:3]
    out = pd.DataFrame(
        {
            "munic_res": df["CODMUNRES"].astype(str).str.strip(),
            "year": year,
            "group": cid3.map(mapping),
            "age": age_from_idade(df["IDADE"]),
        }
    )
    out = out[out["group"].notna()]
    return out.groupby(["munic_res", "year", "group", "age"], dropna=False).size().rename("obitos").reset_index()


def read_do(dbc_path, year: int) -> pd.DataFrame:
    from dbfread import DBF
    from pyreaddbc import dbc2dbf

    dbf = dbc_path.with_suffix(".dbf")
    dbc2dbf(str(dbc_path), str(dbf))
    prefixes = set(code_to_group())
    rows = []
    for rec in DBF(str(dbf), encoding="iso-8859-1", load=False, char_decode_errors="replace"):
        if str(rec.get("CAUSABAS", "")).strip().upper()[:3] in prefixes:
            rows.append({c: rec.get(c) for c in COLUMNS})
    dbf.unlink(missing_ok=True)
    return reduce_do(pd.DataFrame(rows, columns=COLUMNS), year)


def municipal_deaths(uf: UF, mun7: list[str]) -> SourceResult:
    n_years = int(load("calculadora")["years_average"])
    this_year = dt.date.today().year
    frames, years, last_url = [], [], None
    # SIM consolidado sai com ~2 anos de defasagem: procura do ano passado para trás
    for year in range(this_year - 1, this_year - 9, -1):
        if len(years) == n_years:
            break
        url = file_url(uf.sigla, year)
        dest = RAW_DIR / "sim_dbc" / f"DO{uf.sigla}{year}.dbc"
        try:
            if not dest.exists():
                _download(url, dest)
        except NotPublished:
            if not years:
                continue  # ainda não publicado: tenta o ano anterior
            break  # buraco no meio da série: para, para não misturar anos não consecutivos
        frames.append(read_do(dest, year))
        years.append(year)
        last_url = last_url or url
    if not years:
        raise SourceUnavailable(f"SIM: nenhum arquivo DO{uf.sigla}AAAA.dbc encontrado nos últimos 8 anos")
    df = pd.concat(frames, ignore_index=True)
    by6 = {c[:6]: c for c in mun7}
    df["cod_ibge7"] = df["munic_res"].str[:6].map(by6)
    unmatched = int(df.loc[df["cod_ibge7"].isna(), "obitos"].sum())
    df = df.dropna(subset=["cod_ibge7"]).drop(columns="munic_res")
    years = sorted(years)
    fake = Fetched(dest.parent, last_url, "official", "", pd.Timestamp.utcnow().isoformat(), False)
    meta = make_meta(
        "datasus_sim", fake, f"{years[0]}–{years[-1]}", f"óbitos de residentes fora da UF ou sem município: {unmatched}"
    )
    return SourceResult(df, meta, {"years": years, "obitos_sem_municipio": unmatched})

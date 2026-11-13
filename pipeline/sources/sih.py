"""DATASUS SIH/SUS — internações por DRSAI por município de residência.

Arquivos RD{UF}{AA}{MM}.dbc (AIH reduzida) por UF do estabelecimento e mês de processamento. Para contar
por residência é preciso ler as UFs vizinhas/todas (`residence_scope`), porque um morador da Bahia internado
em Pernambuco aparece no arquivo de PE. Cada arquivo é reduzido a um extrato DRSAI pequeno (Parquet) que fica
em cache (`data/raw/sih_extracts`, preservado entre execuções pelo actions/cache); o .dbc é apagado em seguida.

Regras de contagem (alinhadas ao TabNet, "Internações" por ano de processamento):
- internação = AIH com IDENT ≠ 5 (AIH de longa permanência/continuação não conta como nova internação);
- valor = VAL_TOT de todas as AIHs (inclusive continuação), nominal do mês de processamento;
- dias = DIAS_PERM; óbito hospitalar = MORTE == 1;
- idade em anos a partir de COD_IDADE/IDADE (4 = anos, 5 = 100 + anos, demais = menor de 1 ano).
"""

from __future__ import annotations

import logging
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

from pipeline.config import RAW_DIR, load
from pipeline.transform.cid import code_to_group

log = logging.getLogger(__name__)
ALL_UFS = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]
EXTRACT_DIR = RAW_DIR / "sih_extracts"
COLUMNS = [
    "MUNIC_RES",
    "ANO_CMPT",
    "MES_CMPT",
    "IDENT",
    "DIAG_PRINC",
    "DIAS_PERM",
    "VAL_TOT",
    "MORTE",
    "IDADE",
    "COD_IDADE",
]


def file_url(uf: str, year: int, month: int) -> str:
    tpl = load("sources")["datasus_sih"]["url_template"]
    return tpl.format(uf=uf, yy=f"{year % 100:02d}", mm=f"{month:02d}")


def age_years(cod_idade: pd.Series, idade: pd.Series) -> pd.Series:
    cod = cod_idade.astype(str).str.strip()
    val = pd.to_numeric(idade, errors="coerce")
    out = pd.Series(0.0, index=idade.index)
    out[cod == "4"] = val[cod == "4"]
    out[cod == "5"] = 100 + val[cod == "5"]
    return out


def reduce_rd(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra DRSAI (todas as camadas) e mantém só as colunas necessárias, com tipos limpos."""
    mapping = code_to_group()
    df = df[[c for c in COLUMNS if c in df.columns]].copy()
    cid3 = df["DIAG_PRINC"].astype(str).str.strip().str.upper().str[:3]
    df["group"] = cid3.map(mapping)
    df = df[df["group"].notna()].copy()
    out = pd.DataFrame(
        {
            "munic_res6": df["MUNIC_RES"].astype(str).str.strip().str[:6],
            "year": pd.to_numeric(df["ANO_CMPT"], errors="coerce").astype("Int64"),
            "month": pd.to_numeric(df["MES_CMPT"], errors="coerce").astype("Int64"),
            "is_admission": df["IDENT"].astype(str).str.strip() != "5",
            "cid": df["DIAG_PRINC"].astype(str).str.strip().str.upper(),
            "group": df["group"],
            "days": pd.to_numeric(df["DIAS_PERM"], errors="coerce").fillna(0).astype(float),
            "value": pd.to_numeric(df["VAL_TOT"], errors="coerce").fillna(0).astype(float),
            "death": pd.to_numeric(df["MORTE"], errors="coerce").fillna(0).astype(int) == 1,
            "age": age_years(df["COD_IDADE"], df["IDADE"]),
        }
    )
    return out.reset_index(drop=True)


def _download(url: str, dest: Path, timeout: int = 300) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=timeout) as r, open(tmp, "wb") as fh:  # noqa: S310 - FTP oficial
        shutil.copyfileobj(r, fh)
    tmp.replace(dest)


def extract(uf: str, year: int, month: int, *, refresh: bool = False) -> Path | None:
    """Garante o extrato DRSAI de um arquivo RD. Devolve None se o arquivo não existe no FTP."""
    out = EXTRACT_DIR / f"RD{uf}{year % 100:02d}{month:02d}.parquet"
    if out.exists() and not refresh:
        return out
    url = file_url(uf, year, month)
    dbc = RAW_DIR / "sih_dbc" / Path(url).name
    try:
        _download(url, dbc)
    except Exception as exc:  # noqa: BLE001
        log.warning("SIH indisponível %s: %s", url, exc)
        return None
    dbf = dbc.with_suffix(".dbf")
    try:
        red = reduce_rd(read_rd(dbc, dbf))
        out.parent.mkdir(parents=True, exist_ok=True)
        red.to_parquet(out, index=False)
    finally:
        dbc.unlink(missing_ok=True)
        dbf.unlink(missing_ok=True)
    return out


def read_rd(dbc: Path, dbf: Path) -> pd.DataFrame:
    """Converte .dbc → .dbf (pyreaddbc) e lê só as colunas e linhas DRSAI (pré-filtro pelo CID)."""
    from dbfread import DBF
    from pyreaddbc import dbc2dbf

    dbc2dbf(str(dbc), str(dbf))
    prefixes = set(code_to_group())
    rows = []
    for rec in DBF(str(dbf), encoding="iso-8859-1", load=False, char_decode_errors="replace"):
        diag = str(rec.get("DIAG_PRINC", "")).strip().upper()
        if diag[:3] in prefixes:
            rows.append({c: rec.get(c) for c in COLUMNS})
    return pd.DataFrame(rows, columns=COLUMNS)


def latest_complete_year(probe_uf: str = "BA", start: int | None = None) -> int:
    """Último ano com o arquivo de dezembro publicado."""
    import datetime as dt

    y = start or dt.date.today().year
    for year in range(y, y - 4, -1):
        if extract(probe_uf, year, 12) is not None:
            return year
    raise RuntimeError("nenhum arquivo de dezembro do SIH encontrado nos últimos 4 anos")


def load_extracts(years: list[int], scope: list[str]) -> tuple[pd.DataFrame, list[str]]:
    frames, missing = [], []
    for year in years:
        for month in range(1, 13):
            for uf in scope:
                p = extract(uf, year, month)
                if p is None:
                    missing.append(f"RD{uf}{year % 100:02d}{month:02d}")
                    continue
                frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame(columns=["munic_res6"]), missing
    return pd.concat(frames, ignore_index=True), missing


def aggregate(ext: pd.DataFrame, uf_code: str, crosswalk6to7: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """Agrega município de residência × ano × grupo. Retorna também o relatório da de-para."""
    ext = ext[ext["munic_res6"].str.startswith(uf_code)].copy()
    ext["cod_ibge7"] = ext["munic_res6"].map(crosswalk6to7)
    unmapped = ext[ext["cod_ibge7"].isna()]
    report = {
        "rows": int(len(ext)),
        "unmapped_rows": int(len(unmapped)),
        "unmapped_codes": sorted(unmapped["munic_res6"].unique().tolist()),
    }
    ext = ext[ext["cod_ibge7"].notna()]
    ext["adm"] = ext["is_admission"].astype(int)
    ext["adm_death"] = (ext["is_admission"] & ext["death"]).astype(int)
    ext["days_6_17"] = ext["days"].where((ext["age"] >= 6) & (ext["age"] <= 17), 0.0)
    ext["days_under14"] = ext["days"].where(ext["age"] < 14, 0.0)
    ext["adm_under5"] = (ext["is_admission"] & (ext["age"] < 5)).astype(int)
    g = ext.groupby(["cod_ibge7", "year", "group"], as_index=False).agg(
        internacoes=("adm", "sum"),
        valor_nominal=("value", "sum"),
        dias=("days", "sum"),
        obitos=("adm_death", "sum"),
        dias_6_17=("days_6_17", "sum"),
        dias_menor14=("days_under14", "sum"),
        internacoes_menor5=("adm_under5", "sum"),
    )
    g["year"] = g["year"].astype(int)
    return g, report

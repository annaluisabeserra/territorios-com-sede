"""Utilitários para fontes cujo layout muda entre edições: descoberta de arquivos via CKAN e colunas por padrão.

Regra geral: quando a coluna esperada não é encontrada, o leitor falha com uma mensagem que lista as colunas
vistas (vai para o .meta.json), em vez de adivinhar.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from pipeline.sources.catalog import fetch_one
from pipeline.sources.http import SourceURL


def norm(s: object) -> str:
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def find_col(columns, *patterns: str, required: bool = True) -> str | None:
    """Primeira coluna cujo nome normalizado casa com algum padrão (na ordem dos padrões)."""
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for pat in patterns:
        for c in cols:
            if re.search(pat, normed[c]):
                return c
    if required:
        raise KeyError(f"coluna não encontrada para {patterns}; colunas vistas: {[str(c) for c in cols][:60]}")
    return None


def ckan_resources(source_id: str, api_base: str, package: str, cache_tag: str) -> list[dict]:
    """Lista de recursos (name, url, format) de um conjunto de dados CKAN."""
    url = f"{api_base.rstrip('/')}/api/3/action/package_show?id={package}"
    f = fetch_one(source_id, SourceURL(url, "official"), f"ckan_{cache_tag}.json", "national", max_age_days=7)
    data = json.loads(f.path.read_text())
    if not data.get("success"):
        raise RuntimeError(f"CKAN respondeu sem sucesso para {package}")
    return [
        {"name": r.get("name") or "", "url": r.get("url") or "", "format": (r.get("format") or "").lower()}
        for r in data["result"].get("resources", [])
    ]


def year_of(text: str) -> int | None:
    m = re.findall(r"(20\d{2})", text)
    return int(m[-1]) if m else None


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def iter_csv_chunks(
    path: Path, usecols=None, chunksize: int = 200_000, member_pattern: str = r"\.csv$"
) -> Iterator[pd.DataFrame]:
    """Lê CSV (ou CSV dentro de .zip) em pedaços, detectando separador e codificação."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if re.search(member_pattern, n, re.I)]
            if not names:
                raise FileNotFoundError(f"nenhum arquivo casando {member_pattern} em {path.name}: {z.namelist()[:20]}")
            for n in names:
                with z.open(n) as fh:
                    head = fh.read(20000)
                enc = "utf-8-sig" if _is_utf8(head) else "latin-1"
                sep = _sep(_decode(head))
                with z.open(n) as fh:
                    yield from pd.read_csv(
                        io.TextIOWrapper(fh, encoding=enc, errors="replace"),
                        sep=sep,
                        dtype=str,
                        usecols=usecols,
                        chunksize=chunksize,
                        low_memory=False,
                    )
        return
    head = path.open("rb").read(20000)
    enc = "utf-8-sig" if _is_utf8(head) else "latin-1"
    yield from pd.read_csv(
        path,
        sep=_sep(_decode(head)),
        dtype=str,
        encoding=enc,
        encoding_errors="replace",
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )


def read_table(path: Path) -> pd.DataFrame:
    """Planilha ou CSV inteiro (arquivos pequenos), com cabeçalho na primeira linha que parece cabeçalho."""
    name = path.name.lower()
    if name.endswith((".xlsx", ".xls")):
        raw = pd.read_excel(path, header=None, dtype=str)
        # cabeçalho = primeira linha com pelo menos metade das células preenchidas
        for i in range(min(len(raw), 30)):
            if raw.iloc[i].notna().mean() >= 0.5:
                df = raw.iloc[i + 1 :].copy()
                df.columns = [str(c) for c in raw.iloc[i]]
                return df
        raise ValueError(f"cabeçalho não encontrado em {path.name}")
    return pd.concat(list(iter_csv_chunks(path)), ignore_index=True)


def _is_utf8(b: bytes) -> bool:
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # pode ter cortado no meio de um caractere multibyte
        try:
            b[:-3].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False


def _sep(sample: str) -> str:
    first = sample.splitlines()[0] if sample else ""
    return max([";", ",", "\t", "|"], key=first.count)


def to_ibge7(series: pd.Series, mun7: list[str]) -> pd.Series:
    """Códigos de 6 ou 7 dígitos → 7 dígitos dos municípios da UF (outros viram NaN)."""
    s = series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    by6 = {c[:6]: c for c in mun7}
    seven = set(mun7)
    return s.where(s.isin(seven), s.str[:6].map(by6))


def to_number(series: pd.Series) -> pd.Series:
    """Número em formato brasileiro ("1.234,5") ou internacional ("1234.5")."""
    s = series.astype(str).str.strip()
    br = s.str.contains(",", regex=False)
    s = s.where(~br, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")

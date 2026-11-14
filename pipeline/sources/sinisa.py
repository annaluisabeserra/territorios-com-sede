"""SINISA — sucessor do SNIS a partir do ano de referência 2023 (coleta SINISA 2024 em diante).

O Ministério das Cidades publica, por edição, planilhas de "Informações e Indicadores" por módulo (água,
esgoto). Os nomes dos arquivos mudam a cada edição, então o leitor:

1. abre as páginas de resultados listadas em `sources.yaml → sinisa.pages`;
2. escolhe os links de planilha (.xlsx/.csv/.zip) de água e de esgoto com indicadores municipais
   (descarta retificações, glossários, manuais e planilhas de prestadores regionais);
3. reconhece as colunas pelo código do indicador (ex.: IAG0001) ou, na falta dele, pelo texto do cabeçalho;
4. devolve o mesmo formato da série do SNIS (`cod_ibge7`, `year`, colunas `snis_*`), para continuar a série.

Equivalências SNIS → SINISA usadas (Trata Brasil/GO Associados 2025; Ranking ABES 2025; glossário SINISA):
IN055 → IAG0001, IN056 → IES0001, IN046 → IES2003. As demais vêm por texto do cabeçalho e ficam registradas
nos flags. A mudança de metodologia entre os sistemas é uma quebra de série documentada em METODOLOGIA.md.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL
from pipeline.sources.snis import clean_series

CODE_RE = re.compile(r"\b([A-Z]{3}\d{4})\b")
LINK_RE = re.compile(r"""href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
SHEET_EXT = (".xlsx", ".xls", ".csv", ".zip")


def norm(s: object) -> str:
    """Minúsculas, sem acento, espaços simples."""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


# --------------------------------------------------------------------------- descoberta de links


def pick_links(html: str, base_url: str) -> dict[str, list[str]]:
    """Links de planilha por módulo ('agua' | 'esgoto'), do mais provável ao menos provável."""
    from urllib.parse import urljoin

    scored: dict[str, list[tuple[int, str]]] = {"agua": [], "esgoto": []}
    for href, text in LINK_RE.findall(html):
        url = urljoin(base_url, href.strip())
        low = norm(url + " " + re.sub(r"<[^>]+>", " ", text))
        if not any(ext in url.lower() for ext in SHEET_EXT):
            continue
        if any(bad in low for bad in ("retific", "glossari", "manual", "regiona", "residuo", "pluvia", "drenag")):
            continue
        module = "esgoto" if "esgot" in low else "agua" if ("agua" in low or "abastec" in low) else None
        if module is None:
            continue
        score = 2 * ("indicador" in low) + ("informac" in low) + ("munic" in low) + ("planilha" in low)
        scored[module].append((score, url))
    return {m: [u for _, u in sorted(v, key=lambda x: -x[0])] for m, v in scored.items()}


# --------------------------------------------------------------------------- leitura de planilha


def _frames(path: Path) -> list[pd.DataFrame]:
    """Todas as abas (sem cabeçalho) de um .xlsx/.xls/.csv, ou dos arquivos dentro de um .zip."""
    name = path.name.lower()
    if name.endswith(".zip"):
        out = []
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith((".xlsx", ".xls", ".csv")):
                    tmp = path.with_name(path.stem + "__" + Path(n).name)
                    tmp.write_bytes(z.read(n))
                    out += _frames(tmp)
        return out
    if name.endswith(".csv"):
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "latin-1"):
            try:
                txt = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = ";" if txt[:5000].count(";") > txt[:5000].count(",") else ","
        return [pd.read_csv(io.StringIO(txt), sep=sep, header=None, dtype=str)]
    return list(pd.read_excel(path, sheet_name=None, header=None, dtype=str).values())


def _ibge_column(df: pd.DataFrame, start: int) -> int | None:
    best, best_share = None, 0.5
    body = df.iloc[start : start + 200]
    for j in range(df.shape[1]):
        vals = body.iloc[:, j].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        if not len(vals):
            continue
        share = vals.str.fullmatch(r"\d{6,7}").mean()
        if share > best_share:
            best, best_share = j, share
    return best


def _data_start(df: pd.DataFrame) -> int | None:
    """Primeira linha em que alguma coluna tem cara de código IBGE (6 ou 7 dígitos)."""
    for i in range(min(len(df), 40)):
        row = df.iloc[i].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        if row.str.fullmatch(r"\d{6,7}").any():
            nxt = df.iloc[i + 1 : i + 4].astype(str).apply(lambda c: c.str.fullmatch(r"\d{6,7}(\.0)?")).any(axis=None)
            if nxt:
                return i
    return None


def parse_sheet(
    df: pd.DataFrame, indicators: dict, ref_year: int, uf: UF, mun7: list[str]
) -> tuple[pd.DataFrame, dict]:
    """Uma aba → DataFrame (cod_ibge7, year, colunas internas) e o mapa coluna→indicador usado."""
    start = _data_start(df)
    if start is None or start == 0:
        return pd.DataFrame(), {}
    ibge = _ibge_column(df, start)
    if ibge is None:
        return pd.DataFrame(), {}
    header = [norm(" ".join(df.iloc[:start, j].dropna().astype(str))) for j in range(df.shape[1])]
    codes = [CODE_RE.findall(" ".join(df.iloc[:start, j].dropna().astype(str))) for j in range(df.shape[1])]
    used: dict[str, str] = {}
    cols: dict[str, int] = {}
    for name, rule in indicators.items():
        for j in range(df.shape[1]):
            if any(c in rule.get("codes", []) for c in codes[j]):
                cols[name], used[name] = j, f"código {codes[j][0]}"
                break
        else:
            pat = rule.get("header")
            if pat:
                for j in range(df.shape[1]):
                    if j != ibge and re.search(pat, header[j]):
                        cols[name], used[name] = j, f"cabeçalho '{header[j][:80]}'"
                        break
    if not cols:
        return pd.DataFrame(), {}
    body = df.iloc[start:]
    code = body.iloc[:, ibge].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    by6 = {c[:6]: c for c in mun7}
    code = code.where(code.str.len() == 7, code.map(by6))
    out = pd.DataFrame({"cod_ibge7": code})
    year_col = next((j for j, h in enumerate(header) if re.fullmatch(r"ano( de referencia)?", h)), None)
    out["year"] = pd.to_numeric(body.iloc[:, year_col], errors="coerce") if year_col is not None else ref_year
    for name, j in cols.items():
        v = body.iloc[:, j].astype(str).str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        # "1.234,5" → 1234.5; valores já com ponto decimal (ex.: "84.1" vindo do Excel) chegam sem vírgula
        raw = body.iloc[:, j].astype(str).str.strip()
        v = v.where(raw.str.contains(","), raw)
        out[name] = pd.to_numeric(v, errors="coerce")
    out = out[out["cod_ibge7"].notna() & out["cod_ibge7"].str.startswith(uf.code)]
    return out, used


def header_sample(path: Path, n: int = 15) -> list[str]:
    """Primeiros textos das linhas de cabeçalho da 1ª aba (diagnóstico quando nada é reconhecido)."""
    try:
        frames = _frames(path)
    except Exception as exc:  # noqa: BLE001
        return [f"(não foi possível abrir: {type(exc).__name__})"]
    if not frames:
        return []
    df = frames[0]
    cells = [str(v) for v in df.iloc[:8].to_numpy().ravel() if pd.notna(v) and str(v).strip()]
    return [c[:60] for c in cells[:n]]


def read_module(path: Path, indicators: dict, ref_year: int, uf: UF, mun7: list[str]) -> tuple[pd.DataFrame, dict]:
    parts, used = [], {}
    for df in _frames(path):
        part, u = parse_sheet(df, indicators, ref_year, uf, mun7)
        if len(part):
            parts.append(part)
            used.update(u)
    if not parts:
        return pd.DataFrame(), {}
    merged = parts[0]
    for p in parts[1:]:
        merged = merged.merge(p, on=["cod_ibge7", "year"], how="outer", suffixes=("", "__dup"))
        for c in [c for c in merged.columns if c.endswith("__dup")]:
            merged[c[:-5]] = merged[c[:-5]].fillna(merged[c])
            merged = merged.drop(columns=c)
    return merged, used


# --------------------------------------------------------------------------- entrada


def municipal_series(uf: UF, mun7: list[str]) -> SourceResult:  # noqa: F821
    from pipeline.sources.catalog import SourceResult

    s = spec("sinisa")
    indicators: dict = s["indicators"]
    frames, used_all, errors, files = [], {}, [], []
    fetched_any = None
    for page in s["pages"]:
        url, ref_year = page["url"], int(page["reference_year"])
        try:
            html_f = fetch_one(
                "sinisa", SourceURL(url, "official"), f"sinisa_{ref_year}.html", "national", max_age_days=30
            )
            links = pick_links(html_f.path.read_text(errors="ignore"), url)
        except SourceUnavailable as exc:
            errors.append(f"{ref_year}: página indisponível ({str(exc).splitlines()[0][:160]})")
            continue
        year_parts = []
        for module in ("agua", "esgoto"):
            mod_ind = {k: v for k, v in indicators.items() if v["module"] == module}
            tried = []
            for i, link in enumerate(links[module][:3]):
                ext = next((e for e in SHEET_EXT if e in link.lower()), ".xlsx")
                try:
                    f = fetch_one(
                        "sinisa",
                        SourceURL(link, "official"),
                        f"sinisa_{ref_year}_{module}_{i}{ext}",  # um arquivo por link (antes, todos reusavam o 1º)
                        "national",
                        max_age_days=60,
                    )
                    part, used = read_module(f.path, mod_ind, ref_year, uf, mun7)
                except Exception as exc:  # noqa: BLE001 - próximo link
                    errors.append(f"{ref_year}/{module}: {link}: {type(exc).__name__}: {str(exc)[:160]}")
                    continue
                if not len(part):
                    tried.append(f"{link} → cabeçalhos: {header_sample(f.path)}")
                if len(part):
                    year_parts.append(part)
                    used_all.update({f"{ref_year}:{k}": v for k, v in used.items()})
                    files.append(link)
                    fetched_any = fetched_any or f
                    break
            else:
                errors.append(
                    f"{ref_year}/{module}: nenhuma planilha com indicadores municipais reconhecíveis; "
                    f"links de planilha na página: {links[module][:5]}; tentativas: {tried}"
                )
        if year_parts:
            y = year_parts[0]
            for p in year_parts[1:]:
                y = y.merge(p, on=["cod_ibge7", "year"], how="outer")
            frames.append(y)
    if not frames:
        raise SourceUnavailable("SINISA: nenhuma edição pôde ser lida.\n" + "\n".join(errors))
    df = pd.concat(frames, ignore_index=True).groupby(["cod_ibge7", "year"], as_index=False).first()
    flags = {"indicadores_reconhecidos": used_all, "avisos": errors[:20]}
    # Percentual em escala 0–1? (algumas planilhas exportam fração)
    for col in [c for c in df.columns if c.endswith("_pct")]:
        q = df[col].dropna()
        if len(q) >= 10 and q.quantile(0.95) <= 1.0:
            df[col] = df[col] * 100
            flags[f"{col}_fracao_para_pct"] = True
    df, cflags = clean_series(df)
    flags.update(cflags)
    years = f"{int(df['year'].min())}–{int(df['year'].max())}"
    meta = make_meta(
        "sinisa",
        fetched_any,
        years,
        f"planilhas: {'; '.join(files)}. Quebra de série em relação ao SNIS (ver metodologia).",
    )
    return SourceResult(df, meta, flags)

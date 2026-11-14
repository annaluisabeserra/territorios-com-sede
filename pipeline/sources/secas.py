"""ANA — Monitor de Secas do Brasil: severidade mensal da seca, levada a cada município.

A página "Dados SIG" de cada ano (`sources.yaml → monitor_secas.page_template`) lista, por mês, um .zip com o
shapefile das áreas em seca (S0 fraca … S4 excepcional). Para cada um dos últimos 12 meses publicados, o
município recebe a classe da área que contém o seu ponto representativo (dentro do polígono municipal);
fora de qualquer área de seca = sem seca. Indicadores: meses com seca moderada ou pior (S1+) e classe máxima.
"""

from __future__ import annotations

import datetime as dt
import re

import geopandas as gpd
import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL

LINK_RE = re.compile(r"""href=["']([^"']+\.zip[^"']*)["']""", re.I)


def month_links(html: str, base: str, year: int) -> dict[tuple[int, int], str]:
    from urllib.parse import urljoin

    out = {}
    for href in LINK_RE.findall(html):
        m = re.search(r"(20\d{2})[_\-/]?(0[1-9]|1[0-2])(?!\d)", href) or re.search(
            r"(0[1-9]|1[0-2])[_\-/](20\d{2})", href
        )
        if not m:
            continue
        a, b = m.groups()
        y, mo = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
        if y == year:
            out[(y, mo)] = urljoin(base, href)
    return out


def severity(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Classe 0–4 a partir da primeira coluna cujos valores parecem S0–S4, D0–D4 ou 0–4."""
    for c in gdf.columns:
        if c == "geometry":
            continue
        v = gdf[c].astype(str).str.strip().str.upper()
        m = v.str.extract(r"^[SD]?([0-4])$")[0]
        if m.notna().mean() > 0.8:
            return pd.to_numeric(m)
    raise KeyError(f"coluna de severidade não encontrada; colunas: {list(gdf.columns)}")


def month_severity(shp_zip, points: gpd.GeoDataFrame) -> pd.Series:
    areas = gpd.read_file(f"zip://{shp_zip}")
    areas = areas.assign(sev=severity(areas))[["sev", "geometry"]].to_crs(points.crs)
    j = gpd.sjoin(points, areas, how="left", predicate="within")
    return j.groupby(j.index)["sev"].max()


def municipal_drought(uf: UF, malha: gpd.GeoDataFrame) -> SourceResult:
    s = spec("monitor_secas")
    today = dt.date.today()
    links: dict[tuple[int, int], str] = {}
    pages = []
    for year in (today.year, today.year - 1):
        url = s["page_template"].format(ano=year)
        try:
            f = fetch_one(
                "monitor_secas", SourceURL(url, "official"), f"monitor_secas_{year}.html", "national", max_age_days=7
            )
            links.update(month_links(f.path.read_text(errors="ignore"), url, year))
            pages.append(f)
        except SourceUnavailable:
            continue
    months = sorted(links)[-12:]
    if len(months) < 6:
        raise SourceUnavailable(f"Monitor de Secas: só {len(months)} meses com shapefile encontrados")
    pts = malha[["cod_ibge7", "geometry"]].copy()
    pts["geometry"] = pts.geometry.representative_point()
    pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=malha.crs).set_index("cod_ibge7")
    table = {}
    errors = []
    for y, mo in months:
        try:
            z = fetch_one(
                "monitor_secas", SourceURL(links[(y, mo)], "official"), f"monitor_secas_{y}{mo:02d}.zip", "national"
            )
            table[f"{y}-{mo:02d}"] = month_severity(z.path, pts)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{y}-{mo:02d}: {type(exc).__name__}: {str(exc)[:200]}")
    if len(table) < 6:
        raise SourceUnavailable("Monitor de Secas: menos de 6 meses legíveis.\n" + "\n".join(errors[:5]))
    sev = pd.DataFrame(table)  # NaN = fora de área de seca no mês
    out = pd.DataFrame(
        {
            "seca_meses_12m": (sev >= 1).sum(axis=1).astype(float),
            "seca_classe_max_12m": sev.max(axis=1),
        }
    )
    out.index.name = "cod_ibge7"
    meta = make_meta(
        "monitor_secas",
        pages[0],
        f"{min(table)} a {max(table)} ({len(table)} meses)",
        "classe no ponto representativo do município",
    )
    return SourceResult(out.reset_index(), meta, {"meses": sorted(table), "avisos": errors})

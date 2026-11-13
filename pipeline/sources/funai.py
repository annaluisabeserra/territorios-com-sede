"""FUNAI — terras indígenas (polígonos oficiais, nível de território; SPEC §7)."""

from __future__ import annotations

import geopandas as gpd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, fetch_one, make_meta, try_chain
from pipeline.sources.http import SourceURL


def _normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cols = {c.lower(): c for c in gdf.columns}
    rename = {}
    for want, options in {
        "codigo_funai": ["terrai_codigo", "code_indigenous_land", "codigo"],
        "nome": ["terrai_nome", "name_indigenous_land", "name_ti", "nome"],
        "etnia": ["etnia_nome", "etnia"],
        "fase": ["fase_ti", "phase", "fase"],
        "modalidade": ["modalidade_ti", "modalidade", "modality"],
        "area_ha": ["superficie_perimetro_ha", "area_ha", "superficie"],
        "ufs": ["uf_sigla", "abbrev_state", "uf"],
        "data_ref": ["data_atualizacao", "date"],
        "municipios": ["municipio_nome", "name_muni", "municipio"],
    }.items():
        for opt in options:
            if opt in cols:
                rename[cols[opt]] = want
                break
    g = gdf.rename(columns=rename)
    # Lista branca: nenhum campo de coordenação regional, faixa de fronteira, aldeia ou ponto sai daqui.
    keep = [
        c
        for c in ["codigo_funai", "nome", "etnia", "fase", "modalidade", "area_ha", "ufs", "data_ref"]
        if c in g.columns
    ]
    g = g[keep + ["geometry"]].copy()
    if "codigo_funai" in g:
        g["codigo_funai"] = g["codigo_funai"].astype("Int64").astype(str)
    if "data_ref" in g:
        g["data_ref"] = g["data_ref"].astype("Int64").astype(str)
    if g.crs is None:
        g = g.set_crs(4674)
    return g.to_crs(4326)


def terras_indigenas(uf: UF, uf_shape: gpd.GeoDataFrame) -> SourceResult:
    """Polígonos que tocam a UF (recorte espacial pela malha municipal)."""

    def load(src: SourceURL, cache: str, reader) -> SourceResult:
        f = fetch_one("funai_terras_indigenas", src, cache, "national", max_age_days=60)
        g = _normalize(reader(f.path))
        g = g[g.geometry.notna()].copy()
        g["geometry"] = g.geometry.make_valid()
        shape = uf_shape.to_crs(4326).union_all()
        g = g[g.intersects(shape)].reset_index(drop=True)
        return SourceResult(g, make_meta("funai_terras_indigenas", f, "vigente na data de coleta", src.note))

    return try_chain(
        "funai_terras_indigenas",
        uf,
        {
            "official": lambda s: load(s, "funai_tis.geojson", gpd.read_file),
            "mirror": lambda s: load(s, "geobr_indigenouslands_2024_simplified.parquet", gpd.read_parquet),
        },
    )

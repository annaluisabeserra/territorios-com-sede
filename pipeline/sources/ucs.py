"""Unidades de conservação de uso sustentável onde vivem populações tradicionais (RESEX e RDS).

Proxy de comunidades extrativistas e ribeirinhas (SPEC §5, P2). Nível de território: polígono oficial do CNUC,
nunca localização de comunidades.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import wkt

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, fetch_one, make_meta, spec, try_chain
from pipeline.sources.http import SourceURL


def fix_prepositions(name: str) -> str:
    """O espelho capitaliza preposições ("Reserva Extrativista Da Baia De Iguapé"). Só a caixa é corrigida."""
    import re

    return re.sub(r"(?<=\s)(Da|De|Do|Das|Dos|E)(?=\s)", lambda m: m.group(1).lower(), str(name))


def uso_sustentavel(uf: UF, uf_shape: gpd.GeoDataFrame) -> SourceResult:
    cats = set(spec("ucs_uso_sustentavel")["categories"])

    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ucs_uso_sustentavel", src, "bd_geobr_unidade_conservacao.csv.gz", "national", max_age_days=180)
        df = pd.read_csv(f.path)
        df = df[df["categoria"].isin(cats)].copy()
        df["geometry"] = df["geometria"].map(wkt.loads)
        g = gpd.GeoDataFrame(
            df[
                [
                    "id_cnuc",
                    "unidade_conservacao",
                    "categoria",
                    "esfera",
                    "ano_criacao",
                    "organizacao_orgao",
                    "geometry",
                ]
            ],
            geometry="geometry",
            crs=4674,
        ).rename(columns={"unidade_conservacao": "nome", "organizacao_orgao": "orgao"})
        g["geometry"] = g.geometry.make_valid()
        g = g.to_crs(4326)
        shape = uf_shape.to_crs(4326).union_all()
        g = g[g.intersects(shape)].reset_index(drop=True)
        g["ano_criacao"] = g["ano_criacao"].astype("Int64").astype(str).replace("<NA>", None)
        g["nome"] = g["nome"].map(fix_prepositions)
        return SourceResult(g, make_meta("ucs_uso_sustentavel", f, "cadastro vigente na data do espelho", src.note))

    return try_chain("ucs_uso_sustentavel", uf, {"mirror": mirror})

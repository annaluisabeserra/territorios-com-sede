"""Invariantes dos arquivos públicos gerados a partir de data/processed (versionado)."""

import json
import math

import pytest

from pipeline import config
from pipeline.transform import build

UFS = [u for u in config.ufs() if (config.PROCESSED_DIR / u.slug / "municipios.parquet").exists()]


@pytest.fixture(scope="module", params=UFS, ids=lambda u: u.sigla)
def built(request):
    build.build_uf(request.param)
    return request.param


def _walk(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)
    else:
        yield o


def test_every_municipality_has_a_card(built):
    uf = built
    resumo = json.loads((config.PUBLIC_DIR / uf.slug / "resumo.json").read_text())
    assert len(resumo["municipios"]) == uf.expected_municipalities
    for m in resumo["municipios"]:
        assert (config.PUBLIC_DIR / uf.slug / "municipios" / f"{m['slug']}.json").exists()


def test_no_nan_and_percentages_in_range(built):
    uf = built
    resumo = json.loads((config.PUBLIC_DIR / uf.slug / "resumo.json").read_text())
    for v in _walk(resumo):
        assert not (isinstance(v, float) and math.isnan(v))
    for m in resumo["municipios"]:
        for k, v in m["ind"].items():
            if k.endswith("_pct") and v is not None:
                assert 0 <= v <= 100, (m["nome"], k, v)


def test_every_source_has_status(built):
    resumo = json.loads((config.PUBLIC_DIR / built.slug / "resumo.json").read_text())
    for name, s in resumo["sources"].items():
        assert s["status"] in {"ok", "stale", "unavailable"}, name
        if s["status"] != "unavailable":
            assert s["url"] and s["reference_period"], name


def test_indigenous_lands_have_names_and_no_sensitive_fields(built):
    import geopandas as gpd

    p = config.PUBLIC_DIR / built.slug / "terras_indigenas.geojson"
    if not p.exists():
        pytest.skip("sem camada de TIs")
    g = gpd.read_file(p)
    assert g["nome"].notna().all()
    forbidden = {"coordination_region", "faixa_fron", "name_adm_unit", "aldeia", "lat", "lon"}
    assert not (forbidden & set(g.columns))
    assert set(g.geom_type) <= {"Polygon", "MultiPolygon"}  # nunca pontos


def test_suppressed_counts_are_null_not_zero(built):
    resumo = json.loads((config.PUBLIC_DIR / built.slug / "resumo.json").read_text())
    vals = [m["ind"].get("pop_quilombola") for m in resumo["municipios"]]
    # sigilo total vira None; o espelho não deve produzir zeros artificiais em massa
    assert sum(1 for v in vals if v == 0) < 5


def test_no_broken_tokens_in_public_text(built):
    """Regressão da revisão M4: 'None', 'nan' e '¿' nunca podem aparecer em texto público."""
    import re

    bad = re.compile(r"\bNone\b|\bnan\b|¿", re.IGNORECASE)
    d = config.PUBLIC_DIR / built.slug / "municipios"
    for p in d.glob("*.json"):
        f = json.loads(p.read_text())
        text = " ".join(f["resumo"]) + f["regiao_intermediaria"] + f["regiao_imediata"]
        text += " ".join(s["why"] for s in f["suggestions"])
        assert not bad.search(text), (p.name, bad.search(text).group(0))

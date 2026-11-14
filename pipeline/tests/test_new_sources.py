"""Leitores novos (SIM, SISAGUA, S2ID, Monitor de Secas, Censo Escolar, SICONFI) com dados sintéticos de teste."""

from __future__ import annotations

import datetime as dt

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline import config
from pipeline.sources import escolar, s2id, secas, siconfi, sim, sisagua
from pipeline.transform import impact

BA = config.uf("BA")
MUN = ["2927408", "2900108", "2910800"]


def test_sim_age_codes_and_drsai_filter():
    ages = sim.age_from_idade(pd.Series(["205", "310", "430", "505", "999"]))
    assert ages.tolist()[:4] == [0.0, 0.0, 30.0, 105.0]
    do = pd.DataFrame(
        {
            "CODMUNRES": ["292740", "292740", "290010"],
            "CAUSABAS": ["A099", "I219", "A270"],
            "IDADE": ["401", "470", "455"],
            "DTOBITO": [""] * 3,
        }
    )
    red = sim.reduce_do(do, 2022)
    assert red["obitos"].sum() == 2  # infarto (I21) não é DRSAI
    assert set(red["group"]) == {"feco_oral", "contato_agua"}


def test_sisagua_summary_uses_named_columns_and_ignores_other_ufs():
    ch = pd.DataFrame(
        {
            "Código IBGE": ["292740", "292740", "290010", "355030"],
            "Parâmetro": ["Turbidez", "Escherichia coli", "Coliformes totais", "Turbidez"],
            "Número de amostras analisadas": ["100", "50", "10", "999"],
            "Número de amostras fora do padrão": ["10", "1", "20", "0"],  # 20 > 10: inconsistente, descartada
        }
    )
    out, info = sisagua.summarize([ch], BA, MUN)
    s = out.set_index("cod_ibge7")
    assert s.loc["2927408", "sisagua_pct_fora_padrao"] == pytest.approx(100 * 11 / 150)
    assert s.loc["2927408", "sisagua_ecoli_pct_fora"] == pytest.approx(2.0)
    assert "2900108" not in s.index
    assert info["colunas"]["fora"] == "Número de amostras fora do padrão"


def test_s2id_counts_by_type_in_last_five_years():
    df = pd.DataFrame(
        {
            "Cod_IBGE": ["2927408", "2900108", "2900108", "2900108", "3550308"],
            "COBRADE": [
                "1.2.1.0.0 - Inundações",
                "1.4.1.1.0 - Estiagem",
                "14120 - Seca",
                "1.4.1.1.0 - Estiagem",
                "Estiagem",
            ],
            "Data do Reconhecimento": ["10/03/2024", "05/08/2021", "01/01/2025", "01/01/2015", "01/01/2024"],
        }
    )
    out, _ = s2id.count_decrees(df, BA, MUN, today=dt.date(2026, 11, 1))
    o = out.set_index("cod_ibge7")
    assert o.loc["2927408", "decretos_chuva_5a"] == 1
    assert o.loc["2900108", "decretos_seca_5a"] == 2  # 2015 fica fora da janela 2021–2025
    assert o.loc["2910800", "decretos_seca_5a"] == 0


def test_monitor_secas_links_and_severity():
    html = (
        '<a href="/arquivos/2025_10_MS.zip">ZIP</a><a href="/x/shp_03-2025.zip">ZIP</a><a href="/a/2024_12.zip">z</a>'
    )
    links = secas.month_links(html, "https://monitordesecas.ana.gov.br/dados-sig?ano=2025", 2025)
    assert set(links) == {(2025, 10), (2025, 3)}
    g = gpd.GeoDataFrame({"Classe": ["S0", "S2", "S4"]}, geometry=[box(0, 0, 1, 1)] * 3)
    assert secas.severity(g).tolist() == [0, 2, 4]


def test_monitor_secas_point_in_area(tmp_path):
    areas = gpd.GeoDataFrame(
        {"categoria": ["S1", "S3"]}, geometry=[box(0, 0, 10, 10), box(0, 0, 2, 2)], crs="EPSG:4326"
    )
    z = tmp_path / "m.zip"
    areas.to_file(tmp_path / "m.shp")
    import zipfile

    with zipfile.ZipFile(z, "w") as zz:
        for ext in ("shp", "shx", "dbf", "prj", "cpg"):
            p = tmp_path / f"m.{ext}"
            if p.exists():
                zz.write(p, p.name)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy([1, 5, 50], [1, 5, 50]), crs="EPSG:4326", index=["a", "b", "c"])
    sev = secas.month_severity(z, pts)
    assert sev["a"] == 3 and sev["b"] == 1 and pd.isna(sev["c"])


def test_censo_escolar_public_active_schools_only():
    ch = pd.DataFrame(
        {
            "CO_MUNICIPIO": ["2927408"] * 4 + ["2900108"],
            "TP_SITUACAO_FUNCIONAMENTO": ["1", "1", "2", "1", "1"],
            "TP_DEPENDENCIA": ["3", "2", "3", "4", "3"],  # 4 = privada (fora)
            "IN_AGUA_POTAVEL": ["0", "1", "0", "0", ""],
            "IN_BANHEIRO": ["1", "1", "1", "1", "0"],
            "IN_ESGOTO_INEXISTENTE": ["1", "0", "0", "0", "0"],
            "QT_MAT_BAS": ["100", "300", "50", "80", "20"],
        }
    )
    o = escolar.summarize([ch], MUN).set_index("cod_ibge7")
    assert o.loc["2927408", "escolas_publicas"] == 2
    assert o.loc["2927408", "escolas_sem_agua_potavel_pct"] == 50.0
    assert o.loc["2927408", "escolas_sem_agua_potavel_matriculas"] == 100
    assert pd.isna(o.loc["2900108", "escolas_sem_agua_potavel_pct"])  # não informado ≠ zero
    assert o.loc["2900108", "escolas_sem_banheiro_pct"] == 100.0


def test_siconfi_function_17_liquidated_without_subfunctions():
    items = [
        {"conta": "17 - Saneamento", "coluna": "Despesas Empenhadas", "valor": 900.0},
        {"conta": "17 - Saneamento", "coluna": "Despesas Liquidadas", "valor": 800.0},
        {"conta": "17.512 - Saneamento Básico Urbano", "coluna": "Despesas Liquidadas", "valor": 700.0},
        {"conta": "10 - Saúde", "coluna": "Despesas Liquidadas", "valor": 5.0},
    ]
    assert siconfi.saneamento_value(items) == 800.0
    assert siconfi.saneamento_value(items[:1]) == 900.0
    assert siconfi.saneamento_value(items[3:]) is None


def test_lives_value_human_capital():
    # Adulto de 64 anos: só 1 ano produtivo (t = 0), sem desconto
    assert impact.lives_value([(64.0, 1.0)], 10.0, 0.085, 15, 65) == pytest.approx(3650.0)
    # Criança de 1 ano: começa a contar em t = 14, então vale menos que um adulto de 15 anos
    child = impact.lives_value([(1.0, 1.0)], 10.0, 0.085, 15, 65)
    teen = impact.lives_value([(15.0, 1.0)], 10.0, 0.085, 15, 65)
    assert 0 < child < teen
    assert impact.lives_value([(70.0, 2.0), (None, 3.0)], 10.0, 0.085, 15, 65) == 0.0
    assert impact.lives_value([(30.0, 1.0)], None, 0.085, 15, 65) is None


def test_indicator_limitations_are_plain_strings():
    # "texto: texto" sem aspas vira dicionário no YAML e quebra o dicionário de dados
    for k, v in config.load("indicadores")["indicators"].items():
        assert all(isinstance(x, str) for x in v["limitations"]), k
        assert isinstance(v["formula"], str), k

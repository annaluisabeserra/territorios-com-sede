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
    assert o.loc["2927408", "escolas_sem_agua_potavel_n"] == 1
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


def test_s2id_counts_distinct_ordinances_when_rows_repeat():
    df = pd.DataFrame(
        {
            "Cod_IBGE": ["2900108"] * 3,
            "COBRADE": ["Estiagem"] * 3,
            "Data do Reconhecimento": ["01/02/2024"] * 3,
            "Portaria": ["123/2024", "123/2024", "456/2024"],  # duas linhas da mesma portaria
        }
    )
    out, _ = s2id.count_decrees(df, BA, MUN, today=dt.date(2026, 11, 1))
    assert out.set_index("cod_ibge7").loc["2900108", "decretos_seca_5a"] == 2


def test_sidra_hierarchical_categories_are_not_double_counted(monkeypatch):
    from pipeline.sources import sidra

    # Total (0) > Rede geral (1) > [Rede geral distribuição (2), Rede geral outra (2)]; Poço (1)
    levels = {6795: 0, 1: 1, 11: 2, 12: 2, 2: 1}
    assert sidra.drop_nested({1, 11, 12}, levels) == {1}
    assert sidra.leaf_ids(levels) == {11, 12, 2}
    choice = sidra.TableChoice(
        10341,
        "t",
        1,
        "Moradores",
        1821,
        {6795: "Total", 1: "Rede geral", 11: "Rede geral de distribuição", 12: "Rede geral, outra", 2: "Poço"},
        levels,
    )
    rows = []
    for cid, name, v in [
        (6795, "Total", 100),
        (1, "Rede geral", 70),
        (11, "Rede geral de distribuição", 60),
        (12, "Rede geral, outra", 10),
        (2, "Poço", 30),
    ]:
        rows.append({"cod_ibge7": "2800308", "category_id": cid, "category": name, "value": float(v)})
    monkeypatch.setattr(sidra, "_discover", lambda sid: choice)
    monkeypatch.setattr(
        sidra,
        "_values",
        lambda c, uf, all_categories: (pd.DataFrame(rows), type("F", (), {"fetched_at": "", "sha256": ""})(), "u"),
    )
    monkeypatch.setattr(sidra, "spec", lambda sid: {"name": "x", "sidra": {"numerator": ["rede geral"]}})
    res = sidra.share_from_catalog("censo_agua", config.uf("SE"), "censo_agua_rede_pct")
    assert res.data.iloc[0]["censo_agua_rede_pct"] == 70.0  # 70 de 100, não 140


def test_monitor_secas_links_by_query_params():
    html = '<a href="/dados-sig/download?tipo=shp&ano=2025&mes=7">ZIP</a><a href="/dados-sig/download?tipo=pdf&ano=2025&mes=7">PDF</a>'
    assert secas.month_links(html, "https://monitordesecas.ana.gov.br/dados-sig?ano=2025", 2025) == {
        (2025, 7): "https://monitordesecas.ana.gov.br/dados-sig/download?tipo=shp&ano=2025&mes=7"
    }


def test_firewall_block_page_is_detected(tmp_path):
    from pipeline.sources.http import looks_blocked

    p = tmp_path / "x.csv"
    p.write_bytes(
        b"<html><head><title>Request Rejected</title></head><body>The requested URL was rejected.</body></html>"
    )
    assert looks_blocked(p)
    p.write_bytes(b"cod_ibge7;valor\n2800308;1\n")
    assert not looks_blocked(p)


def _meta(tid, var_name, unit="Pessoas", n_cls=0):
    return {
        "id": tid,
        "nome": f"t{tid}",
        "periodicidade": {"inicio": 2022, "fim": 2022},
        "nivelTerritorial": {"Administrativo": ["N6"]},
        "variaveis": [{"id": tid * 10, "nome": var_name, "unidade": unit}],
        "classificacoes": [{"id": i, "nome": f"c{i}", "categorias": []} for i in range(n_cls)],
    }


def test_sidra_excludes_household_residents_when_choosing_quilombola_population():
    from pipeline.sources import sidra

    metas = [
        _meta(10101, "Moradores em domicílios com pelo menos um morador quilombola"),
        _meta(9578, "Pessoas quilombolas", n_cls=2),
    ]
    c = sidra.choose_table(metas, ["quilombola"], None, ("pessoas",), ["domicilio"], 9578)
    assert c.table == 9578


def test_sidra_income_excludes_mass_of_income():
    from pipeline.sources import sidra

    metas = [
        _meta(10297, "Massa de rendimento nominal mensal domiciliar per capita", unit="Reais"),
        _meta(10295, "Valor do rendimento nominal médio mensal domiciliar per capita", unit="Reais", n_cls=1),
    ]
    c = sidra.choose_table(metas, ["rendimento", "medio", "per capita"], None, ("reais",), ["massa", "participacao"])
    assert c.table == 10295


def test_sidra_dash_means_zero_and_x_means_suppressed():
    from pipeline.sources import sidra

    assert sidra.parse_value("-") == 0.0
    assert sidra.parse_value("X") is None and sidra.parse_value("...") is None
    assert sidra.parse_value("12") == 12.0

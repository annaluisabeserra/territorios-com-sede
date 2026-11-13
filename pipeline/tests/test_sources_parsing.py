"""Parsers das fontes com fixtures sintéticas (só para teste; nunca publicadas)."""

import pandas as pd

from pipeline.sources import sidra
from pipeline.sources.sih import age_years, aggregate, reduce_rd
from pipeline.transform.cid import code_to_group, expand


def test_cid_expand_and_groups():
    assert expand("A00-A09")[0] == "A00" and expand("A00-A09")[-1] == "A09" and len(expand("A00-A09")) == 10
    g = code_to_group()
    assert g["A09"] == "feco_oral" and g["B65"] == "contato_agua" and g["A90"] == "vetores"
    assert "J18" not in g


def test_sidra_choose_table_prefers_simplest_valid():
    metas = [
        {
            "id": 1,
            "nome": "A",
            "periodicidade": {"inicio": 2010, "fim": 2010},
            "nivelTerritorial": {"Administrativo": ["N6"]},
            "variaveis": [{"id": 1, "nome": "Moradores", "unidade": "Pessoas"}],
            "classificacoes": [{"id": 9, "nome": "Forma de abastecimento de água", "categorias": []}],
        },
        {
            "id": 2,
            "nome": "B",
            "periodicidade": {"inicio": 2022, "fim": 2022},
            "nivelTerritorial": {"Administrativo": ["N1", "N6"]},
            "variaveis": [
                {"id": 381, "nome": "Moradores em domicílios particulares permanentes ocupados", "unidade": "Pessoas"}
            ],
            "classificacoes": [
                {
                    "id": 11,
                    "nome": "Forma principal de abastecimento de água",
                    "categorias": [{"id": 0, "nome": "Total"}, {"id": 1, "nome": "Rede geral de distribuição"}],
                },
                {"id": 12, "nome": "Cor ou raça", "categorias": []},
            ],
        },
        {
            "id": 3,
            "nome": "C",
            "periodicidade": {"inicio": 2022, "fim": 2022},
            "nivelTerritorial": {"Administrativo": ["N6"]},
            "variaveis": [{"id": 381, "nome": "Moradores em domicílios", "unidade": "Pessoas"}],
            "classificacoes": [{"id": 11, "nome": "Forma principal de abastecimento de água", "categorias": []}],
        },
    ]
    c = sidra.choose_table(metas, ["moradores"], ["abastecimento de água"])
    assert c.table == 3  # 2010 descartada; entre 2 e 3, a com menos classificações


def test_sidra_parse_values_handles_missing_tokens():
    payload = [
        {
            "id": "381",
            "resultados": [
                {
                    "classificacoes": [{"id": "11", "categoria": {"0": "Total"}}],
                    "series": [
                        {"localidade": {"id": "2927408"}, "serie": {"2022": "100"}},
                        {"localidade": {"id": "2900108"}, "serie": {"2022": "X"}},
                    ],
                },
                {
                    "classificacoes": [{"id": "11", "categoria": {"1": "Rede geral de distribuição"}}],
                    "series": [{"localidade": {"id": "2927408"}, "serie": {"2022": "80"}}],
                },
            ],
        }
    ]
    df = sidra.parse_values(payload)
    assert len(df) == 3
    assert df.loc[df.cod_ibge7 == "2900108", "value"].isna().all()
    assert df.loc[(df.cod_ibge7 == "2927408") & (df.category == "Total"), "value"].item() == 100.0


def _rd():
    return pd.DataFrame(
        {
            "MUNIC_RES": ["292740", "292740", "292740", "290000", "230010", "292740"],
            "ANO_CMPT": ["2023"] * 6,
            "MES_CMPT": ["01"] * 6,
            "IDENT": ["1", "5", "1", "1", "1", "1"],
            "DIAG_PRINC": ["A090", "A090", "B659", "A09 ", "A010", "J189"],
            "DIAS_PERM": [3, 10, 2, 1, 4, 5],
            "VAL_TOT": [300.0, 900.0, 200.0, 50.0, 400.0, 999.0],
            "MORTE": [0, 0, 1, 0, 0, 0],
            "IDADE": ["8", "8", "70", "3", "30", "40"],
            "COD_IDADE": ["4", "4", "4", "3", "4", "4"],
        }
    )


def test_age_years():
    s = age_years(pd.Series(["4", "5", "3", "2"]), pd.Series(["30", "1", "6", "10"]))
    assert s.tolist() == [30, 101, 0, 0]


def test_sih_reduce_filters_drsai_and_keeps_continuation_value():
    red = reduce_rd(_rd())
    assert len(red) == 5  # J18 (pneumonia) fora
    agg, rep = aggregate(red, "29", {"292740": "2927408"})
    sal = agg[agg.cod_ibge7 == "2927408"].set_index("group")
    # IDENT=5 não conta como internação, mas o valor entra
    assert sal.loc["feco_oral", "internacoes"] == 1
    assert sal.loc["feco_oral", "valor_nominal"] == 1200.0
    assert sal.loc["feco_oral", "dias_6_17"] == 13
    assert sal.loc["contato_agua", "obitos"] == 1
    # residência em outra UF fica de fora; código ignorado é reportado
    assert rep["unmapped_codes"] == ["290000"]
    assert "2300100" not in set(agg.cod_ibge7)

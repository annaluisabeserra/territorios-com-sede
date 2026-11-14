"""Leitor do SINISA com planilhas sintéticas (fixtures de teste, nunca publicadas)."""

from __future__ import annotations

import pandas as pd

from pipeline import config
from pipeline.sources import sinisa
from pipeline.transform.build import merge_snis_sinisa

BA = config.uf("BA")
MUN = ["2927408", "2900108", "2910800"]
IND = config.load("sources")["sinisa"]["indicators"]
AGUA = {k: v for k, v in IND.items() if v["module"] == "agua"}
ESG = {k: v for k, v in IND.items() if v["module"] == "esgoto"}


def test_pick_links_prefers_municipal_indicator_sheets_and_skips_noise():
    html = """
    <a href="/x/RETIFICACAO_UBERABA_ESGOTO.xlsx">Retificação Uberaba</a>
    <a href="/x/GLOSSARIO_AGUA.pdf">Glossário</a>
    <a href="/x/planilha-agua.xlsx/@@download/file">Planilha de Informações e Indicadores - Abastecimento de Água</a>
    <a href="/x/agua-prestadores-regionais.xlsx">Água - prestadores regionais</a>
    <a href="https://www.gov.br/y/SINISA_ESGOTO_INDICADORES_MUNICIPIOS.zip">Esgotamento Sanitário</a>
    <a href="/x/residuos.xlsx">Resíduos sólidos</a>
    """
    links = sinisa.pick_links(html, "https://www.gov.br/cidades/r/")
    assert links["agua"] == ["https://www.gov.br/x/planilha-agua.xlsx/@@download/file"]
    assert links["esgoto"] == ["https://www.gov.br/y/SINISA_ESGOTO_INDICADORES_MUNICIPIOS.zip"]


def test_parse_sheet_by_indicator_code_with_ptbr_numbers():
    df = pd.DataFrame(
        [
            ["Tabela de indicadores — SINISA 2025", None, None, None],
            ["Código IBGE", "Município", "IAG0001", "IAG0002"],
            [None, None, "Índice de atendimento total da população com rede de água", "Índice urbano"],
            ["2927408", "Salvador", "99,1", "99,5"],
            ["2900108", "Abaíra", "84,25", "97"],
            ["3550308", "São Paulo", "99,9", "99,9"],
        ]
    )
    out, used = sinisa.parse_sheet(df, AGUA, 2024, BA, MUN)
    assert used["snis_agua_pct"] == "código IAG0001"
    assert list(out["cod_ibge7"]) == ["2927408", "2900108"]  # só a UF pedida
    assert out["snis_agua_pct"].tolist() == [99.1, 84.25]
    assert (out["year"] == 2024).all()


def test_parse_sheet_by_header_text_and_six_digit_codes():
    df = pd.DataFrame(
        [
            [
                "Cód. IBGE",
                "UF",
                "Ano de referência",
                "Atendimento total com rede coletora de esgoto (%)",
                "Índice de tratamento do esgoto coletado (%)",
            ],
            ["292740", "BA", "2023", "60.5", "80"],
            ["291080", "BA", "2023", None, "50"],
            ["290010", "BA", "2023", "10", None],
        ]
    )
    out, used = sinisa.parse_sheet(df, ESG, 2099, BA, MUN)
    assert set(used) == {"snis_esgoto_pct", "snis_tratamento_coletado_pct"}
    assert out["cod_ibge7"].tolist() == ["2927408", "2910800", "2900108"]
    assert (out["year"] == 2023).all()  # coluna "ano" vence o ano da página
    assert out["snis_esgoto_pct"].iloc[0] == 60.5
    assert pd.isna(out["snis_esgoto_pct"].iloc[1])  # vazio continua vazio, nunca zero


def test_read_module_from_xlsx_file(tmp_path):
    p = tmp_path / "agua.xlsx"
    pd.DataFrame(
        [
            ["Código do município", "IAG0001", "Índice de perdas na distribuição (%)"],
            ["2927408", 98.0, 40.2],
            ["2900108", 70.0, 30.0],
        ]
    ).to_excel(p, header=False, index=False)
    out, used = sinisa.read_module(p, AGUA, 2024, BA, MUN)
    assert used["snis_agua_pct"].startswith("código")
    assert used["snis_perdas_pct"].startswith("cabeçalho")
    assert out.set_index("cod_ibge7").loc["2900108", "snis_perdas_pct"] == 30.0


def test_merge_never_overwrites_snis_years():
    snis = pd.DataFrame({"cod_ibge7": ["1", "1"], "year": [2021, 2022], "snis_agua_pct": [80.0, 81.0]})
    sin = pd.DataFrame({"cod_ibge7": ["1", "1"], "year": [2022, 2023], "snis_agua_pct": [99.0, 83.0]})
    m = merge_snis_sinisa(snis, sin)
    assert m.set_index("year").loc[2022, "snis_agua_pct"] == 81.0
    assert m.set_index("year").loc[2023, "_fonte"] == "sinisa"
    assert merge_snis_sinisa(None, None) is None


def test_thermometer_crossing_snis_sinisa_is_marked_uncertain():
    from pipeline.transform.build import mark_series_break

    th = {"status": "atrasado", "years": [2019, 2020, 2021, 2022, 2023], "uncertain": False, "reason": ""}
    mark_series_break(th, [2023, 2024])
    assert th["uncertain"] and "SINISA" in th["reason"]
    only_snis = {"status": "no_ritmo", "years": [2018, 2019, 2020], "uncertain": False, "reason": ""}
    mark_series_break(only_snis, [2023])
    assert not only_snis["uncertain"]

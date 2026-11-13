from pipeline.transform.act import suggestions
from pipeline.transform.summary import municipal_summary, one_in


def ids(ind, semi=False):
    return [s["id"] for s in suggestions(ind, {"semiarido": semi})]


def test_education_always_and_rules_fire_on_data():
    assert ids({}) == ["educacao_ambiental"]
    r = ids({"censo_agua_rede_pct": 60.0, "censo_esgoto_adequado_pct": 30.0}, semi=True)
    assert r == [
        "captacao_chuva",
        "tratamento_ponto_de_uso",
        "unidade_autonoma_solar",
        "saneamento_rural",
        "educacao_ambiental",
    ]


def test_losses_rule_requires_urban_context():
    assert "reducao_perdas" not in ids({"snis_perdas_pct": 50.0, "populacao": 10_000})
    assert "reducao_perdas" in ids({"snis_perdas_pct": 50.0, "populacao": 80_000})


def test_summary_never_invents():
    txt = " ".join(municipal_summary("X", {"populacao": 1000}, {}, {}))
    assert "Não há dado oficial recente sobre o atendimento de esgoto" in txt
    assert "ainda não foram processados" in txt
    assert one_in(33.3) == "1 em cada 3"


def test_summary_uses_each_indicator_year_and_treatment():
    ind = {"populacao": 1000, "snis_esgoto_pct": 42.2, "snis_esgoto_tratado_pct": 0.0, "snis_agua_pct": 67.8}
    txt = " ".join(municipal_summary("X", ind, {}, {"years": {"snis_esgoto_pct": 2022, "snis_agua_pct": 2021}}))
    assert "SNIS 2022" in txt and "(2021)" in txt and "None" not in txt
    assert "coletado e tratado" in txt


def test_summary_no_sewage_declaration():
    txt = " ".join(municipal_summary("X", {"populacao": 1}, {}, {"esgoto_sem_declaracao": True}))
    assert "Nenhum prestador declarou" in txt


def test_no_sewage_provider_triggers_decentralized_sanitation():
    r = suggestions({"snis_agua_pct": 90.0}, {"esgoto_sem_declaracao": True})
    s = next(x for x in r if x["id"] == "saneamento_rural")
    assert "nenhum prestador" in s["why"]


def test_solar_mentions_energy_not_evaluated():
    r = suggestions({"snis_agua_pct": 50.0}, {})
    assert "energia não foi avaliado" in next(x for x in r if x["id"] == "unidade_autonoma_solar")["why"]


def test_summary_leads_with_treated_and_never_prints_nan():
    import math

    ind = {"populacao": 1000, "snis_esgoto_pct": 99.85, "snis_esgoto_tratado_pct": 0.0, "snis_agua_pct": math.nan}
    txt = " ".join(municipal_summary("X", ind, {}, {"years": {"snis_esgoto_tratado_pct": 2022}}))
    assert txt.index("0,0% da população tem o esgoto coletado e tratado") < txt.index("99,9%")
    assert "nan" not in txt.lower() and "None" not in txt


def test_rounding_matches_site():
    from pipeline.transform.summary import pct

    assert pct(99.85) == "99,9%" and pct(2.25) == "2,3%"

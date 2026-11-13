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

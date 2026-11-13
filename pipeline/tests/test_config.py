import math

from pipeline import config


def test_ufs_load_and_ba_active():
    ufs = {u.sigla: u for u in config.ufs()}
    assert "BA" in ufs
    assert ufs["BA"].code == "29"
    assert config.uf("ba").name == "Bahia"


def test_index_weights_sum_to_one():
    dims = config.load("pesos_indice")["dimensions"]
    assert math.isclose(sum(d["weight"] for d in dims.values()), 1.0)


def test_index_components_reference_known_indicators_or_declared_extras():
    known = set(config.load("indicadores")["indicators"])
    # indicadores das fontes P1/P2 entram no indicadores.yaml quando a fonte for implementada (M6)
    pending_p1 = {"cadunico_pct_pop", "decretos_seca_5a", "decretos_chuva_5a", "sisagua_pct_fora_padrao"}
    for dim in config.load("pesos_indice")["dimensions"].values():
        for comp in dim["components"]:
            assert comp["indicator"] in known | pending_p1, comp["indicator"]


def test_indicators_have_required_fields():
    for key, ind in config.load("indicadores")["indicators"].items():
        for field in ("label", "short", "unit", "direction", "group", "source", "formula", "limitations"):
            assert field in ind, f"{key} sem {field}"
        if ind.get("map"):
            assert ind.get("palette") in {"sequential", "diverging"}, key


def test_sdw_scenario_is_labelled():
    sc = {s["id"]: s for s in config.load("calculadora")["scenarios"]}
    assert sc["sdw92"]["reduction_pct"] == 92
    assert "validação independente" in sc["sdw92"]["disclaimer"]

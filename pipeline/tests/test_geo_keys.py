import pytest

from pipeline.transform.geo_keys import build_crosswalk, ibge_check_digit, to6


@pytest.mark.parametrize(
    "code7",
    ["2927408", "2312403", "2910800", "3550308", "5300108"],  # Salvador, S. G. do Amarante/CE, Feira, SP, DF
)
def test_check_digit_known_codes(code7):
    assert ibge_check_digit(code7[:6]) == int(code7[6])


def test_to6_rejects_bad_input():
    with pytest.raises(ValueError):
        to6("29274")


def test_crosswalk_detects_collision():
    with pytest.raises(ValueError):
        build_crosswalk(["2927408", "2927400"])
    assert build_crosswalk(["2927408"]) == {"292740": "2927408"}

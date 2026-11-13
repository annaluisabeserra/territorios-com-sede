"""Chaves geográficas: código IBGE de 7 dígitos ↔ 6 dígitos (DATASUS)."""

from __future__ import annotations

WEIGHTS = (1, 2, 1, 2, 1, 2)


def ibge_check_digit(code6: str) -> int:
    """Dígito verificador do código de município do IBGE (módulo 10, pesos 1-2).

    Válido para quase todos os municípios; há exceções históricas conhecidas, por isso a de-para oficial é
    construída a partir da lista do IBGE (truncando o 7º dígito), e esta função serve só como verificação.
    """
    if len(code6) != 6 or not code6.isdigit():
        raise ValueError(f"código de 6 dígitos inválido: {code6!r}")
    total = 0
    for digit, weight in zip(code6, WEIGHTS, strict=True):
        p = int(digit) * weight
        total += p // 10 + p % 10
    return (10 - total % 10) % 10


def to6(code7: str) -> str:
    code7 = str(code7)
    if len(code7) != 7 or not code7.isdigit():
        raise ValueError(f"código IBGE de 7 dígitos inválido: {code7!r}")
    return code7[:6]


def build_crosswalk(codes7: list[str]) -> dict[str, str]:
    """De-para 6→7 a partir da lista oficial. Falha se houver colisão (dois 7 com o mesmo 6)."""
    out: dict[str, str] = {}
    for c7 in codes7:
        c6 = to6(c7)
        if c6 in out and out[c6] != c7:
            raise ValueError(f"colisão na de-para: {c6} → {out[c6]} e {c7}")
        out[c6] = c7
    return out

"""Expansão dos códigos CID-10 configurados em cid_drsai.yaml."""

from __future__ import annotations

from functools import cache

from pipeline.config import load


def expand(code: str) -> list[str]:
    """'A00-A09' → ['A00', ..., 'A09']; 'B15' → ['B15']. Intervalos só dentro da mesma letra."""
    code = code.strip().upper()
    if "-" not in code:
        if len(code) != 3:
            raise ValueError(f"código CID de 3 caracteres esperado: {code}")
        return [code]
    a, b = code.split("-")
    if a[0] != b[0]:
        raise ValueError(f"intervalo CID entre letras diferentes: {code}")
    lo, hi = int(a[1:]), int(b[1:])
    if lo > hi:
        raise ValueError(f"intervalo CID invertido: {code}")
    return [f"{a[0]}{n:02d}" for n in range(lo, hi + 1)]


@cache
def code_to_group() -> dict[str, str]:
    out: dict[str, str] = {}
    for gid, g in load("cid_drsai")["groups"].items():
        for c in g["codes"]:
            for code in expand(c):
                if code in out:
                    raise ValueError(f"CID {code} em dois grupos: {out[code]} e {gid}")
                out[code] = gid
    return out


def groups_in_layer(layer: str) -> set[str]:
    return {gid for gid, g in load("cid_drsai")["groups"].items() if g["layer"] == layer}


def core_groups() -> set[str]:
    return groups_in_layer("core")

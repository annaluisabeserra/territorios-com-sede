"""Carregamento das configurações YAML do pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
ROOT = CONFIG_DIR.parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PUBLIC_DIR = DATA_DIR / "public"
PIPELINE_VERSION = "0.1.0"


@cache
def load(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class UF:
    sigla: str
    code: str
    name: str
    region: str
    expected_municipalities: int
    census2022_population: int
    slug: str
    active: bool
    preposicao: str = "de"  # "da Bahia", "do Ceará": usado em textos
    capital: str | None = None  # código IBGE da capital (sonda de fontes por município, ex.: SICONFI)


def ufs(active_only: bool = True) -> list[UF]:
    data = load("ufs")["ufs"]
    out = [UF(sigla=k, **v) for k, v in data.items()]
    return [u for u in out if u.active] if active_only else out


def uf(sigla: str) -> UF:
    for u in ufs(active_only=False):
        if u.sigla == sigla.upper():
            return u
    raise KeyError(f"UF não configurada em ufs.yaml: {sigla}")

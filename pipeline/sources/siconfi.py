"""Tesouro Nacional — SICONFI: despesa municipal na função 17 (Saneamento), DCA Anexo I-E.

Uma consulta por município à API de dados abertos (`sources.yaml → siconfi.api`). Usa o último exercício com
declaração da capital ou do primeiro município que responder; município sem DCA naquele ano fica sem dado
(nunca zero). Valor: despesa liquidada na função Saneamento, em R$ nominais do exercício.
"""

from __future__ import annotations

import datetime as dt
import json
import time

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, SourceUnavailable, fetch_one, make_meta, spec
from pipeline.sources.http import SourceURL
from pipeline.sources.tabular import norm


def saneamento_value(items: list[dict]) -> float | None:
    """Despesa liquidada da função 17 - Saneamento (sem subfunções); empenhada só se não houver liquidada."""
    rows = [i for i in items if norm(i.get("conta", "")).startswith("17 saneamento")]
    for col in ("liquidad", "empenhad"):
        vals = [float(i["valor"]) for i in rows if col in norm(i.get("coluna", "")) and i.get("valor") is not None]
        if vals:
            return sum(vals)
    return None


def _query(cod: str, year: int) -> dict:
    s = spec("siconfi")
    url = f"{s['api']}/dca?an_exercicio={year}&no_anexo=DCA-Anexo%20I-E&id_ente={cod}"
    f = fetch_one("siconfi", SourceURL(url, "official"), f"siconfi_{year}_{cod}.json", "siconfi", max_age_days=60)
    return json.loads(f.path.read_text()), f


def municipal_spending(uf: UF, mun7: list[str], capital: str | None = None) -> SourceResult:
    probe = capital if capital in mun7 else mun7[0]
    year = None
    for y in range(dt.date.today().year - 1, dt.date.today().year - 4, -1):
        try:
            data, _ = _query(probe, y)
        except SourceUnavailable:
            continue
        if saneamento_value(data.get("items", [])) is not None or data.get("items"):
            year = y
            break
    if year is None:
        raise SourceUnavailable(f"SICONFI: nenhum exercício com DCA para {probe}")
    rows, last_f, errors = [], None, 0
    for cod in mun7:
        try:
            data, last_f = _query(cod, year)
            rows.append({"cod_ibge7": cod, "despesa_saneamento": saneamento_value(data.get("items", []))})
        except SourceUnavailable:
            errors += 1
            rows.append({"cod_ibge7": cod, "despesa_saneamento": None})
        time.sleep(spec("siconfi").get("pause_s", 0.3))
    df = pd.DataFrame(rows)
    if df["despesa_saneamento"].notna().sum() == 0:
        raise SourceUnavailable(f"SICONFI {year}: nenhum município com valor na função Saneamento")
    df["despesa_saneamento_ano"] = year
    meta = make_meta("siconfi", last_f, str(year), f"DCA Anexo I-E, função 17; consultas com erro: {errors}")
    return SourceResult(
        df, meta, {"exercicio": year, "erros": errors, "sem_valor": int(df["despesa_saneamento"].isna().sum())}
    )

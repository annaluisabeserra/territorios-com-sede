"""IPCA mensal (número-índice) para corrigir valores monetários (SIH) para reais do ano-base."""

from __future__ import annotations

import json

import pandas as pd

from pipeline.config import UF
from pipeline.sources.catalog import SourceResult, fetch_one, make_meta, try_chain
from pipeline.sources.http import SourceURL


def monthly_index(uf: UF) -> SourceResult:
    def official(src: SourceURL) -> SourceResult:
        # SGS 433 = variação mensal (%). Encadeamos para obter um número-índice (base = primeiro mês = 100).
        f = fetch_one("ipca", src, "bcb_sgs_433.json", "national", max_age_days=20)
        rows = json.loads(f.path.read_text())
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["var"] = df["valor"].astype(float)
        df = df.sort_values("date")
        df["index"] = 100 * (1 + df["var"] / 100).cumprod()
        out = pd.DataFrame({"year": df["date"].dt.year, "month": df["date"].dt.month, "index": df["index"]})
        last = out.iloc[-1]
        return SourceResult(out, make_meta("ipca", f, f"até {int(last.month):02d}/{int(last.year)}"))

    def mirror(src: SourceURL) -> SourceResult:
        f = fetch_one("ipca", src, "bd_ipca_mes_brasil.csv.gz", "national", max_age_days=60)
        df = pd.read_csv(f.path)
        out = df.rename(columns={"ano": "year", "mes": "month", "indice": "index"})[["year", "month", "index"]]
        out = out.dropna().sort_values(["year", "month"]).reset_index(drop=True)
        last = out.iloc[-1]
        return SourceResult(out, make_meta("ipca", f, f"até {int(last.month):02d}/{int(last.year)}", src.note))

    return try_chain("ipca", uf, {"official": official, "mirror": mirror})


def annual_deflator(ipca: pd.DataFrame, base_year: int) -> dict[int, float]:
    """Fator que leva valores nominais de cada ano para reais do ano-base (média anual do índice).

    Usa a média dos meses disponíveis de cada ano; o ano-base precisa ter os 12 meses ou é rebaixado para o
    último ano completo (decisão conservadora, registrada no meta pelo chamador).
    """
    g = ipca.groupby("year")["index"].agg(["mean", "count"])
    if base_year not in g.index or g.loc[base_year, "count"] < 12:
        raise ValueError(f"ano-base {base_year} sem 12 meses de IPCA")
    base = g.loc[base_year, "mean"]
    return {int(y): float(base / row["mean"]) for y, row in g.iterrows() if row["count"] == 12}


def last_complete_year(ipca: pd.DataFrame) -> int:
    g = ipca.groupby("year")["month"].nunique()
    return int(g[g == 12].index.max())

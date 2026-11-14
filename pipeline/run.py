"""Orquestrador do pipeline: `python -m pipeline.run [--uf BA] [--skip-sih] [--only-build]`.

Etapas por UF:
  1. ingestão (uma etapa por fonte; falha de fonte não derruba o pipeline, exceto as fontes-chave);
  2. validação (pipeline/validate) — checagens da SPEC §9 derrubam o pipeline se falharem;
  3. transformação (pipeline/transform/build.py) — indicadores, termômetro, índice, JSON público.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline import config
from pipeline.sources import ana, escolar, funai, ibge, ipca, s2id, secas, siconfi, sih, sim, sinisa, sisagua, snis, ucs
from pipeline.sources.catalog import SourceResult
from pipeline.sources.meta import OutputMeta, read_meta
from pipeline.transform.geo_keys import build_crosswalk

log = logging.getLogger("pipeline")

# Fontes sem as quais não há plataforma: falha aqui derruba o pipeline daquela UF.
KEY_SOURCES = {"municipios", "malhas", "populacao"}


def processed_dir(uf: config.UF) -> Path:
    d = config.PROCESSED_DIR / uf.slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(df: pd.DataFrame, path: Path) -> None:
    if isinstance(df, gpd.GeoDataFrame):
        df.to_parquet(path, index=False)
    else:
        df.to_parquet(path, index=False)


def stage(uf: config.UF, name: str, fn: Callable[[], SourceResult], status: dict) -> None:
    path = processed_dir(uf) / f"{name}.parquet"
    try:
        res = fn()
        _write(res.data, path)
        meta = OutputMeta(output=path.name, uf=uf.sigla, sources=[res.meta])
        # Histórico de mudanças: avisa quando o arquivo de origem mudou desde a última atualização válida
        prev_meta = read_meta(path)
        prev_sha = ((prev_meta or {}).get("sources") or [{}])[0].get("sha256")
        if prev_sha and res.meta.sha256 and prev_sha != res.meta.sha256:
            res.meta.notes = (
                res.meta.notes
                + f" | arquivo de origem mudou desde a última atualização (sha256 anterior {prev_sha[:12]}…)"
            ).strip(" |")
            log.info("[%s] %s: arquivo de origem mudou", uf.sigla, name)
        if res.flags:
            meta.status_reason = json.dumps(res.flags, ensure_ascii=False)
            if res.flags.get("stale"):
                meta.status = "stale"
        meta.write(path)
        status[name] = {"status": "ok", "rows": int(len(res.data)), "url_kind": res.meta.url_kind, "url": res.meta.url}
        log.info("[%s] %s: ok (%d linhas, %s)", uf.sigla, name, len(res.data), res.meta.url_kind)
    except Exception as exc:  # noqa: BLE001
        # Motivo curto para os metadados públicos (sem stack trace nem detalhes do ambiente)
        # Todas as linhas (cada URL tentada e o erro dela), numa linha só: sem isso o motivo se perdia
        lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        reason = f"{type(exc).__name__}: {' | '.join(lines)[:1500]}"
        prev = read_meta(path)
        if path.exists() and prev:
            prev["status"] = "stale"
            prev["status_reason"] = f"última atualização falhou: {reason[:500]}"
            path.with_name(path.name + ".meta.json").write_text(json.dumps(prev, ensure_ascii=False, indent=2))
            status[name] = {"status": "stale", "reason": reason[:500]}
            log.warning("[%s] %s: falhou, mantida a última versão válida", uf.sigla, name)
        else:
            unavailable = OutputMeta(output=path.name, uf=uf.sigla, status="unavailable", status_reason=reason[:2000])
            unavailable.write(path)
            status[name] = {"status": "unavailable", "reason": reason[:500]}
            log.warning("[%s] %s: indisponível (%s)", uf.sigla, name, reason.splitlines()[0][:200])
        if name in KEY_SOURCES:
            raise


def run_sih(uf: config.UF, status: dict) -> None:
    """SIH separado: muitas leituras, escopo de residência configurável, de-para validada."""

    def fn() -> SourceResult:
        from pipeline.sources.catalog import make_meta
        from pipeline.sources.http import Fetched

        cfg = config.load("sources")["datasus_sih"]
        n_years = int(config.load("calculadora")["years_average"])
        scope = sih.ALL_UFS if cfg.get("residence_scope") == "all_ufs" else [uf.sigla]
        last = sih.latest_complete_year(scope)
        years = list(range(last - n_years + 1, last + 1))
        ext, missing = sih.load_extracts(years, scope)
        own = [m for m in missing if m.startswith(f"RD{uf.sigla}")]
        if own:
            raise RuntimeError(f"arquivos da própria UF ausentes em anos completos: {own}")
        mun = pd.read_parquet(processed_dir(uf) / "municipios.parquet")
        cw = build_crosswalk(mun["cod_ibge7"].tolist())
        agg, report = sih.aggregate(ext, uf.code, cw)
        (processed_dir(uf) / "sih_crosswalk_report.json").write_text(
            json.dumps({**report, "missing_files": missing, "years": years}, ensure_ascii=False, indent=2)
        )
        fake = Fetched(
            Path(), sih.file_url(uf.sigla, last, 12), "official", "", pd.Timestamp.utcnow().isoformat(), False
        )
        meta = make_meta(
            "datasus_sih",
            fake,
            f"{years[0]}–{years[-1]} (ano de processamento)",
            f"escopo de residência: {len(scope)} UFs; arquivos ausentes: {len(missing)}",
        )
        return SourceResult(agg, meta)

    stage(uf, "sih_drsai", fn, status)


def ingest(uf: config.UF, skip_sih: bool = False) -> dict:
    status: dict = {}
    stage(uf, "municipios", lambda: ibge.municipios(uf), status)
    stage(uf, "malhas", lambda: ibge.malhas(uf), status)
    stage(uf, "populacao", lambda: ibge.populacao(uf), status)
    stage(uf, "censo_agua", lambda: ibge.agua(uf), status)
    stage(uf, "censo_esgoto", lambda: ibge.esgoto(uf), status)
    stage(uf, "censo_lixo", lambda: ibge.lixo(uf), status)
    stage(uf, "censo_quilombola", lambda: ibge.quilombola(uf), status)
    stage(uf, "censo_raca", lambda: ibge.raca(uf), status)
    stage(uf, "semiarido", lambda: ibge.semiarido(uf), status)
    stage(uf, "snis", lambda: snis.municipal_series(uf), status)
    mun7 = pd.read_parquet(processed_dir(uf) / "municipios.parquet")["cod_ibge7"].tolist()
    stage(uf, "sinisa", lambda: sinisa.municipal_series(uf, mun7), status)
    stage(uf, "ana_atlas", lambda: ana.atlas_esgotos(uf), status)
    stage(uf, "ipca", lambda: ipca.monthly_index(uf), status)
    malha = gpd.read_parquet(processed_dir(uf) / "malhas.parquet")
    stage(uf, "terras_indigenas", lambda: funai.terras_indigenas(uf, malha), status)
    stage(uf, "ucs_uso_sustentavel", lambda: ucs.uso_sustentavel(uf, malha), status)
    stage(uf, "censo_renda", lambda: ibge.renda(uf), status)
    stage(uf, "censo_indigenas", lambda: ibge.indigenas(uf), status)
    from pipeline.sources.catalog import declared_unavailable

    stage(uf, "sim_drsai", lambda: sim.municipal_deaths(uf, mun7), status)
    stage(uf, "sisagua", lambda: sisagua.municipal_quality(uf, mun7), status)
    stage(uf, "s2id", lambda: s2id.municipal_decrees(uf, mun7), status)
    stage(uf, "monitor_secas", lambda: secas.municipal_drought(uf, malha), status)
    stage(uf, "censo_escolar", lambda: escolar.municipal_schools(uf, mun7), status)
    stage(uf, "siconfi", lambda: siconfi.municipal_spending(uf, mun7, uf.capital), status)
    for sid in ("incra_quilombolas", "palmares_certidoes", "cadunico"):
        stage(uf, sid, lambda sid=sid: declared_unavailable(sid), status)
    if skip_sih:
        status["sih_drsai"] = {"status": "skipped"}
    else:
        run_sih(uf, status)
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pipeline Territórios com Sede")
    ap.add_argument("--uf", action="append", help="sigla da UF (repetível). Padrão: todas as ativas")
    ap.add_argument("--skip-sih", action="store_true", help="pula o SIH (download pesado)")
    ap.add_argument("--only-build", action="store_true", help="só transforma o que já está em data/processed")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from pipeline.transform import build
    from pipeline.validate import checks

    ufs = [config.uf(s) for s in args.uf] if args.uf else config.ufs()
    failures = 0
    for uf in ufs:
        if args.only_build and not (config.PROCESSED_DIR / uf.slug / "municipios.parquet").exists():
            # UF recém-ativada ainda sem dados processados (entram no próximo data-refresh): não derruba CI e deploy
            log.warning("[%s] sem dados processados ainda; pulada no --only-build", uf.sigla)
            continue
        try:
            if not args.only_build:
                status = ingest(uf, skip_sih=args.skip_sih)
                (processed_dir(uf) / "_ingest_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2))
            checks.run_all(uf)
            build.build_uf(uf)
        except Exception:  # noqa: BLE001
            failures += 1
            log.error("[%s] pipeline falhou:\n%s", uf.sigla, traceback.format_exc())
    if failures == 0:
        build.build_national_index([asdict(u) for u in ufs])
        from pipeline.validate import report

        report.main()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""Acesso ao `sources.yaml` e utilidades comuns às fontes."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pipeline.config import UF, load
from pipeline.sources.http import Fetched, FetchError, SourceURL, fetch
from pipeline.sources.meta import SourceMeta


class SourceUnavailable(RuntimeError):
    """A fonte não pôde ser obtida (todas as URLs falharam ou o recorte não existe)."""


@dataclass
class SourceResult:
    data: pd.DataFrame
    meta: SourceMeta
    flags: dict | None = None  # ex.: {"lower_bound": True}


def spec(source_id: str) -> dict:
    return load("sources")[source_id]


def chain(source_id: str, uf: UF | None = None, kinds: tuple[str, ...] = ("official", "mirror")) -> list[SourceURL]:
    out = []
    for item in spec(source_id).get("urls", []):
        if item["kind"] not in kinds:
            continue
        url = item["url"]
        if uf is not None:
            url = url.format(uf_code=uf.code, uf=uf.sigla)
        out.append(SourceURL(url=url, kind=item["kind"], note=item.get("note", "")))
    return out


def fetch_one(source_id: str, url: SourceURL, cache_name: str, subdir: str, **kw) -> Fetched:
    try:
        return fetch([url], cache_name, subdir=subdir, **kw)
    except FetchError as exc:
        raise SourceUnavailable(str(exc)) from exc


def make_meta(source_id: str, fetched: Fetched, reference_period: str, notes: str = "") -> SourceMeta:
    s = spec(source_id)
    return SourceMeta(
        source_id=source_id,
        name=s["name"],
        url=fetched.url,
        url_kind=fetched.kind,
        reference_period=reference_period,
        fetched_at=fetched.fetched_at,
        sha256=fetched.sha256,
        license=s.get("license", ""),
        notes=notes,
    )


def try_chain(source_id: str, uf: UF, handlers: dict[str, callable]) -> SourceResult:
    """Tenta cada URL da cadeia; `handlers[kind](SourceURL) -> SourceResult`. Erros são acumulados."""
    errors: list[str] = []
    for src in chain(source_id, uf):
        handler = handlers.get(src.kind)
        if handler is None:
            continue
        try:
            return handler(src)
        except Exception as exc:  # noqa: BLE001 - cada falha é registrada e a próxima URL é tentada
            errors.append(f"[{src.kind}] {src.url}: {type(exc).__name__}: {exc}")
    raise SourceUnavailable(f"{source_id}: nenhuma URL utilizável.\n" + "\n".join(errors))


def declared_unavailable(source_id: str) -> SourceResult:
    """Fonte registrada mas sem leitor nem espelho: falha com o motivo documentado em sources.yaml."""
    s = spec(source_id)
    raise SourceUnavailable(
        f"{s['name']}: {s.get('unavailable_reason', 'indisponível')}. Referência: {s.get('official_reference', '')}"
    )

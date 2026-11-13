"""Download com cache em disco, checksum e cadeia de URLs (oficial → espelho).

Cada download devolve um `Fetched` com o caminho local e a URL efetivamente usada, que vai para o
`.meta.json` da saída (ADR-002). Rodar duas vezes reaproveita o cache (idempotência).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline.config import RAW_DIR

log = logging.getLogger(__name__)
USER_AGENT = "territorios-com-sede-pipeline/0.1 (+https://github.com/institutosdw)"


@dataclass(frozen=True)
class SourceURL:
    url: str
    kind: str = "official"  # official | mirror
    note: str = ""


@dataclass(frozen=True)
class Fetched:
    path: Path
    url: str
    kind: str
    sha256: str
    fetched_at: str
    from_cache: bool


class FetchError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(
    urls: list[SourceURL],
    cache_name: str,
    *,
    subdir: str = "",
    max_age_days: float | None = None,
    retries: int = 3,
    timeout: int = 120,
) -> Fetched:
    """Baixa o primeiro URL que responder. Usa cache se existir e não estiver vencido."""
    target = RAW_DIR / subdir / cache_name
    sidecar = target.with_name(target.name + ".fetch.json")
    if target.exists() and sidecar.exists():
        info = json.loads(sidecar.read_text())
        age_days = (time.time() - target.stat().st_mtime) / 86400
        if max_age_days is None or age_days <= max_age_days:
            if sha256_file(target) == info["sha256"]:
                return Fetched(target, info["url"], info["kind"], info["sha256"], info["fetched_at"], True)
            log.warning("checksum divergente no cache de %s; baixando de novo", target)

    target.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for src in urls:
        for attempt in range(1, retries + 1):
            try:
                with requests.get(
                    src.url, timeout=timeout, stream=True, headers={"User-Agent": USER_AGENT}
                ) as r:
                    r.raise_for_status()
                    tmp = target.with_name(target.name + ".part")
                    with open(tmp, "wb") as fh:
                        for chunk in r.iter_content(1 << 20):
                            fh.write(chunk)
                tmp.replace(target)
                digest = sha256_file(target)
                now = datetime.now(UTC).isoformat(timespec="seconds")
                sidecar.write_text(
                    json.dumps(
                        {"url": src.url, "kind": src.kind, "sha256": digest, "fetched_at": now}, indent=2
                    )
                )
                log.info("baixado %s (%s)", src.url, src.kind)
                return Fetched(target, src.url, src.kind, digest, now, False)
            except Exception as exc:  # noqa: BLE001 - registramos e tentamos o próximo
                errors.append(f"{src.url} [tentativa {attempt}]: {exc}")
                if attempt < retries:
                    time.sleep(2**attempt)
    raise FetchError("todas as URLs falharam:\n" + "\n".join(errors))

"""Metadados por arquivo de saída (SPEC §4: fonte, URL, coleta, período, versão)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pipeline.config import PIPELINE_VERSION


@dataclass
class SourceMeta:
    source_id: str
    name: str
    url: str
    url_kind: str  # official | mirror | derived
    reference_period: str
    fetched_at: str
    sha256: str = ""
    license: str = ""
    notes: str = ""


@dataclass
class OutputMeta:
    output: str
    uf: str
    sources: list[SourceMeta] = field(default_factory=list)
    status: str = "ok"  # ok | stale | unavailable
    status_reason: str = ""
    pipeline_version: str = PIPELINE_VERSION
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def write(self, data_path: Path) -> Path:
        path = data_path.with_name(data_path.name + ".meta.json")
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def read_meta(data_path: Path) -> dict | None:
    path = data_path.with_name(data_path.name + ".meta.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

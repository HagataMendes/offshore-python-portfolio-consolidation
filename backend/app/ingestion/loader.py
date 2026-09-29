"""Simula a chegada dos arquivos de exemplo, na ordem do manifesto."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .pipeline import IngestionService


def load_sample_files(service: IngestionService, root: Path) -> int:
    manifest = json.loads((root / "manifest.json").read_text())
    for item in manifest:
        service.ingest(
            file_name=item["delivered_as"],
            content=(root / item["path"]).read_bytes(),
            received_at=datetime.fromisoformat(item["received_at"]),
        )
    return len(manifest)

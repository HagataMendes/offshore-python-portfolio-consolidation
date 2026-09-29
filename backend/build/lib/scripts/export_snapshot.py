"""Salva as respostas da API num JSON que o front usa quando roda sem back-end.

Assim a prévia estática (GitHub Pages, por exemplo) mostra exatamente os
números calculados pelo Python.

Uso:  python scripts/export_snapshot.py
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "frontend" / "src" / "mocks" / "snapshot.json"
AS_OF, FROM, MONTH = "2026-09-30", "2026-08-31", "2026-09"


def main() -> None:
    logging.disable(logging.INFO)
    settings = replace(
        Settings.from_env(),
        data_dir=ROOT / "sample_data",
        database_url=None,
        use_aws=False,
        load_samples=True,
    )
    with TestClient(create_app(settings)) as api:

        def get(path: str, **params: str):
            r = api.get(path, params=params)
            r.raise_for_status()
            return r.json()

        clients = get("/clients")
        snapshot = {
            "clients": clients,
            "portfolio": {c["id"]: get(f"/clients/{c['id']}/positions", date=AS_OF) for c in clients},
            "statement": {c["id"]: get(f"/clients/{c['id']}/statement", month=MONTH) for c in clients},
            "performance": {
                c["id"]: get(f"/clients/{c['id']}/performance", **{"from": FROM, "to": AS_OF})
                for c in clients
            },
            "ingested_files": get("/ingestion/files"),
            "reconciliation_breaks": get("/reconciliation/breaks"),
        }
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n")
    print(f"Snapshot salvo em {OUT.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()

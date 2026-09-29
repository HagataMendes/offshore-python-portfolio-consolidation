"""Configuração por variáveis de ambiente (12-factor)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "sim"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str | None  # vazio = memória; postgresql+psycopg://... = Postgres
    use_aws: bool  # DynamoDB (idempotência) + SNS (eventos) + S3/SQS (worker)
    load_samples: bool  # ingerir sample_data ao subir (só no modo sem worker)
    bucket: str
    queue_name: str
    dlq_name: str
    topic_name: str
    files_table: str
    cors_origins: list[str]

    @classmethod
    def from_env(cls) -> Settings:
        database_url = os.getenv("DATABASE_URL") or None
        use_aws = _flag("USE_AWS", False)
        return cls(
            data_dir=Path(os.getenv("SAMPLE_DATA_DIR", BACKEND_DIR / "sample_data")),
            database_url=database_url,
            use_aws=use_aws,
            # Sem worker (modo simples), a própria API carrega os arquivos de exemplo.
            load_samples=_flag("LOAD_SAMPLES", not use_aws),
            bucket=os.getenv("S3_BUCKET", "custodian-files"),
            queue_name=os.getenv("SQS_QUEUE", "custodian-files-queue"),
            dlq_name=os.getenv("SQS_DLQ", "custodian-files-dlq"),
            topic_name=os.getenv("SNS_TOPIC", "portfolio-events"),
            files_table=os.getenv("DYNAMODB_FILES_TABLE", "processed-files"),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
        )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..domain.models import Custodian


class FileStatus(StrEnum):
    PROCESSED = "processado"
    DUPLICATE = "duplicado"
    FAILED = "erro_dlq"  # em produção: após 3 tentativas, a mensagem vai para a DLQ do SQS


@dataclass(frozen=True)
class IngestionRecord:
    id: str
    file_name: str
    custodian: Custodian | None
    file_format: str
    received_at: datetime
    status: FileStatus
    records: int
    duration_ms: int
    correlation_id: str
    error: str | None = None

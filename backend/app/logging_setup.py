"""Logs estruturados em JSON: prontos para Datadog ou CloudWatch.

Cada linha carrega um correlation_id, que acompanha o arquivo desde a chegada
até a gravação. Com ele dá para rastrear tudo o que aconteceu com um arquivo.
"""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def log_event(logger: logging.Logger, msg: str, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, msg, extra={"extra_fields": fields})

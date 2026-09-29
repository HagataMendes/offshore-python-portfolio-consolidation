"""Worker: consome a fila SQS e processa os arquivos que chegam no S3.

    custodiante → S3 (inbox/) → notificação → SQS → este worker → Postgres + DynamoDB → SNS

Regras de erro:
- Arquivo inválido (layout errado): é um erro permanente. Tentar de novo não resolve,
  então a mensagem vai direto para a DLQ e sai da fila principal.
- Erro inesperado (banco fora do ar, timeout): é temporário. A mensagem NÃO é apagada,
  volta para a fila depois do visibility timeout e é tentada de novo. Depois de 3
  tentativas, a própria SQS move para a DLQ (redrive policy).

Rodar:  python -m app.worker
"""

from __future__ import annotations

import json
import logging
import signal
from datetime import datetime
from urllib.parse import unquote_plus

from .config import Settings
from .container import Container
from .infra.aws import aws_client
from .ingestion.records import FileStatus
from .logging_setup import log_event, setup_logging

logger = logging.getLogger("worker")


class SqsWorker:
    def __init__(self, container: Container, sqs=None, s3=None) -> None:
        self.c = container
        self.sqs = sqs or aws_client("sqs")
        self.s3 = s3 or aws_client("s3")
        self.queue_url = self.sqs.get_queue_url(QueueName=container.settings.queue_name)["QueueUrl"]
        self.dlq_url = self.sqs.get_queue_url(QueueName=container.settings.dlq_name)["QueueUrl"]
        self._running = True

    def stop(self, *_: object) -> None:
        log_event(logger, "encerrando worker")
        self._running = False

    def run_forever(self) -> None:
        log_event(logger, "worker iniciado", queue=self.queue_url)
        while self._running:
            self.poll_once(wait_seconds=10)

    def poll_once(self, wait_seconds: int = 0) -> int:
        """Lê até 1 mensagem e processa. Uma por vez mantém a ordem de chegada dos arquivos."""
        resp = self.sqs.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=wait_seconds
        )
        messages = resp.get("Messages", [])
        for msg in messages:
            self._handle(msg)
        return len(messages)

    def drain(self, max_messages: int = 1000) -> int:
        """Processa até a fila esvaziar (útil em testes e na carga inicial)."""
        total = 0
        while total < max_messages and self.poll_once():
            total += 1
        return total

    # ------------------------------------------------------------------------

    def _handle(self, msg: dict) -> None:
        body = json.loads(msg["Body"])
        records = body.get("Records", [])
        if not records:  # s3:TestEvent e afins: nada a fazer
            self._delete(msg)
            return
        try:
            failed_errors: list[str] = []
            for rec in records:
                bucket = rec["s3"]["bucket"]["name"]
                key = unquote_plus(rec["s3"]["object"]["key"])
                obj = self.s3.get_object(Bucket=bucket, Key=key)
                received_at = _received_at(obj.get("Metadata", {}), rec.get("eventTime"))
                result = self.c.ingestion.ingest(key.rsplit("/", 1)[-1], obj["Body"].read(), received_at)
                if result.status is FileStatus.FAILED:
                    failed_errors.append(f"{key}: {result.error}")
        except Exception as e:  # erro temporário: deixa a SQS tentar de novo
            log_event(
                logger, "falha temporária, mensagem volta para a fila", level=logging.ERROR, error=str(e)
            )
            return

        if failed_errors:
            self.sqs.send_message(
                QueueUrl=self.dlq_url,
                MessageBody=msg["Body"],
                MessageAttributes={
                    "error": {"DataType": "String", "StringValue": "; ".join(failed_errors)[:1000]}
                },
            )
            log_event(logger, "mensagem enviada para a DLQ", level=logging.WARNING, errors=failed_errors)
        self._delete(msg)

    def _delete(self, msg: dict) -> None:
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=msg["ReceiptHandle"])


def _received_at(metadata: dict, event_time: str | None) -> datetime:
    """Horário de chegada: o metadado 'received-at' (usado na simulação) ou o horário do evento S3."""
    if "received-at" in metadata:
        return datetime.fromisoformat(metadata["received-at"])
    if event_time:
        return datetime.fromisoformat(event_time.replace("Z", "+00:00")).replace(tzinfo=None)
    return datetime.now()


def main() -> None:
    setup_logging()
    settings = Settings.from_env()
    worker = SqsWorker(Container(settings))
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()

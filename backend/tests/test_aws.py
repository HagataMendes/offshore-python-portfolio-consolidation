"""Caminho completo pela AWS: S3 → SQS → worker → DynamoDB → SNS.

Usa o moto, que simula a AWS dentro do próprio teste (sem rede, sem conta).
"""

import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest
from moto import mock_aws

from app.container import Container
from app.infra.aws import DynamoFileRegistry, aws_client
from app.ingestion.records import FileStatus
from app.worker import SqsWorker
from scripts import bootstrap_aws, upload_samples
from tests.conftest import SAMPLE, make_settings


@pytest.fixture
def aws(monkeypatch):
    for var, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
        "SAMPLE_DATA_DIR": str(SAMPLE),
    }.items():
        monkeypatch.setenv(var, value)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    with mock_aws():
        aws_client.cache_clear()
        bootstrap_aws.main()
        yield
    aws_client.cache_clear()


@pytest.fixture
def worker(aws) -> SqsWorker:
    return SqsWorker(Container(make_settings(use_aws=True, load_samples=False)))


def put(key: str, body: bytes) -> None:
    aws_client("s3").put_object(Bucket="custodian-files", Key=f"inbox/teste/{key}", Body=body)


def queue_messages(name: str) -> list[dict]:
    sqs = aws_client("sqs")
    url = sqs.get_queue_url(QueueName=name)["QueueUrl"]
    return sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, MessageAttributeNames=["All"]).get(
        "Messages", []
    )


def test_dynamodb_so_deixa_um_worker_reservar_o_arquivo(aws):
    registry = DynamoFileRegistry("processed-files")
    assert registry.claim("abc", "arquivo.csv", "c1") is True
    assert registry.claim("abc", "arquivo.csv", "c2") is False  # outro worker, mesmo arquivo
    registry.release("abc")
    assert registry.claim("abc", "arquivo.csv", "c3") is True  # liberado após falha


def test_arquivo_no_s3_vira_mensagem_e_e_processado(worker):
    content = (SAMPLE / "pershing" / "pershing_positions_20260831.csv").read_bytes()
    put("pershing_positions_20260831.csv", content)

    worker.drain()  # inclui a mensagem de teste que o S3 manda ao configurar a notificação
    [rec] = worker.c.repository.file_records()
    assert rec.status is FileStatus.PROCESSED
    assert queue_messages("custodian-files-queue") == []  # mensagem apagada após sucesso


def test_duplicado_e_barrado_pelo_dynamodb(worker):
    content = (SAMPLE / "pershing" / "pershing_positions_20260831.csv").read_bytes()
    put("a/pershing_positions_20260831.csv", content)
    put("b/pershing_positions_20260831.csv", content)
    worker.drain()
    assert [r.status for r in worker.c.repository.file_records()] == [
        FileStatus.PROCESSED,
        FileStatus.DUPLICATE,
    ]


def test_arquivo_invalido_vai_para_a_dlq(worker):
    put("ubs_positions_20260929.json", b'{"fileType": "POSITIONS", "portfolios": []}')
    worker.drain()
    [rec] = worker.c.repository.file_records()
    assert rec.status is FileStatus.FAILED
    [dead] = queue_messages("custodian-files-dlq")
    assert '"asOf" ausente' in dead["MessageAttributes"]["error"]["StringValue"]
    assert queue_messages("custodian-files-queue") == []


def test_evento_publicado_no_sns_chega_em_quem_assina(worker):
    put(
        "pershing_positions_20260831.csv",
        (SAMPLE / "pershing" / "pershing_positions_20260831.csv").read_bytes(),
    )
    worker.drain()
    [msg] = queue_messages("portfolio-events-audit")
    event = json.loads(json.loads(msg["Body"])["Message"])
    assert event["client_id"] == "maria" and event["as_of"] == "2026-08-31"


def test_erro_temporario_deixa_a_mensagem_na_fila(worker, monkeypatch):
    put(
        "pershing_positions_20260831.csv",
        (SAMPLE / "pershing" / "pershing_positions_20260831.csv").read_bytes(),
    )

    def banco_fora_do_ar(*_args, **_kwargs):
        raise ConnectionError("Postgres indisponível")

    monkeypatch.setattr(worker.c.ingestion.repo, "save_holdings", banco_fora_do_ar)
    worker.poll_once()
    assert worker.c.repository.file_records() == []
    # A reserva no DynamoDB foi desfeita, então a nova tentativa vai processar normalmente.
    digest = hashlib.sha256(
        (SAMPLE / "pershing" / "pershing_positions_20260831.csv").read_bytes()
    ).hexdigest()
    assert DynamoFileRegistry("processed-files").claim(digest, "retry", "c9")


def test_mes_inteiro_pela_fila_da_o_mesmo_resultado(worker):
    upload_samples.main(delay_seconds=0)
    worker.drain()
    statuses = [r.status for r in worker.c.repository.file_records()]
    assert len(statuses) == 53
    assert statuses.count(FileStatus.PROCESSED) == 51
    total = worker.c.portfolio.portfolio("maria", date(2026, 9, 30)).total_usd
    assert total == Decimal("113994.25")

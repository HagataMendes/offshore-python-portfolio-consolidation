"""Adaptadores AWS: DynamoDB (idempotência) e SNS (eventos).

Localmente, AWS_ENDPOINT_URL aponta para o LocalStack; na AWS de verdade fica vazio.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from functools import cache

import boto3
from botocore.exceptions import ClientError

from ..logging_setup import log_event

logger = logging.getLogger("aws")


@cache
def aws_client(service: str):
    return boto3.client(
        service,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL") or None,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


class DynamoFileRegistry:
    """Tabela de arquivos processados, com chave = hash SHA-256 do conteúdo.

    O put condicional (attribute_not_exists) é atômico: se dois workers tentarem
    registrar o mesmo arquivo ao mesmo tempo, só um consegue.
    """

    def __init__(self, table_name: str, client=None) -> None:
        self.table = table_name
        self.client = client or aws_client("dynamodb")

    def claim(self, digest: str, file_name: str, correlation_id: str) -> bool:
        try:
            self.client.put_item(
                TableName=self.table,
                Item={
                    "sha256": {"S": digest},
                    "file_name": {"S": file_name},
                    "correlation_id": {"S": correlation_id},
                    "status": {"S": "IN_PROGRESS"},
                    "claimed_at": {"S": datetime.now(UTC).isoformat()},
                },
                ConditionExpression="attribute_not_exists(sha256)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def complete(self, digest: str) -> None:
        self.client.update_item(
            TableName=self.table,
            Key={"sha256": {"S": digest}},
            UpdateExpression="SET #s = :done, completed_at = :at",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":done": {"S": "DONE"}, ":at": {"S": datetime.now(UTC).isoformat()}},
        )

    def release(self, digest: str) -> None:
        self.client.delete_item(TableName=self.table, Key={"sha256": {"S": digest}})


class SnsEventPublisher:
    """Publica eventos num tópico SNS. Quem quiser reagir (recalcular performance,
    notificar o assessor...) assina o tópico, sem acoplar ao serviço de ingestão."""

    def __init__(self, topic_arn: str, client=None) -> None:
        self.topic_arn = topic_arn
        self.client = client or aws_client("sns")

    def publish(self, topic: str, payload: dict) -> None:
        self.client.publish(
            TopicArn=self.topic_arn,
            Message=json.dumps(payload),
            MessageAttributes={"event_type": {"DataType": "String", "StringValue": topic}},
        )
        log_event(logger, "evento publicado no SNS", topic=topic, **payload)


def topic_arn_by_name(name: str, client=None) -> str:
    """create_topic é idempotente: devolve o ARN do tópico existente."""
    return (client or aws_client("sns")).create_topic(Name=name)["TopicArn"]

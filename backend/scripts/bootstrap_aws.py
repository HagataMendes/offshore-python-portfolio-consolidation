"""Cria os recursos AWS do projeto (no LocalStack ou numa conta real). Pode rodar várias vezes.

    S3  custodian-files         onde os custodiantes depositam os arquivos (pasta inbox/)
    SQS custodian-files-queue   recebe um aviso a cada arquivo novo no S3
    SQS custodian-files-dlq     mensagens que falharam (após 3 tentativas ou arquivo inválido)
    SNS portfolio-events        eventos "carteira atualizada"
    SQS portfolio-events-audit  assina o tópico, para dar para ver os eventos
    DynamoDB processed-files    arquivos já processados (idempotência)

Uso:  AWS_ENDPOINT_URL=http://localhost:4566 python -m scripts.bootstrap_aws
"""

from __future__ import annotations

import json

from botocore.exceptions import ClientError

from app.config import Settings
from app.infra.aws import aws_client

MAX_RECEIVE_COUNT = 3


def main() -> None:
    s = Settings.from_env()
    s3, sqs, sns, ddb = aws_client("s3"), aws_client("sqs"), aws_client("sns"), aws_client("dynamodb")

    # S3
    try:
        s3.create_bucket(Bucket=s.bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise

    # SQS: DLQ + fila principal com redrive
    dlq_url = sqs.create_queue(QueueName=s.dlq_name)["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    queue_url = sqs.create_queue(QueueName=s.queue_name)["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            "VisibilityTimeout": "60",
            "RedrivePolicy": json.dumps(
                {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": MAX_RECEIVE_COUNT}
            ),
            # Permite que o S3 escreva na fila.
            "Policy": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "s3.amazonaws.com"},
                            "Action": "sqs:SendMessage",
                            "Resource": queue_arn,
                            "Condition": {"ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{s.bucket}"}},
                        }
                    ],
                }
            ),
        },
    )

    # S3 → SQS: todo arquivo novo em inbox/ gera uma mensagem na fila
    s3.put_bucket_notification_configuration(
        Bucket=s.bucket,
        NotificationConfiguration={
            "QueueConfigurations": [
                {
                    "QueueArn": queue_arn,
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "inbox/"}]}},
                }
            ]
        },
    )

    # SNS + uma fila de auditoria assinando o tópico
    topic_arn = sns.create_topic(Name=s.topic_name)["TopicArn"]
    audit_url = sqs.create_queue(QueueName=f"{s.topic_name}-audit")["QueueUrl"]
    audit_arn = sqs.get_queue_attributes(QueueUrl=audit_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=audit_arn)

    # DynamoDB
    try:
        ddb.create_table(
            TableName=s.files_table,
            KeySchema=[{"AttributeName": "sha256", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "sha256", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceInUseException":
            raise

    print(f"Recursos prontos: s3://{s.bucket}, {s.queue_name} (+DLQ), {s.topic_name}, {s.files_table}")


if __name__ == "__main__":
    main()

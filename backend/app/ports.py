"""Portas: o que o sistema precisa da infraestrutura, sem dizer COMO é feito.

O domínio, a ingestão e a API conversam só com estas interfaces. Cada uma tem
uma implementação em memória (testes e demo) e uma real:

    PortfolioRepository    → Postgres       (app/infra/sql.py)
    ProcessedFileRegistry  → DynamoDB       (app/infra/aws.py)
    EventPublisher         → SNS            (app/infra/aws.py)

Trocar a infraestrutura não mexe em regra de negócio. É a arquitetura
"portas e adaptadores" (hexagonal).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date
from typing import Protocol

from .domain.models import Custodian, Holding, Transaction
from .domain.reconciliation import PositionBook
from .ingestion.records import IngestionRecord


class PortfolioRepository(Protocol):
    def atomic(self) -> AbstractContextManager[None]:
        """Tudo o que acontece dentro do bloco é gravado junto, ou nada é gravado."""
        ...

    def save_holdings(
        self, client_id: str, custodian: Custodian, day: date, holdings: list[Holding]
    ) -> None: ...

    def holdings_by_day(self, client_id: str, custodian: Custodian) -> dict[date, list[Holding]]: ...

    def add_transaction(self, tx: Transaction) -> bool:
        """Grava a movimentação. Devolve False se ela já existia."""
        ...

    def transactions_for(self, client_id: str) -> list[Transaction]: ...

    def next_file_id(self) -> str: ...

    def add_file_record(self, record: IngestionRecord) -> None: ...

    def file_records(self) -> list[IngestionRecord]: ...

    def load_book(self) -> PositionBook: ...

    def save_book(self, book: PositionBook) -> None: ...


class ProcessedFileRegistry(Protocol):
    """Controle de idempotência: garante que o mesmo arquivo não é processado duas vezes,
    mesmo com vários workers rodando ao mesmo tempo."""

    def claim(self, digest: str, file_name: str, correlation_id: str) -> bool:
        """Reserva o arquivo. Devolve False se outro processo já o reservou ou processou."""
        ...

    def complete(self, digest: str) -> None: ...

    def release(self, digest: str) -> None:
        """Desfaz a reserva quando o processamento falha, para um reenvio poder ser tentado."""
        ...


class EventPublisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...

"""Implementações em memória das portas. Usadas nos testes e na demo sem Docker."""

from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import nullcontext
from datetime import date

from ..domain.models import Custodian, Holding, Transaction
from ..domain.reconciliation import PositionBook
from ..ingestion.records import IngestionRecord
from ..logging_setup import log_event

logger = logging.getLogger("events")


class InMemoryRepository:
    def __init__(self) -> None:
        self._holdings: dict[tuple[str, Custodian], dict[date, list[Holding]]] = defaultdict(dict)
        self._transactions: dict[str, Transaction] = {}
        self._files: list[IngestionRecord] = []
        self._book = PositionBook()

    def atomic(self):
        return nullcontext()

    def save_holdings(self, client_id: str, custodian: Custodian, day: date, holdings: list[Holding]) -> None:
        # Um reenvio corrigido do mesmo dia substitui a versão anterior.
        self._holdings[(client_id, custodian)][day] = list(holdings)

    def holdings_by_day(self, client_id: str, custodian: Custodian) -> dict[date, list[Holding]]:
        return dict(self._holdings.get((client_id, custodian), {}))

    def add_transaction(self, tx: Transaction) -> bool:
        if tx.id in self._transactions:
            return False
        self._transactions[tx.id] = tx
        return True

    def transactions_for(self, client_id: str) -> list[Transaction]:
        return [t for t in self._transactions.values() if t.client_id == client_id]

    def next_file_id(self) -> str:
        return f"f-{len(self._files) + 1:03d}"

    def add_file_record(self, record: IngestionRecord) -> None:
        self._files.append(record)

    def file_records(self) -> list[IngestionRecord]:
        return list(self._files)

    def load_book(self) -> PositionBook:
        return self._book

    def save_book(self, book: PositionBook) -> None:
        self._book = book


class InMemoryFileRegistry:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def claim(self, digest: str, file_name: str, correlation_id: str) -> bool:
        if digest in self._items:
            return False
        self._items[digest] = "IN_PROGRESS"
        return True

    def complete(self, digest: str) -> None:
        self._items[digest] = "DONE"

    def release(self, digest: str) -> None:
        self._items.pop(digest, None)


class InMemoryEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, topic: str, payload: dict) -> None:
        self.events.append((topic, payload))
        log_event(logger, "evento publicado", topic=topic, **payload)

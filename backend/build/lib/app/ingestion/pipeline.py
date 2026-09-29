"""O caminho de um arquivo, do custodiante até os dados consolidados.

    arquivo chega → já processei? → adapter traduz → grava + reconcilia → publica evento

Em produção, isto roda no worker que consome a fila SQS alimentada pelo S3
(app/worker.py). Na demo sem Docker, a "fila" é o manifesto de exemplo.
A lógica é a mesma nos dois casos.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime

from ..adapters.base import FileKind, InvalidFileError, ParsedFile
from ..adapters.registry import AdapterRegistry
from ..domain.models import Custodian, Holding
from ..logging_setup import log_event
from ..ports import EventPublisher, PortfolioRepository, ProcessedFileRegistry
from .records import FileStatus, IngestionRecord

logger = logging.getLogger("ingestion")


class IngestionService:
    def __init__(
        self,
        repository: PortfolioRepository,
        files: ProcessedFileRegistry,
        adapters: AdapterRegistry,
        events: EventPublisher,
    ) -> None:
        self.repo = repository
        self.files = files
        self.adapters = adapters
        self.events = events

    def ingest(self, file_name: str, content: bytes, received_at: datetime) -> IngestionRecord:
        correlation_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()
        digest = hashlib.sha256(content).hexdigest()
        adapter = self._adapter_or_none(file_name)
        log_event(
            logger, "arquivo recebido", file=file_name, correlation_id=correlation_id, sha256=digest[:12]
        )

        def record(status: FileStatus, records: int = 0, error: str | None = None) -> IngestionRecord:
            rec = IngestionRecord(
                id=self.repo.next_file_id(),
                file_name=file_name,
                custodian=adapter.custodian if adapter else None,
                file_format=adapter.file_format if adapter else "?",
                received_at=received_at,
                status=status,
                records=records,
                duration_ms=max(1, round((time.perf_counter() - started) * 1000)),
                correlation_id=correlation_id,
                error=error,
            )
            self.repo.add_file_record(rec)
            log_event(
                logger,
                "arquivo finalizado",
                level=logging.WARNING if status is FileStatus.FAILED else logging.INFO,
                file=file_name,
                correlation_id=correlation_id,
                status=status.value,
                records=records,
                error=error,
            )
            return rec

        # 1. Idempotência: o mesmo conteúdo nunca é processado duas vezes.
        #    A reserva é atômica (no DynamoDB, um put condicional), então dois workers
        #    recebendo o mesmo arquivo ao mesmo tempo não processam em dobro.
        if not self.files.claim(digest, file_name, correlation_id):
            with self.repo.atomic():
                return record(FileStatus.DUPLICATE)

        try:
            # 2. Tradução: o adapter do custodiante converte para o modelo padrão.
            try:
                if adapter is None:
                    raise InvalidFileError(f"Nenhum custodiante reconhece o arquivo {file_name}")
                parsed = adapter.parse(file_name, content)
            except InvalidFileError as e:
                self.files.release(digest)
                with self.repo.atomic():
                    return record(FileStatus.FAILED, error=str(e))

            # 3. Gravação e reconciliação, numa única transação.
            with self.repo.atomic():
                affected = self._apply(parsed)
                rec = record(FileStatus.PROCESSED, parsed.records)
        except Exception:
            # Erro inesperado (ex.: banco fora do ar): libera o arquivo e deixa a fila tentar de novo.
            self.files.release(digest)
            raise

        self.files.complete(digest)

        # 4. Evento: avisa quem precisar recalcular (performance, notificações...).
        for client_id in sorted(affected):
            self.events.publish(
                "carteira-atualizada",
                {"client_id": client_id, "as_of": parsed.as_of.isoformat(), "correlation_id": correlation_id},
            )
        return rec

    # ------------------------------------------------------------------------

    def _adapter_or_none(self, file_name: str):
        try:
            return self.adapters.for_file(file_name)
        except InvalidFileError:
            return None

    def _apply(self, parsed: ParsedFile) -> set[str]:
        book = self.repo.load_book()
        if parsed.kind is FileKind.TRANSACTIONS:
            for tx in parsed.transactions:
                if self.repo.add_transaction(tx):
                    book.apply(tx)
            self.repo.save_book(book)
            return {tx.client_id for tx in parsed.transactions}

        by_account: dict[tuple[str, Custodian], list[Holding]] = defaultdict(list)
        for h in parsed.holdings:
            by_account[(h.client_id, h.custodian)].append(h)
        for (client_id, custodian), holdings in by_account.items():
            if book.is_initialized(client_id, custodian):
                for brk in book.check(holdings):
                    log_event(
                        logger,
                        "quebra de reconciliação",
                        level=logging.WARNING,
                        client_id=client_id,
                        custodian=custodian.value,
                        asset=brk.asset_name,
                        expected=brk.expected_quantity,
                        reported=brk.reported_quantity,
                    )
            else:
                book.open(holdings)  # primeira carga: vira o ponto de partida
            self.repo.save_holdings(client_id, custodian, parsed.as_of, holdings)
        self.repo.save_book(book)
        return {client_id for client_id, _ in by_account}

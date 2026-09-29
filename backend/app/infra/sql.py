"""Repositório em banco relacional (Postgres em produção, SQLite nos testes rápidos).

Usa SQLAlchemy Core: SQL explícito, sem mágica de ORM. Valores monetários ficam em
NUMERIC no Postgres (exato, nunca float). No SQLite, que não tem decimal exato,
guardamos como texto para não perder centavos.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    Date,
    DateTime,
    Engine,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    TypeDecorator,
    delete,
    func,
    insert,
    select,
)

from ..domain.models import (
    AssetClass,
    Custodian,
    Holding,
    ReconciliationBreak,
    Transaction,
    TransactionType,
)
from ..domain.reconciliation import BookState, PositionBook
from ..ingestion.records import FileStatus, IngestionRecord


class ExactDecimal(TypeDecorator):
    """NUMERIC no Postgres; texto no SQLite (que só tem float)."""

    impl = Numeric(28, 10)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(64))
        return dialect.type_descriptor(Numeric(28, 10))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


metadata = MetaData()

holdings = Table(
    "holdings",
    metadata,
    Column("client_id", String(40), primary_key=True),
    Column("custodian", String(20), primary_key=True),
    Column("as_of", Date, primary_key=True),
    Column("security_id", String(40), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("asset_class", String(20), nullable=False),
    Column("quantity", ExactDecimal, nullable=False),
    Column("price", ExactDecimal, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("price_is_percent", Boolean, nullable=False),
    Column("ticker", String(20)),
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", String(60), primary_key=True),
    Column("client_id", String(40), nullable=False, index=True),
    Column("custodian", String(20), nullable=False),
    Column("trade_date", Date, nullable=False),
    Column("type", String(20), nullable=False),
    Column("amount", ExactDecimal, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("security_id", String(40)),
    Column("quantity", ExactDecimal, nullable=False),
    Column("price", ExactDecimal),
    Column("ticker", String(200)),
)

ingested_files = Table(
    "ingested_files",
    metadata,
    Column("id", String(20), primary_key=True),
    Column("file_name", String(200), nullable=False),
    Column("custodian", String(20)),
    Column("file_format", String(10), nullable=False),
    Column("received_at", DateTime, nullable=False),
    Column("status", String(20), nullable=False),
    Column("records", Integer, nullable=False),
    Column("duration_ms", Integer, nullable=False),
    Column("correlation_id", String(20), nullable=False),
    Column("error", String(500)),
)

book_accounts = Table(
    "book_accounts",
    metadata,
    Column("client_id", String(40), primary_key=True),
    Column("custodian", String(20), primary_key=True),
)

book_positions = Table(
    "book_positions",
    metadata,
    Column("client_id", String(40), primary_key=True),
    Column("custodian", String(20), primary_key=True),
    Column("security_id", String(40), primary_key=True),
    Column("quantity", ExactDecimal, nullable=False),
)

security_names = Table(
    "security_names",
    metadata,
    Column("security_id", String(40), primary_key=True),
    Column("name", String(200), nullable=False),
)

reconciliation_breaks = Table(
    "reconciliation_breaks",
    metadata,
    Column("id", String(20), primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("day", Date, nullable=False),
    Column("client_id", String(40), nullable=False),
    Column("custodian", String(20), nullable=False),
    Column("security_id", String(40), nullable=False),
    Column("asset_name", String(200), nullable=False),
    Column("expected_quantity", ExactDecimal, nullable=False),
    Column("reported_quantity", ExactDecimal, nullable=False),
    Column("resolved", Boolean, nullable=False),
    Column("note", String(500), nullable=False),
)


class SqlRepository:
    def __init__(self, engine: Engine, create_schema: bool = True) -> None:
        self.engine = engine
        self._local = threading.local()  # uma transação por thread
        if create_schema:
            metadata.create_all(engine)

    # --- transação ---------------------------------------------------------------

    @contextmanager
    def atomic(self) -> Iterator[None]:
        if getattr(self._local, "conn", None) is not None:  # já dentro de uma transação
            yield
            return
        with self.engine.begin() as conn:
            self._local.conn = conn
            try:
                yield
            finally:
                self._local.conn = None

    @contextmanager
    def _conn(self) -> Iterator[Connection]:
        current = getattr(self._local, "conn", None)
        if current is not None:
            yield current
        else:
            with self.engine.begin() as conn:
                yield conn

    # --- posições -----------------------------------------------------------------

    def save_holdings(self, client_id: str, custodian: Custodian, day: date, rows: list[Holding]) -> None:
        with self._conn() as c:
            c.execute(
                delete(holdings).where(
                    holdings.c.client_id == client_id,
                    holdings.c.custodian == custodian.value,
                    holdings.c.as_of == day,
                )
            )
            c.execute(
                insert(holdings),
                [
                    {
                        "client_id": h.client_id,
                        "custodian": h.custodian.value,
                        "as_of": h.as_of,
                        "security_id": h.security_id,
                        "name": h.name,
                        "asset_class": h.asset_class.value,
                        "quantity": h.quantity,
                        "price": h.price,
                        "currency": h.currency,
                        "price_is_percent": h.price_is_percent,
                        "ticker": h.ticker,
                    }
                    for h in rows
                ],
            )

    def holdings_by_day(self, client_id: str, custodian: Custodian) -> dict[date, list[Holding]]:
        query = (
            select(holdings)
            .where(holdings.c.client_id == client_id, holdings.c.custodian == custodian.value)
            .order_by(holdings.c.as_of, holdings.c.security_id)
        )
        result: dict[date, list[Holding]] = defaultdict(list)
        with self._conn() as c:
            for r in c.execute(query).mappings():
                result[r["as_of"]].append(
                    Holding(
                        client_id=r["client_id"],
                        custodian=Custodian(r["custodian"]),
                        as_of=r["as_of"],
                        security_id=r["security_id"],
                        name=r["name"],
                        asset_class=AssetClass(r["asset_class"]),
                        quantity=r["quantity"],
                        price=r["price"],
                        currency=r["currency"],
                        price_is_percent=r["price_is_percent"],
                        ticker=r["ticker"],
                    )
                )
        return dict(result)

    # --- movimentações ----------------------------------------------------------------

    def add_transaction(self, tx: Transaction) -> bool:
        with self._conn() as c:
            exists = c.execute(select(transactions.c.id).where(transactions.c.id == tx.id)).first()
            if exists:
                return False
            c.execute(
                insert(transactions).values(
                    id=tx.id,
                    client_id=tx.client_id,
                    custodian=tx.custodian.value,
                    trade_date=tx.trade_date,
                    type=tx.type.value,
                    amount=tx.amount,
                    currency=tx.currency,
                    security_id=tx.security_id,
                    quantity=tx.quantity,
                    price=tx.price,
                    ticker=tx.ticker,
                )
            )
            return True

    def transactions_for(self, client_id: str) -> list[Transaction]:
        query = select(transactions).where(transactions.c.client_id == client_id).order_by(transactions.c.id)
        with self._conn() as c:
            return [
                Transaction(
                    id=r["id"],
                    client_id=r["client_id"],
                    custodian=Custodian(r["custodian"]),
                    trade_date=r["trade_date"],
                    type=TransactionType(r["type"]),
                    amount=r["amount"],
                    currency=r["currency"],
                    security_id=r["security_id"],
                    quantity=r["quantity"],
                    price=r["price"],
                    ticker=r["ticker"],
                )
                for r in c.execute(query).mappings()
            ]

    # --- log de arquivos ----------------------------------------------------------------

    def next_file_id(self) -> str:
        with self._conn() as c:
            n = c.execute(select(func.count()).select_from(ingested_files)).scalar_one()
        return f"f-{n + 1:03d}"

    def add_file_record(self, record: IngestionRecord) -> None:
        with self._conn() as c:
            c.execute(
                insert(ingested_files).values(
                    id=record.id,
                    file_name=record.file_name,
                    custodian=record.custodian.value if record.custodian else None,
                    file_format=record.file_format,
                    received_at=record.received_at,
                    status=record.status.value,
                    records=record.records,
                    duration_ms=record.duration_ms,
                    correlation_id=record.correlation_id,
                    error=record.error,
                )
            )

    def file_records(self) -> list[IngestionRecord]:
        with self._conn() as c:
            rows = c.execute(select(ingested_files).order_by(ingested_files.c.id)).mappings().all()
        return [
            IngestionRecord(
                id=r["id"],
                file_name=r["file_name"],
                custodian=Custodian(r["custodian"]) if r["custodian"] else None,
                file_format=r["file_format"],
                received_at=r["received_at"],
                status=FileStatus(r["status"]),
                records=r["records"],
                duration_ms=r["duration_ms"],
                correlation_id=r["correlation_id"],
                error=r["error"],
            )
            for r in rows
        ]

    # --- reconciliação ----------------------------------------------------------------

    def load_book(self) -> PositionBook:
        state = BookState()
        with self._conn() as c:
            for r in c.execute(select(book_accounts)).mappings():
                state.initialized.add((r["client_id"], Custodian(r["custodian"])))
            for r in c.execute(select(book_positions)).mappings():
                key = (r["client_id"], Custodian(r["custodian"]))
                state.quantities.setdefault(key, {})[r["security_id"]] = r["quantity"]
            for r in c.execute(select(security_names)).mappings():
                state.names[r["security_id"]] = r["name"]
            for r in c.execute(
                select(reconciliation_breaks).order_by(reconciliation_breaks.c.seq)
            ).mappings():
                state.breaks.append(
                    ReconciliationBreak(
                        id=r["id"],
                        day=r["day"],
                        client_id=r["client_id"],
                        custodian=Custodian(r["custodian"]),
                        security_id=r["security_id"],
                        asset_name=r["asset_name"],
                        expected_quantity=r["expected_quantity"],
                        reported_quantity=r["reported_quantity"],
                        resolved=r["resolved"],
                        note=r["note"],
                    )
                )
        return PositionBook(state)

    def save_book(self, book: PositionBook) -> None:
        """Regrava o estado do book. Simples e suficiente para o volume da demo;
        em volume real, gravaríamos só as linhas alteradas."""
        state = book.snapshot()
        with self._conn() as c:
            for table in (book_accounts, book_positions, security_names, reconciliation_breaks):
                c.execute(delete(table))
            if state.initialized:
                c.execute(
                    insert(book_accounts),
                    [{"client_id": k[0], "custodian": k[1].value} for k in sorted(state.initialized)],
                )
            rows = [
                {"client_id": k[0], "custodian": k[1].value, "security_id": sec, "quantity": qty}
                for k, by_sec in state.quantities.items()
                for sec, qty in by_sec.items()
            ]
            if rows:
                c.execute(insert(book_positions), rows)
            if state.names:
                c.execute(
                    insert(security_names), [{"security_id": k, "name": v} for k, v in state.names.items()]
                )
            if state.breaks:
                c.execute(
                    insert(reconciliation_breaks),
                    [
                        {
                            "id": b.id,
                            "seq": i,
                            "day": b.day,
                            "client_id": b.client_id,
                            "custodian": b.custodian.value,
                            "security_id": b.security_id,
                            "asset_name": b.asset_name,
                            "expected_quantity": b.expected_quantity,
                            "reported_quantity": b.reported_quantity,
                            "resolved": b.resolved,
                            "note": b.note,
                        }
                        for i, b in enumerate(state.breaks)
                    ],
                )

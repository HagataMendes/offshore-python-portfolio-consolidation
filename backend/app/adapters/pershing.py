"""Adapter da Pershing: CSV, datas MM/DD/AAAA, ativos identificados pelo ticker."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..domain.models import AssetClass, Custodian, Holding, Transaction, TransactionType, cash_key
from ..reference import ReferenceData, UnknownReferenceError
from .base import FileKind, InvalidFileError, ParsedFile

POSITION_COLUMNS = {"ACCOUNT", "DATE", "SEC_TYPE", "TICKER", "DESCRIPTION", "QTY", "PRICE", "CCY"}
TX_COLUMNS = {"ACCOUNT", "TRADE_DATE", "TXN_TYPE", "TICKER", "QTY", "PRICE", "NET_AMOUNT", "CCY", "REF"}

TX_TYPES = {
    "BUY": TransactionType.BUY,
    "SELL": TransactionType.SELL,
    "DIV": TransactionType.DIVIDEND,
    "DEP": TransactionType.DEPOSIT,
    "WDL": TransactionType.WITHDRAWAL,
    "FEE": TransactionType.FEE,
}


class PershingAdapter:
    custodian = Custodian.PERSHING
    file_format = "CSV"

    def __init__(self, reference: ReferenceData) -> None:
        self.ref = reference

    def matches(self, file_name: str) -> bool:
        return file_name.lower().startswith("pershing_") and file_name.lower().endswith(".csv")

    def parse(self, file_name: str, content: bytes) -> ParsedFile:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        if "transactions" in file_name:
            return self._transactions(rows)
        return self._positions(rows)

    # --- posições -------------------------------------------------------------

    def _positions(self, rows: list[dict[str, str]]) -> ParsedFile:
        _require_columns(rows, POSITION_COLUMNS)
        holdings = [self._holding(r) for r in rows]
        as_of = holdings[0].as_of if holdings else _fail("Arquivo de posições vazio")
        return ParsedFile(self.custodian, FileKind.POSITIONS, as_of, holdings=holdings)

    def _holding(self, r: dict[str, str]) -> Holding:
        client_id = self._client(r["ACCOUNT"])
        currency = r["CCY"].strip()
        if r["SEC_TYPE"] == "CASH":
            security_id, name, ticker, cls = cash_key(currency), "Caixa em dólar", None, AssetClass.CASH
        else:
            sec = self._security(r["TICKER"])
            security_id, name, ticker, cls = sec.isin, sec.name, sec.ticker, sec.asset_class
        return Holding(
            client_id=client_id,
            custodian=self.custodian,
            as_of=_us_date(r["DATE"]),
            security_id=security_id,
            name=name,
            asset_class=cls,
            quantity=_dec(r["QTY"], "QTY"),
            price=_dec(r["PRICE"], "PRICE"),
            currency=currency,
            ticker=ticker,
        )

    # --- movimentações ----------------------------------------------------------

    def _transactions(self, rows: list[dict[str, str]]) -> ParsedFile:
        _require_columns(rows, TX_COLUMNS)
        txs = [self._transaction(r) for r in rows]
        as_of = max(t.trade_date for t in txs) if txs else _fail("Arquivo de movimentações vazio")
        return ParsedFile(self.custodian, FileKind.TRANSACTIONS, as_of, transactions=txs)

    def _transaction(self, r: dict[str, str]) -> Transaction:
        kind = TX_TYPES.get(r["TXN_TYPE"]) or _fail(f"Tipo de movimentação desconhecido: {r['TXN_TYPE']}")
        sec = self._security(r["TICKER"]) if r["TICKER"] else None
        return Transaction(
            id=f"PSH-{r['REF']}",
            client_id=self._client(r["ACCOUNT"]),
            custodian=self.custodian,
            trade_date=_us_date(r["TRADE_DATE"]),
            type=kind,
            amount=_dec(r["NET_AMOUNT"], "NET_AMOUNT"),
            currency=r["CCY"],
            security_id=sec.isin if sec else None,
            quantity=_dec(r["QTY"] or "0", "QTY"),
            price=_dec(r["PRICE"], "PRICE") if r["PRICE"] else None,
            ticker=sec.ticker if sec else None,
        )

    # --- apoio ----------------------------------------------------------------

    def _client(self, account: str) -> str:
        try:
            return self.ref.client_for_account(self.custodian, account)
        except UnknownReferenceError as e:
            raise InvalidFileError(str(e)) from e

    def _security(self, ticker: str):
        try:
            return self.ref.security_by_ticker(ticker)
        except UnknownReferenceError as e:
            raise InvalidFileError(str(e)) from e


def _require_columns(rows: list[dict[str, str]], expected: set[str]) -> None:
    if not rows:
        return
    missing = expected - set(rows[0])
    if missing:
        raise InvalidFileError(f"Colunas ausentes no CSV: {', '.join(sorted(missing))}")


def _us_date(text: str) -> date:
    try:
        return datetime.strptime(text.strip(), "%m/%d/%Y").date()  # 09/28/2026
    except ValueError:
        raise InvalidFileError(f"Data fora do padrão MM/DD/AAAA: {text!r}") from None


def _dec(text: str, column: str) -> Decimal:
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        raise InvalidFileError(f"Valor inválido na coluna {column}: {text!r}") from None


def _fail(message: str):
    raise InvalidFileError(message)

"""Adapter do UBS: JSON, datas ISO, ativos pelo ISIN, renda fixa com preço em %."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from ..domain.models import AssetClass, Custodian, Holding, Transaction, TransactionType, cash_key
from ..reference import ReferenceData, UnknownReferenceError
from .base import FileKind, InvalidFileError, ParsedFile

ASSET_CLASSES = {"BOND": AssetClass.FIXED_INCOME, "EQUITY": AssetClass.EQUITY, "CASH": AssetClass.CASH}

MOVEMENT_KINDS = {
    "SECURITY_PURCHASE": TransactionType.BUY,
    "SECURITY_SALE": TransactionType.SELL,
    "DIVIDEND": TransactionType.DIVIDEND,
    "CASH_DEPOSIT": TransactionType.DEPOSIT,
    "CASH_WITHDRAWAL": TransactionType.WITHDRAWAL,
    "CUSTODY_FEE": TransactionType.FEE,
}

CASH_NAMES = {"USD": "Caixa em dólar", "EUR": "Caixa em euro"}


class UbsAdapter:
    custodian = Custodian.UBS
    file_format = "JSON"

    def __init__(self, reference: ReferenceData) -> None:
        self.ref = reference

    def matches(self, file_name: str) -> bool:
        return file_name.lower().startswith("ubs_") and file_name.lower().endswith(".json")

    def parse(self, file_name: str, content: bytes) -> ParsedFile:
        try:
            doc = json.loads(content)
        except json.JSONDecodeError as e:
            raise InvalidFileError(f"JSON inválido: {e.msg} (linha {e.lineno})") from e
        for required in ("fileType", "asOf", "portfolios"):
            if required not in doc:
                raise InvalidFileError(f'Campo obrigatório "{required}" ausente no arquivo')
        as_of = _iso(doc["asOf"])

        if doc["fileType"] == "POSITIONS":
            holdings = [
                self._holding(p["accountId"], h, as_of)
                for p in doc["portfolios"]
                for h in p.get("holdings", [])
            ]
            return ParsedFile(self.custodian, FileKind.POSITIONS, as_of, holdings=holdings)
        if doc["fileType"] == "TRANSACTIONS":
            txs = [
                self._transaction(p["accountId"], m)
                for p in doc["portfolios"]
                for m in p.get("movements", [])
            ]
            return ParsedFile(self.custodian, FileKind.TRANSACTIONS, as_of, transactions=txs)
        raise InvalidFileError(f"fileType desconhecido: {doc['fileType']}")

    def _holding(self, account: str, h: dict[str, Any], as_of: date) -> Holding:
        cls = ASSET_CLASSES.get(h["assetClass"]) or _fail(f"Classe de ativo desconhecida: {h['assetClass']}")
        currency = h["currency"]
        if cls is AssetClass.CASH:
            security_id, name, ticker = (
                cash_key(currency),
                CASH_NAMES.get(currency, f"Caixa {currency}"),
                None,
            )
        else:
            sec = self.ref.security_by_isin(h["isin"])
            security_id = h["isin"]
            name = sec.name if sec else h["description"]
            ticker = sec.ticker if sec else None
        return Holding(
            client_id=self._client(account),
            custodian=self.custodian,
            as_of=as_of,
            security_id=security_id,
            name=name,
            asset_class=cls,
            quantity=_dec(h["units"], "units"),
            price=_dec(h["px"], "px"),
            currency=currency,
            price_is_percent=h.get("priceUnit") == "PERCENT",
            ticker=ticker,
        )

    def _transaction(self, account: str, m: dict[str, Any]) -> Transaction:
        kind = MOVEMENT_KINDS.get(m["kind"]) or _fail(f"Tipo de movimentação desconhecido: {m['kind']}")
        isin = m.get("isin")
        sec = self.ref.security_by_isin(isin) if isin else None
        return Transaction(
            id=f"UBS-{m['ref']}",
            client_id=self._client(account),
            custodian=self.custodian,
            trade_date=_iso(m["valueDate"]),
            type=kind,
            amount=_dec(m["amount"], "amount"),
            currency=m["currency"],
            security_id=isin,
            quantity=_dec(m.get("units") or "0", "units"),
            price=_dec(m["px"], "px") if m.get("px") else None,
            ticker=(sec.ticker or sec.name) if sec else None,
        )

    def _client(self, account: str) -> str:
        try:
            return self.ref.client_for_account(self.custodian, account)
        except UnknownReferenceError as e:
            raise InvalidFileError(str(e)) from e


def _iso(text: str) -> date:
    try:
        return date.fromisoformat(text)  # 2026-09-28
    except (TypeError, ValueError):
        raise InvalidFileError(f"Data fora do padrão AAAA-MM-DD: {text!r}") from None


def _dec(text: Any, field: str) -> Decimal:
    try:
        return Decimal(str(text))
    except InvalidOperation:
        raise InvalidFileError(f"Valor inválido no campo {field}: {text!r}") from None


def _fail(message: str):
    raise InvalidFileError(message)

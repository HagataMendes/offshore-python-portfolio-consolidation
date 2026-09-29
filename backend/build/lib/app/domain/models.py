"""Modelo de domínio: o "vocabulário" do sistema.

Tudo aqui é Python puro, sem banco de dados, AWS ou FastAPI.
Valores em dinheiro e quantidades usam Decimal, nunca float:
em float, 0.1 + 0.2 dá 0.30000000000000004, o que é inaceitável em finanças.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Custodian(StrEnum):
    PERSHING = "Pershing"
    UBS = "UBS"


class AssetClass(StrEnum):
    EQUITY = "renda_variavel"
    FIXED_INCOME = "renda_fixa"
    CASH = "caixa"


class TransactionType(StrEnum):
    DEPOSIT = "deposito"
    WITHDRAWAL = "saque"
    BUY = "compra"
    SELL = "venda"
    DIVIDEND = "dividendo"
    FEE = "taxa"

    @property
    def is_external_flow(self) -> bool:
        """Depósitos e saques são dinheiro do cliente entrando ou saindo.
        São os únicos eventos que o TWR 'desconta'."""
        return self in (TransactionType.DEPOSIT, TransactionType.WITHDRAWAL)


def cash_key(currency: str) -> str:
    """Identificador do caixa numa moeda: 'CASH:USD', 'CASH:EUR'."""
    return f"CASH:{currency}"


@dataclass(frozen=True)
class Holding:
    """Uma linha de posição, já no formato padrão (depois do adapter)."""

    client_id: str
    custodian: Custodian
    as_of: date
    security_id: str  # ISIN do ativo, ou CASH:<moeda> para caixa
    name: str
    asset_class: AssetClass
    quantity: Decimal
    price: Decimal
    currency: str
    price_is_percent: bool = False  # renda fixa: preço em % do valor de face
    ticker: str | None = None

    @property
    def isin(self) -> str | None:
        return None if self.asset_class is AssetClass.CASH else self.security_id

    @property
    def local_value(self) -> Decimal:
        if self.price_is_percent:
            return self.quantity * self.price / Decimal(100)
        return self.quantity * self.price


@dataclass(frozen=True)
class Transaction:
    """Uma movimentação, já no formato padrão."""

    id: str
    client_id: str
    custodian: Custodian
    trade_date: date
    type: TransactionType
    amount: Decimal  # efeito no caixa, na moeda da transação: + entra, − sai
    currency: str
    security_id: str | None = None
    quantity: Decimal = Decimal(0)
    price: Decimal | None = None
    ticker: str | None = None


@dataclass(frozen=True)
class ValuationPoint:
    """Valor da carteira num dia, em dólar."""

    day: date
    value: Decimal
    external_flow: Decimal = Decimal(0)  # depósito (+) ou saque (−) no início do dia


@dataclass(frozen=True)
class SubPeriod:
    start: date
    end: date
    ret: Decimal
    flow_before: Decimal


@dataclass(frozen=True)
class ReconciliationBreak:
    id: str
    day: date
    client_id: str
    custodian: Custodian
    security_id: str
    asset_name: str
    expected_quantity: Decimal
    reported_quantity: Decimal
    resolved: bool = False
    note: str = ""


@dataclass
class Client:
    id: str
    name: str
    full_name: str
    account: str
    risk_profile: str
    advisor: str
    base_currency: str = "USD"
    custodian_accounts: dict[Custodian, str] = field(default_factory=dict)

    @property
    def custodians(self) -> list[Custodian]:
        return list(self.custodian_accounts)

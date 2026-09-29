"""Extrato consolidado: saldo inicial → depósitos → saques → resultado → saldo final."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import Transaction, TransactionType, ValuationPoint
from .performance import time_weighted_return
from .text import fmt_money, fmt_number
from .valuation import round_money


@dataclass(frozen=True)
class StatementLine:
    transaction: Transaction
    amount_usd: Decimal
    description: str


@dataclass(frozen=True)
class Statement:
    period_start: date
    period_end: date
    opening_balance: Decimal
    deposits: Decimal
    withdrawals: Decimal  # negativo
    investment_result: Decimal
    closing_balance: Decimal
    twr: Decimal
    lines: list[StatementLine]


def describe(tx: Transaction) -> str:
    """Texto do lançamento no extrato, em português."""
    asset = tx.ticker or tx.security_id or ""
    price = fmt_money(tx.price, tx.currency) if tx.price is not None else ""
    match tx.type:
        case TransactionType.DEPOSIT:
            return "Depósito recebido"
        case TransactionType.WITHDRAWAL:
            return "Saque enviado"
        case TransactionType.BUY:
            return f"Compra de {fmt_number(tx.quantity)} {asset} a {price}"
        case TransactionType.SELL:
            if tx.price is not None and tx.quantity >= 1000:  # renda fixa: preço em %
                return f"Venda de {fmt_number(tx.quantity)} de face de {asset} a {fmt_number(tx.price)}%"
            return f"Venda de {fmt_number(tx.quantity)} {asset} a {price}"
        case TransactionType.DIVIDEND:
            return f"Dividendo {asset}".strip()
        case TransactionType.FEE:
            return "Taxa de custódia"


def build_statement(
    history: Sequence[ValuationPoint],
    transactions: Sequence[Transaction],
    to_usd: Callable[[Transaction], Decimal],
) -> Statement:
    """`history` começa no fechamento do período anterior (o saldo inicial)."""
    opening = history[0].value
    closing = history[-1].value
    lines = [
        StatementLine(tx, round_money(to_usd(tx)), describe(tx))
        for tx in sorted(transactions, key=lambda t: (t.trade_date, t.id))
    ]
    deposits = sum(
        (ln.amount_usd for ln in lines if ln.transaction.type is TransactionType.DEPOSIT), Decimal(0)
    )
    withdrawals = sum(
        (ln.amount_usd for ln in lines if ln.transaction.type is TransactionType.WITHDRAWAL), Decimal(0)
    )
    return Statement(
        period_start=history[0].day,
        period_end=history[-1].day,
        opening_balance=opening,
        deposits=deposits,
        withdrawals=withdrawals,
        # Resultado = o que o mercado deu ou tirou, sem o efeito de depósitos e saques.
        investment_result=closing - opening - deposits - withdrawals,
        closing_balance=closing,
        twr=time_weighted_return(history),
        lines=lines,
    )

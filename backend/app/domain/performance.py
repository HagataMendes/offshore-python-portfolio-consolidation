"""Cálculo de rentabilidade.

Convenção: o fluxo externo (depósito ou saque) entra no INÍCIO do dia,
antes de o mercado se mexer:

    valor_hoje = (valor_ontem + fluxo_hoje) × (1 + retorno_do_dia)

Então o retorno do dia é recuperado a partir dos valores:

    retorno_do_dia = valor_hoje / (valor_ontem + fluxo_hoje) − 1
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from itertools import pairwise

from .models import SubPeriod, ValuationPoint

ONE = Decimal(1)


def daily_return(previous: ValuationPoint, current: ValuationPoint) -> Decimal:
    base = previous.value + current.external_flow
    if base == 0:
        raise ValueError(f"Carteira zerada em {current.day}: retorno do dia indefinido")
    return current.value / base - ONE


def compound(returns: Iterable[Decimal]) -> Decimal:
    """Encadeia retornos: (1 + r1) × (1 + r2) × ... − 1."""
    acc = ONE
    for r in returns:
        acc *= ONE + r
    return acc - ONE


def time_weighted_return(history: Sequence[ValuationPoint]) -> Decimal:
    """TWR: mede a qualidade dos investimentos sem ser distorcido por
    depósitos e saques do cliente. É o padrão de mercado (GIPS)."""
    if len(history) < 2:
        return Decimal(0)
    return compound(daily_return(a, b) for a, b in pairwise(history))


def naive_return(history: Sequence[ValuationPoint]) -> Decimal:
    """Valor final ÷ valor inicial − 1. Fica errado quando há depósitos ou saques:
    serve só para mostrar a diferença para o TWR."""
    return history[-1].value / history[0].value - ONE


def split_sub_periods(history: Sequence[ValuationPoint]) -> list[SubPeriod]:
    """Quebra o período em pedaços, cortando em cada depósito ou saque.
    O TWR é o produto dos retornos desses pedaços."""
    periods: list[SubPeriod] = []
    chunk: list[Decimal] = []
    chunk_start = history[0].day
    flow_before = Decimal(0)

    for previous, current in pairwise(history):
        if current.external_flow != 0 and chunk:
            periods.append(SubPeriod(chunk_start, previous.day, compound(chunk), flow_before))
            chunk = []
            chunk_start = previous.day
        if not chunk:
            flow_before = current.external_flow
        chunk.append(daily_return(previous, current))

    if chunk:
        periods.append(SubPeriod(chunk_start, history[-1].day, compound(chunk), flow_before))
    return periods

"""Valorização: transforma posições (quantidade × preço × câmbio) em dólares."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from .models import Holding

CENT = Decimal("0.01")

# Função que devolve a cotação de uma moeda para USD numa data.
FxLookup = Callable[[str, date], Decimal]


def round_money(value: Decimal) -> Decimal:
    """Arredondamento bancário (meio para o par), padrão em sistemas financeiros."""
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def market_value_usd(holding: Holding, fx: FxLookup) -> Decimal:
    return round_money(holding.local_value * fx(holding.currency, holding.as_of))


def total_usd(holdings: Iterable[Holding], fx: FxLookup) -> Decimal:
    return sum((market_value_usd(h, fx) for h in holdings), Decimal(0))

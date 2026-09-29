"""Formatação de números no padrão brasileiro para textos gerados pelo sistema."""

from decimal import Decimal


def fmt_number(value: Decimal, decimals: int = 2, strip_zeros: bool = True) -> str:
    """Decimal('16365.5') → '16.365,50'; com strip_zeros, Decimal('30') → '30'."""
    text = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if strip_zeros and decimals and text.endswith("," + "0" * decimals):
        text = text[: -(decimals + 1)]
    return text


def fmt_money(value: Decimal, currency: str) -> str:
    symbol = {"USD": "US$", "EUR": "€", "BRL": "R$"}.get(currency, currency)
    return f"{symbol} {fmt_number(value, 2, strip_zeros=False)}"

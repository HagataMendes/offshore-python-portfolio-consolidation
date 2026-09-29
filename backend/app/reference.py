"""Dados de referência: cadastro de clientes, cadastro de ativos, câmbio e histórico.

No mundo real isso viria de outros sistemas (cadastro, market data).
Aqui vem de arquivos em sample_data/reference e sample_data/market.
"""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from .domain.models import AssetClass, Client, Custodian


@dataclass(frozen=True)
class Security:
    isin: str
    ticker: str | None
    name: str
    asset_class: AssetClass


class UnknownReferenceError(LookupError):
    pass


class ReferenceData:
    def __init__(
        self,
        clients: list[Client],
        securities: list[Security],
        fx_rates: dict[str, dict[date, Decimal]],
        monthly_returns: dict[str, dict[str, Decimal]],
    ) -> None:
        self.clients = {c.id: c for c in clients}
        self._accounts = {
            (custodian, account): c.id for c in clients for custodian, account in c.custodian_accounts.items()
        }
        self._by_isin = {s.isin: s for s in securities}
        self._by_ticker = {s.ticker: s for s in securities if s.ticker}
        self._fx = {pair: dict(sorted(rates.items())) for pair, rates in fx_rates.items()}
        self.monthly_returns = monthly_returns

    # --- clientes -----------------------------------------------------------

    def client_for_account(self, custodian: Custodian, account: str) -> str:
        try:
            return self._accounts[(custodian, account)]
        except KeyError:
            raise UnknownReferenceError(f"Conta {account} do {custodian} não está cadastrada") from None

    # --- ativos -------------------------------------------------------------

    def security_by_ticker(self, ticker: str) -> Security:
        try:
            return self._by_ticker[ticker]
        except KeyError:
            raise UnknownReferenceError(f"Ticker {ticker} não está no cadastro de ativos") from None

    def security_by_isin(self, isin: str) -> Security | None:
        return self._by_isin.get(isin)

    # --- câmbio -------------------------------------------------------------

    def fx_to_usd(self, currency: str, day: date) -> Decimal:
        """Cotação da moeda em dólares. Usa a última cotação disponível até a data."""
        if currency == "USD":
            return Decimal(1)
        rates = self._fx.get(f"{currency}USD")
        if not rates:
            raise UnknownReferenceError(f"Sem cotação para {currency}/USD")
        days = list(rates)
        i = bisect_right(days, day)
        if i == 0:
            raise UnknownReferenceError(f"Sem cotação de {currency}/USD até {day}")
        return rates[days[i - 1]]

    # --- carga --------------------------------------------------------------

    @classmethod
    def load(cls, root: Path) -> ReferenceData:
        raw_clients = json.loads((root / "reference" / "clients.json").read_text())
        clients = [
            Client(
                id=c["id"],
                name=c["name"],
                full_name=c["full_name"],
                account=c["account"],
                risk_profile=c["risk_profile"],
                advisor=c["advisor"],
                base_currency=c["base_currency"],
                custodian_accounts={Custodian(k): v for k, v in c["custodian_accounts"].items()},
            )
            for c in raw_clients
        ]
        with open(root / "reference" / "securities.csv") as f:
            securities = [
                Security(r["isin"], r["ticker"] or None, r["name"], AssetClass(r["asset_class"]))
                for r in csv.DictReader(f)
            ]
        fx: dict[str, dict[date, Decimal]] = {}
        for path in (root / "market").glob("fx_*.csv"):
            with open(path) as f:
                for r in csv.DictReader(f):
                    fx.setdefault(r["pair"], {})[date.fromisoformat(r["date"])] = Decimal(r["rate"])
        monthly: dict[str, dict[str, Decimal]] = {}
        with open(root / "reference" / "monthly_returns.csv") as f:
            for r in csv.DictReader(f):
                monthly.setdefault(r["client_id"], {})[r["month"]] = Decimal(r["twr"])
        return cls(clients, securities, fx, monthly)

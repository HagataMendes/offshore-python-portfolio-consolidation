"""Casos de uso: o que a API oferece, montado a partir do domínio e do repositório."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .domain.models import Client, Custodian, Holding, SubPeriod, Transaction, ValuationPoint
from .domain.performance import compound, naive_return, split_sub_periods, time_weighted_return
from .domain.statement import Statement, build_statement
from .domain.valuation import FxLookup, market_value_usd, round_money, total_usd
from .ports import PortfolioRepository
from .reference import ReferenceData


class NotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class PositionView:
    holding: Holding
    fx_rate: Decimal
    market_value_usd: Decimal


@dataclass(frozen=True)
class PortfolioView:
    client: Client
    as_of: date
    total_usd: Decimal
    positions: list[PositionView]
    history: list[ValuationPoint]


@dataclass(frozen=True)
class PerformanceView:
    client: Client
    period_start: date
    period_end: date
    twr: Decimal
    naive_return: Decimal
    sub_periods: list[SubPeriod]
    monthly: list[tuple[str, Decimal]]
    ytd_twr: Decimal


@dataclass(frozen=True)
class _ClientData:
    """Tudo do cliente, lido do repositório uma vez por requisição."""

    holdings: dict[Custodian, dict[date, list[Holding]]]
    transactions: list[Transaction]

    @property
    def days(self) -> list[date]:
        return sorted({d for by_day in self.holdings.values() for d in by_day})

    def holdings_on(self, day: date) -> list[Holding]:
        """Posição consolidada: último arquivo de cada custodiante até a data."""
        result: list[Holding] = []
        for by_day in self.holdings.values():
            days = sorted(by_day)
            i = bisect_right(days, day)
            if i:
                result.extend(by_day[days[i - 1]])
        return result

    def transactions_between(self, after: date, until: date) -> list[Transaction]:
        return [t for t in self.transactions if after < t.trade_date <= until]

    def base_day_before(self, month_start: date) -> date:
        """Último dia com dados antes do mês: é o saldo inicial do mês."""
        before = [d for d in self.days if d < month_start]
        if not before:
            raise NotFoundError(f"Sem fechamento anterior a {month_start}")
        return before[-1]

    def last_day_of(self, month: str) -> date:
        in_month = [d for d in self.days if f"{d:%Y-%m}" == month]
        if not in_month:
            raise NotFoundError(f"Sem dados de {month}")
        return in_month[-1]


class PortfolioService:
    def __init__(self, repository: PortfolioRepository, reference: ReferenceData) -> None:
        self.repo = repository
        self.ref = reference

    # --- apoio -----------------------------------------------------------------

    def client(self, client_id: str) -> Client:
        try:
            return self.ref.clients[client_id]
        except KeyError:
            raise NotFoundError(f"Cliente {client_id} não encontrado") from None

    def _load(self, client_id: str) -> _ClientData:
        client = self.client(client_id)
        return _ClientData(
            holdings={c: self.repo.holdings_by_day(client_id, c) for c in client.custodians},
            transactions=self.repo.transactions_for(client_id),
        )

    @property
    def _fx(self) -> FxLookup:
        return self.ref.fx_to_usd

    def tx_to_usd(self, tx: Transaction) -> Decimal:
        return tx.amount * self._fx(tx.currency, tx.trade_date)

    def _history(self, data: _ClientData, start: date, end: date) -> list[ValuationPoint]:
        """Valor da carteira em cada dia útil, com depósitos e saques do dia."""
        days = [d for d in data.days if start <= d <= end]
        if len(days) < 2:
            raise NotFoundError(f"Sem dados suficientes entre {start} e {end}")
        flows: dict[date, Decimal] = {}
        for tx in data.transactions_between(days[0], days[-1]):
            if tx.type.is_external_flow:
                flows[tx.trade_date] = flows.get(tx.trade_date, Decimal(0)) + round_money(self.tx_to_usd(tx))
        return [
            ValuationPoint(
                day=d,
                value=total_usd(data.holdings_on(d), self._fx),
                external_flow=flows.get(d, Decimal(0)) if i else Decimal(0),
            )
            for i, d in enumerate(days)
        ]

    # --- casos de uso -----------------------------------------------------------

    def portfolio(self, client_id: str, as_of: date) -> PortfolioView:
        client, data = self.client(client_id), self._load(client_id)
        positions = [
            PositionView(h, self._fx(h.currency, h.as_of), market_value_usd(h, self._fx))
            for h in data.holdings_on(as_of)
        ]
        if not positions:
            raise NotFoundError(f"Sem posições para {client_id} em {as_of}")
        base = data.base_day_before(as_of.replace(day=1))
        return PortfolioView(
            client=client,
            as_of=as_of,
            total_usd=sum((p.market_value_usd for p in positions), Decimal(0)),
            positions=positions,
            history=self._history(data, base, as_of),
        )

    def statement(self, client_id: str, month: str) -> tuple[Client, Statement]:
        client, data = self.client(client_id), self._load(client_id)
        base = data.base_day_before(date.fromisoformat(f"{month}-01"))
        last = data.last_day_of(month)
        history = self._history(data, base, last)
        txs = data.transactions_between(base, last)
        return client, build_statement(history, txs, self.tx_to_usd)

    def performance(self, client_id: str, start: date, end: date) -> PerformanceView:
        client, data = self.client(client_id), self._load(client_id)
        history = self._history(data, start, end)

        # Meses: histórico importado de outro sistema + meses calculados a partir dos arquivos.
        monthly = dict(self.ref.monthly_returns.get(client_id, {}))
        for month in sorted({f"{d:%Y-%m}" for d in data.days}):
            try:
                base = data.base_day_before(date.fromisoformat(f"{month}-01"))
            except NotFoundError:
                continue
            monthly[month] = time_weighted_return(self._history(data, base, data.last_day_of(month)))

        months = sorted(m for m in monthly if m.startswith(str(end.year)) and m <= f"{end:%Y-%m}")
        return PerformanceView(
            client=client,
            period_start=history[0].day,
            period_end=history[-1].day,
            twr=time_weighted_return(history),
            naive_return=naive_return(history),
            sub_periods=split_sub_periods(history),
            monthly=[(m, monthly[m]) for m in months],
            ytd_twr=compound(monthly[m] for m in months),
        )

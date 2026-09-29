"""Formato do JSON que a API devolve. Espelha src/types.ts do front.

Internamente tudo é Decimal; na saída viram números JSON (valores com 2 casas).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ..domain.models import Client, SubPeriod, ValuationPoint
from ..domain.statement import Statement
from ..ingestion.records import IngestionRecord
from ..services import PerformanceView, PortfolioView


def money(v: Decimal) -> float:
    return float(round(v, 2))


def rate(v: Decimal) -> float:
    return float(round(v, 8))


class ClientOut(BaseModel):
    id: str
    name: str
    full_name: str
    account: str
    risk_profile: str
    advisor: str
    base_currency: str
    custodians: list[str]

    @classmethod
    def of(cls, c: Client) -> ClientOut:
        return cls(
            id=c.id,
            name=c.name,
            full_name=c.full_name,
            account=c.account,
            risk_profile=c.risk_profile,
            advisor=c.advisor,
            base_currency=c.base_currency,
            custodians=[x.value for x in c.custodians],
        )


class PositionOut(BaseModel):
    isin: str | None
    ticker: str | None
    name: str
    asset_class: Literal["renda_variavel", "renda_fixa", "caixa"]
    custodian: str
    quantity: float
    price: float
    currency: str
    fx_rate: float
    market_value_usd: float


class ValuationPointOut(BaseModel):
    date: date
    value_usd: float
    daily_return: float
    external_flow_usd: float


def history_out(history: list[ValuationPoint]) -> list[ValuationPointOut]:
    out = []
    for i, p in enumerate(history):
        prev = history[i - 1] if i else None
        r = p.value / (prev.value + p.external_flow) - 1 if prev else Decimal(0)
        out.append(
            ValuationPointOut(
                date=p.day,
                value_usd=money(p.value),
                daily_return=rate(r),
                external_flow_usd=money(p.external_flow),
            )
        )
    return out


class PortfolioOut(BaseModel):
    client: ClientOut
    as_of: date
    total_usd: float
    positions: list[PositionOut]
    history: list[ValuationPointOut]

    @classmethod
    def of(cls, v: PortfolioView) -> PortfolioOut:
        return cls(
            client=ClientOut.of(v.client),
            as_of=v.as_of,
            total_usd=money(v.total_usd),
            positions=[
                PositionOut(
                    isin=p.holding.isin,
                    ticker=p.holding.ticker,
                    name=p.holding.name,
                    asset_class=p.holding.asset_class.value,
                    custodian=p.holding.custodian.value,
                    quantity=float(p.holding.quantity),
                    price=float(p.holding.price),
                    currency=p.holding.currency,
                    fx_rate=float(p.fx_rate),
                    market_value_usd=money(p.market_value_usd),
                )
                for p in v.positions
            ],
            history=history_out(v.history),
        )


class TransactionOut(BaseModel):
    id: str
    date: date
    custodian: str
    type: Literal["deposito", "saque", "compra", "venda", "dividendo", "taxa"]
    description: str
    amount_usd: float
    is_external_flow: bool


class StatementOut(BaseModel):
    client: ClientOut
    period_start: date
    period_end: date
    opening_balance_usd: float
    deposits_usd: float
    withdrawals_usd: float
    investment_result_usd: float
    closing_balance_usd: float
    twr: float
    transactions: list[TransactionOut]

    @classmethod
    def of(cls, client: Client, s: Statement) -> StatementOut:
        return cls(
            client=ClientOut.of(client),
            period_start=s.period_start,
            period_end=s.period_end,
            opening_balance_usd=money(s.opening_balance),
            deposits_usd=money(s.deposits),
            withdrawals_usd=money(s.withdrawals),
            investment_result_usd=money(s.investment_result),
            closing_balance_usd=money(s.closing_balance),
            twr=rate(s.twr),
            transactions=[
                TransactionOut(
                    id=ln.transaction.id,
                    date=ln.transaction.trade_date,
                    custodian=ln.transaction.custodian.value,
                    type=ln.transaction.type.value,
                    description=ln.description,
                    amount_usd=money(ln.amount_usd),
                    is_external_flow=ln.transaction.type.is_external_flow,
                )
                for ln in s.lines
            ],
        )


class SubPeriodOut(BaseModel):
    start: date
    end: date
    # "return" é palavra reservada em Python: o campo se chama ret, mas o JSON sai como "return".
    ret: float = Field(serialization_alias="return")
    flow_before_usd: float

    @classmethod
    def of(cls, sp: SubPeriod) -> SubPeriodOut:
        return cls(start=sp.start, end=sp.end, ret=rate(sp.ret), flow_before_usd=money(sp.flow_before))


class MonthlyReturnOut(BaseModel):
    month: str
    twr: float


class PerformanceOut(BaseModel):
    client: ClientOut
    period_start: date
    period_end: date
    twr: float
    naive_return: float
    sub_periods: list[SubPeriodOut]
    monthly: list[MonthlyReturnOut]
    ytd_twr: float

    @classmethod
    def of(cls, v: PerformanceView) -> PerformanceOut:
        return cls(
            client=ClientOut.of(v.client),
            period_start=v.period_start,
            period_end=v.period_end,
            twr=rate(v.twr),
            naive_return=rate(v.naive_return),
            sub_periods=[SubPeriodOut.of(sp) for sp in v.sub_periods],
            monthly=[MonthlyReturnOut(month=m, twr=rate(r)) for m, r in v.monthly],
            ytd_twr=rate(v.ytd_twr),
        )


class IngestedFileOut(BaseModel):
    id: str
    file_name: str
    custodian: str | None
    format: str
    received_at: datetime
    status: Literal["processado", "duplicado", "erro_dlq", "processando"]
    records: int
    duration_ms: int | None
    correlation_id: str
    error: str | None

    @classmethod
    def of(cls, r: IngestionRecord) -> IngestedFileOut:
        return cls(
            id=r.id,
            file_name=r.file_name,
            custodian=r.custodian.value if r.custodian else None,
            format=r.file_format,
            received_at=r.received_at,
            status=r.status.value,
            records=r.records,
            duration_ms=r.duration_ms,
            correlation_id=r.correlation_id,
            error=r.error,
        )


class BreakOut(BaseModel):
    id: str
    date: date
    client_id: str
    custodian: str
    asset: str
    expected_quantity: float
    reported_quantity: float
    status: Literal["aberta", "resolvida"]
    note: str


# --- Análise geral (pandas) -------------------------------------------------------


class AllocationItemOut(BaseModel):
    key: str
    label: str
    value_usd: float
    weight: float


class ClientAnalyticsOut(BaseModel):
    client_id: str
    name: str
    full_name: str
    risk_profile: str
    aum_usd: float
    net_flows_usd: float
    twr: float
    volatility_annual: float
    max_drawdown: float
    sharpe: float | None
    best_day: date
    best_day_return: float
    worst_day: date
    worst_day_return: float
    positive_days: int
    days: int
    top_position: str
    top_weight: float
    hhi: float
    effective_positions: float
    positions: int
    foreign_currency_weight: float
    shock: float
    shock_impact_usd: float
    shock_impact_pct: float
    by_asset_class: list[AllocationItemOut]
    by_currency: list[AllocationItemOut]


class ContributionOut(BaseModel):
    label: str
    contribution: float


class DrawdownPointOut(BaseModel):
    date: date
    twr_index: float
    drawdown: float


class AnalyticsOverviewOut(BaseModel):
    as_of: date
    period_start: date
    total_aum_usd: float
    risk_free_annual: float
    clients: list[ClientAnalyticsOut]
    allocation: dict[str, list[AllocationItemOut]]
    contributions: dict[str, list[ContributionOut]]
    drawdown: dict[str, list[DrawdownPointOut]]

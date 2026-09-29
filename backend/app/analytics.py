"""Análise geral das carteiras com pandas.

O resto do sistema é "contábil": cada centavo em Decimal, uma posição por vez.
Aqui o objetivo é outro: olhar a carteira inteira de uma vez, como uma tabela, e
responder perguntas de gestão:

- Quanto a carteira oscila (volatilidade) e qual foi a pior queda (drawdown)?
- O risco compensou o retorno (índice de Sharpe)?
- A carteira depende demais de um ativo (concentração)?
- Quanto está exposto a outras moedas, e o que acontece se o euro cair?
- Quais ativos puxaram o resultado do mês para cima ou para baixo?

Para análise, float é aceitável (métricas estatísticas, não saldos). Os saldos
oficiais continuam vindo do domínio em Decimal, e os testes conferem que o TWR
calculado aqui com pandas bate com o de lá.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .domain.models import AssetClass
from .ports import PortfolioRepository
from .reference import ReferenceData

TRADING_DAYS = 252
RISK_FREE_ANNUAL = 0.045  # taxa livre de risco ilustrativa (T-Bill americano de curto prazo)
FX_SHOCK = -0.10  # cenário: moedas estrangeiras caem 10% contra o dólar

CLASS_LABEL = {
    AssetClass.EQUITY.value: "Renda variável",
    AssetClass.FIXED_INCOME.value: "Renda fixa",
    AssetClass.CASH.value: "Caixa",
}


# --- 1. Montagem dos DataFrames --------------------------------------------------


def holdings_frame(repo: PortfolioRepository, ref: ReferenceData, client_ids: list[str]) -> pd.DataFrame:
    """Uma linha por (cliente, custodiante, dia do arquivo, ativo), já valorizada em dólar."""
    rows = [
        {
            "client_id": h.client_id,
            "custodian": h.custodian.value,
            "file_date": pd.Timestamp(h.as_of),
            "security_id": h.security_id,
            "name": h.name,
            "label": h.ticker or h.name,
            "asset_class": h.asset_class.value,
            "currency": h.currency,
            "quantity": float(h.quantity),
            "price": float(h.price),
            "price_factor": 0.01 if h.price_is_percent else 1.0,  # renda fixa cotada em %
        }
        for client_id in client_ids
        for custodian in ref.clients[client_id].custodians
        for day_holdings in repo.holdings_by_day(client_id, custodian).values()
        for h in day_holdings
    ]
    return pd.DataFrame(rows)


def daily_panel(holdings: pd.DataFrame, ref: ReferenceData) -> pd.DataFrame:
    """Posição de cada cliente em cada dia útil, somando todos os custodiantes.

    Se um custodiante não mandou arquivo num dia, vale o último arquivo dele
    (merge_asof = "o registro mais recente até esta data").
    """
    days = holdings[["client_id", "file_date"]].drop_duplicates().rename(columns={"file_date": "day"})
    accounts = holdings[["client_id", "custodian"]].drop_duplicates()
    calendar = days.merge(accounts, on="client_id").sort_values("day")

    files = holdings[["client_id", "custodian", "file_date"]].drop_duplicates().sort_values("file_date")
    latest = pd.merge_asof(
        calendar,
        files,
        left_on="day",
        right_on="file_date",
        by=["client_id", "custodian"],
        direction="backward",
    ).dropna(subset=["file_date"])
    panel = latest.merge(holdings, on=["client_id", "custodian", "file_date"])

    # Câmbio de cada moeda em cada dia (USD = 1).
    pairs = panel[["currency", "day"]].drop_duplicates()
    pairs["fx"] = [
        float(ref.fx_to_usd(c, d.date())) for c, d in zip(pairs["currency"], pairs["day"], strict=True)
    ]
    panel = panel.merge(pairs, on=["currency", "day"])

    panel["value_usd"] = panel["quantity"] * panel["price"] * panel["price_factor"] * panel["fx"]
    # Preço em dólar por unidade: base do retorno de cada ativo (inclui a variação do câmbio).
    panel["unit_price_usd"] = panel["price"] * panel["price_factor"] * panel["fx"]
    return panel.sort_values(["client_id", "day", "security_id"]).reset_index(drop=True)


def flows_frame(repo: PortfolioRepository, ref: ReferenceData, client_ids: list[str]) -> pd.DataFrame:
    """Depósitos (+) e saques (−) em dólar, por cliente e dia."""
    rows = [
        {
            "client_id": t.client_id,
            "day": pd.Timestamp(t.trade_date),
            "flow_usd": float(t.amount * ref.fx_to_usd(t.currency, t.trade_date)),
        }
        for client_id in client_ids
        for t in repo.transactions_for(client_id)
        if t.type.is_external_flow
    ]
    if not rows:
        return pd.DataFrame(columns=["client_id", "day", "flow_usd"])
    return pd.DataFrame(rows).groupby(["client_id", "day"], as_index=False)["flow_usd"].sum()


# --- 2. Séries diárias e métricas de risco -------------------------------------------


def daily_returns(panel: pd.DataFrame, flows: pd.DataFrame) -> pd.DataFrame:
    """Valor, fluxo e retorno diário de cada cliente (colunas: client_id, day, value, flow, ret)."""
    values = panel.groupby(["client_id", "day"], as_index=False)["value_usd"].sum()
    df = values.merge(flows, on=["client_id", "day"], how="left").fillna({"flow_usd": 0.0})
    df = df.sort_values(["client_id", "day"])
    prev = df.groupby("client_id")["value_usd"].shift(1)
    # Mesma convenção do domínio: o fluxo entra no início do dia.
    df["ret"] = df["value_usd"] / (prev + df["flow_usd"]) - 1
    return df.reset_index(drop=True)


def risk_metrics(returns: pd.Series) -> dict:
    """Métricas a partir dos retornos diários de um cliente (sem o primeiro dia, que é a base)."""
    r = returns.dropna()
    growth = (1 + r).cumprod()
    drawdown = growth / growth.cummax() - 1
    vol = r.std(ddof=1) * np.sqrt(TRADING_DAYS)
    annual_mean = r.mean() * TRADING_DAYS
    return {
        "twr": float(growth.iloc[-1] - 1),
        "volatility_annual": float(vol),
        "max_drawdown": float(drawdown.min()),
        "sharpe": float((annual_mean - RISK_FREE_ANNUAL) / vol) if vol > 0 else None,
        "best_day": r.idxmax(),
        "best_day_return": float(r.max()),
        "worst_day": r.idxmin(),
        "worst_day_return": float(r.min()),
        "positive_days": int((r > 0).sum()),
        "days": int(r.size),
    }


def drawdown_series(df: pd.DataFrame) -> pd.DataFrame:
    """Índice de crescimento (TWR acumulado) e distância até o topo, dia a dia."""
    out = df[["client_id", "day"]].copy()
    growth = df.groupby("client_id")["ret"].transform(lambda r: (1 + r.fillna(0)).cumprod())
    out["twr_index"] = growth
    out["drawdown"] = growth / growth.groupby(df["client_id"]).cummax() - 1
    return out


# --- 3. Composição da carteira no fim do período --------------------------------------


def allocation(snapshot: pd.DataFrame, by: str) -> pd.DataFrame:
    """Quanto da carteira está em cada grupo (classe, moeda, custodiante)."""
    out = snapshot.groupby(by, as_index=False)["value_usd"].sum().sort_values("value_usd", ascending=False)
    out["weight"] = out["value_usd"] / out["value_usd"].sum()
    return out.rename(columns={by: "key"})


def concentration(snapshot: pd.DataFrame) -> dict:
    """HHI = soma dos pesos ao quadrado. 1/HHI = "número efetivo de ativos".
    Uma carteira com 4 ativos de 25% cada tem HHI 0,25 e 4 ativos efetivos."""
    by_asset = snapshot.groupby("label")["value_usd"].sum()
    w = by_asset / by_asset.sum()
    hhi = float((w**2).sum())
    return {
        "top_position": str(w.idxmax()),
        "top_weight": float(w.max()),
        "hhi": hhi,
        "effective_positions": 1 / hhi,
        "positions": int(w.size),
    }


def fx_exposure(snapshot: pd.DataFrame) -> dict:
    total = snapshot["value_usd"].sum()
    foreign = snapshot.loc[snapshot["currency"] != "USD", "value_usd"].sum()
    return {
        "foreign_currency_weight": float(foreign / total),
        "shock": FX_SHOCK,
        "shock_impact_usd": float(foreign * FX_SHOCK),
        "shock_impact_pct": float(foreign * FX_SHOCK / total),
    }


# --- 4. Contribuição de cada ativo para o resultado -------------------------------------


def contributions(panel: pd.DataFrame, df: pd.DataFrame, client_id: str) -> pd.DataFrame:
    """Quanto cada ativo contribuiu para o TWR do período.

    contribuição do ativo = Σ (peso do ativo ontem × retorno do ativo hoje)

    O retorno do ativo vem do preço em dólar (preço × câmbio), então compras e vendas
    não contam como ganho. O que sobra para fechar o TWR (dividendos, taxas, efeito
    dos juros compostos) aparece numa linha "Outros efeitos".
    """
    p = panel[panel["client_id"] == client_id]
    wide_value = p.pivot_table(index="day", columns="label", values="value_usd", aggfunc="sum").fillna(0.0)
    wide_price = p.pivot_table(index="day", columns="label", values="unit_price_usd", aggfunc="mean")
    asset_ret = wide_price.pct_change(fill_method=None).fillna(0.0)

    c = df[df["client_id"] == client_id].set_index("day")
    base = c["value_usd"].shift(1) + c["flow_usd"]  # patrimônio no início de cada dia
    weights = wide_value.shift(1).div(base, axis=0)
    contrib = (weights * asset_ret).iloc[1:].sum()

    twr = float((1 + c["ret"].dropna()).prod() - 1)
    out = pd.DataFrame({"label": contrib.index, "contribution": contrib.to_numpy()})
    out = out[out["contribution"].abs() > 1e-7].sort_values("contribution", ascending=False)
    residual = pd.DataFrame({"label": ["Outros efeitos"], "contribution": [twr - out["contribution"].sum()]})
    return pd.concat([out, residual], ignore_index=True)


# --- 5. Visão geral ---------------------------------------------------------------------


@dataclass(frozen=True)
class Overview:
    as_of: date
    period_start: date
    total_aum_usd: float
    clients: list[dict]
    allocation: dict[str, list[dict]]
    contributions: dict[str, list[dict]]
    drawdown: dict[str, list[dict]]


def _records(df: pd.DataFrame, label_map: dict | None = None) -> list[dict]:
    out = []
    for row in df.itertuples(index=False):
        key = str(row.key)
        out.append(
            {
                "key": key,
                "label": (label_map or {}).get(key, key),
                "value_usd": round(float(row.value_usd), 2),
                "weight": float(row.weight),
            }
        )
    return out


def build_overview(repo: PortfolioRepository, ref: ReferenceData, start: date, end: date) -> Overview:
    client_ids = list(ref.clients)
    holdings = holdings_frame(repo, ref, client_ids)
    if holdings.empty:
        raise LookupError("Sem posições para analisar")
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    panel = daily_panel(holdings, ref)
    panel = panel[(panel["day"] >= start_ts) & (panel["day"] <= end_ts)]
    df = daily_returns(panel, flows_frame(repo, ref, client_ids))
    last_day = panel["day"].max()
    snapshot = panel[panel["day"] == last_day]

    clients = []
    for client_id in client_ids:
        c = df[df["client_id"] == client_id]
        client = ref.clients[client_id]
        snap = snapshot[snapshot["client_id"] == client_id]
        m = risk_metrics(c.set_index("day")["ret"])
        clients.append(
            {
                "client_id": client_id,
                "name": client.name,
                "full_name": client.full_name,
                "risk_profile": client.risk_profile,
                "aum_usd": round(float(snap["value_usd"].sum()), 2),
                "net_flows_usd": round(float(c["flow_usd"].sum()), 2),
                **{k: v for k, v in m.items() if k not in {"best_day", "worst_day"}},
                "best_day": m["best_day"].date().isoformat(),
                "worst_day": m["worst_day"].date().isoformat(),
                **concentration(snap),
                **fx_exposure(snap),
                "by_asset_class": _records(allocation(snap, "asset_class"), CLASS_LABEL),
                "by_currency": _records(allocation(snap, "currency")),
            }
        )

    dd = drawdown_series(df)
    return Overview(
        as_of=last_day.date(),
        period_start=panel["day"].min().date(),
        total_aum_usd=round(float(snapshot["value_usd"].sum()), 2),
        clients=clients,
        allocation={
            "by_asset_class": _records(allocation(snapshot, "asset_class"), CLASS_LABEL),
            "by_currency": _records(allocation(snapshot, "currency")),
            "by_custodian": _records(allocation(snapshot, "custodian")),
        },
        contributions={
            cid: [
                {"label": r.label, "contribution": float(r.contribution)}
                for r in contributions(panel, df, cid).itertuples(index=False)
            ]
            for cid in client_ids
        },
        drawdown={
            cid: [
                {
                    "date": r.day.date().isoformat(),
                    "twr_index": float(r.twr_index),
                    "drawdown": float(r.drawdown),
                }
                for r in g.itertuples(index=False)
            ]
            for cid, g in dd.groupby("client_id")
        },
    )

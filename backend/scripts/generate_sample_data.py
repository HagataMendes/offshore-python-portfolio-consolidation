"""Gera os arquivos FICTÍCIOS dos custodiantes para setembro de 2026.

Cada custodiante manda arquivos num formato diferente, como na vida real:
- Pershing: CSV, datas MM/DD/AAAA, ativos identificados pelo ticker.
- UBS: JSON, datas ISO, ativos identificados pelo ISIN, renda fixa com preço em %.

O script também cria três situações do dia a dia de um time de consolidação:
- um arquivo reenviado (duplicado), que precisa ser ignorado;
- um arquivo corrompido, que vai para a fila de erros (DLQ) e depois é reenviado;
- um arquivo de movimentações que chega atrasado, gerando uma quebra de
  reconciliação que se resolve sozinha quando ele chega;
- um erro do custodiante (2 cotas de VOO a mais), que fica como quebra aberta.

Uso:  python scripts/generate_sample_data.py
O resultado é determinístico (mesma semente), então os testes podem confiar nele.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "sample_data"

# Fechamento de agosto + dias úteis de setembro (07/09 é feriado nos EUA).
DAYS = [date(2026, 8, 31)] + [
    date(2026, 9, d) for d in range(1, 31) if date(2026, 9, d).weekday() < 5 and d != 7
]

MARIA_PSH, MARIA_UBS, MANOEL_UBS = "4PX-100231", "CH-88.1042.01", "CH-88.1077.02"

AAPL, VOO, MSFT = "US0378331005", "US9229083632", "US5949181045"
EUR_BOND, TNOTE, USD_CORP = "XS0000000011", "US0000000029", "US0000000037"

SEED = 64  # escolhida para a Maria ter um mês positivo e o Manoel um "sobe e desce"
rng = random.Random(SEED)


def q(value: float | Decimal, places: str = "0.01") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_EVEN)


def price_path(end: str, vol: float, drift: float, places: str = "0.01") -> dict[date, Decimal]:
    """Caminho de preços que TERMINA no preço dado, gerado de trás para frente."""
    prices = [float(end)]
    for _ in DAYS[1:]:
        prices.append(prices[-1] / (1 + rng.gauss(drift, vol)))
    prices.reverse()
    return {d: q(p, places) for d, p in zip(DAYS, prices, strict=True)}


# Preços finais em 30/09 iguais aos da tela, para os números baterem com a prévia.
PX = {
    AAPL: price_path("232.40", 0.011, 0.0012),
    VOO: price_path("548.20", 0.007, 0.0010),
    MSFT: price_path("418.50", 0.012, -0.0004),
    EUR_BOND: price_path("98.50", 0.0012, 0.0002),
    TNOTE: price_path("99.20", 0.0010, -0.0001),
    USD_CORP: price_path("101.10", 0.0010, 0.0001),
}
EURUSD = price_path("1.1150", 0.0025, 0.0001, "0.0001")


def between(d: date, start: date, end: date | None = None) -> bool:
    return d >= start and (end is None or d <= end)


# --- Movimentações -----------------------------------------------------------

D = lambda day: date(2026, 9, day)  # noqa: E731

voo_buy_px = PX[VOO][D(16)]
tnote_sell_px = PX[TNOTE][D(14)]

MARIA_PSH_TX = [
    # (data, tipo, ticker, qtd, preço, valor líquido)
    (D(11), "DIV", "AAPL", 100, "0.26", Decimal("26.00")),
    (D(15), "DEP", "", 0, "", Decimal("20000.00")),
    (D(16), "BUY", "VOO", 30, str(voo_buy_px), -q(30 * voo_buy_px)),
]
MARIA_UBS_TX = [(D(30), "CUSTODY_FEE", None, 0, None, Decimal("-15.00"), "EUR")]
MANOEL_UBS_TX = [
    (D(14), "SECURITY_SALE", TNOTE, 60000, tnote_sell_px, q(60000 * tnote_sell_px / 100), "USD"),
    (D(15), "CASH_WITHDRAWAL", None, 0, None, Decimal("-60000.00"), "USD"),
    (D(25), "DIVIDEND", MSFT, 60, Decimal("0.83"), Decimal("49.80"), "USD"),
    (D(30), "CUSTODY_FEE", None, 0, None, Decimal("-20.00"), "USD"),
]


def cash_path(end: Decimal, flows: list[tuple[date, Decimal]]) -> dict[date, Decimal]:
    """Saldo de caixa por dia, de trás para frente a partir do saldo final."""
    start = end - sum(v for _, v in flows)
    out, bal = {}, start
    for d in DAYS:
        bal += sum(v for fd, v in flows if fd == d)
        out[d] = bal
    return out


maria_usd_cash = cash_path(Decimal("4862.50"), [(t[0], t[5]) for t in MARIA_PSH_TX])
maria_eur_cash = cash_path(Decimal("3200.00"), [(t[0], t[5]) for t in MARIA_UBS_TX])
manoel_cash = cash_path(Decimal("6335.00"), [(t[0], t[5]) for t in MANOEL_UBS_TX])


# --- Escrita dos arquivos ------------------------------------------------------


def us_date(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def write_pershing(d: date, voo_qty: int | None = None) -> str:
    name = f"pershing_positions_{d:%Y%m%d}.csv"
    voo = voo_qty if voo_qty is not None else (50 if d >= D(16) else 20)
    rows = [
        [MARIA_PSH, us_date(d), "EQUITY", "AAPL", "APPLE INC", 100, PX[AAPL][d], "USD"],
        [MARIA_PSH, us_date(d), "ETF", "VOO", "VANGUARD S&P 500 ETF", voo, PX[VOO][d], "USD"],
        [MARIA_PSH, us_date(d), "CASH", "USD", "US DOLLAR", maria_usd_cash[d], "1.00", "USD"],
    ]
    with open(OUT / "pershing" / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ACCOUNT", "DATE", "SEC_TYPE", "TICKER", "DESCRIPTION", "QTY", "PRICE", "CCY"])
        w.writerows(rows)
    return f"pershing/{name}"


def write_pershing_tx(d: date) -> str | None:
    txs = [t for t in MARIA_PSH_TX if t[0] == d]
    if not txs:
        return None
    name = f"pershing_transactions_{d:%Y%m%d}.csv"
    with open(OUT / "pershing" / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["ACCOUNT", "TRADE_DATE", "TXN_TYPE", "TICKER", "QTY", "PRICE", "NET_AMOUNT", "CCY", "REF"]
        )
        for i, (td, kind, ticker, qty, px, amount) in enumerate(txs, 1):
            w.writerow(
                [MARIA_PSH, us_date(td), kind, ticker, qty or "", px, amount, "USD", f"PSH{td:%m%d}{i:02d}"]
            )
    return f"pershing/{name}"


def ubs_holding(isin, desc, cls, units, px, unit, ccy):
    return {
        "isin": isin,
        "description": desc,
        "assetClass": cls,
        "units": str(units),
        "px": str(px),
        "priceUnit": unit,
        "currency": ccy,
    }


def write_ubs(d: date, corrupt: bool = False) -> str:
    name = f"ubs_positions_{d:%Y%m%d}.json"
    tnote = 90000 if d >= D(14) else 150000
    doc = {
        "custodian": "UBS",
        "fileType": "POSITIONS",
        "asOf": d.isoformat(),
        "portfolios": [
            {
                "accountId": MARIA_UBS,
                "holdings": [
                    ubs_holding(
                        EUR_BOND, "EUR CORP 3.25% 2029", "BOND", 50000, PX[EUR_BOND][d], "PERCENT", "EUR"
                    ),
                    ubs_holding(None, "CASH EUR", "CASH", maria_eur_cash[d], "1", "UNIT", "EUR"),
                ],
            },
            {
                "accountId": MANOEL_UBS,
                "holdings": [
                    ubs_holding(
                        TNOTE, "US T-NOTE 4.125% 2030", "BOND", tnote, PX[TNOTE][d], "PERCENT", "USD"
                    ),
                    ubs_holding(
                        USD_CORP, "USD CORP 5% 2028", "BOND", 25000, PX[USD_CORP][d], "PERCENT", "USD"
                    ),
                    ubs_holding(MSFT, "MICROSOFT CORP", "EQUITY", 60, PX[MSFT][d], "UNIT", "USD"),
                    ubs_holding(None, "CASH USD", "CASH", manoel_cash[d], "1", "UNIT", "USD"),
                ],
            },
        ],
    }
    if corrupt:
        del doc["asOf"]
        name = name.replace(".json", "__corrompido.json")
    (OUT / "ubs" / name).write_text(json.dumps(doc, indent=2))
    return f"ubs/{name}"


def write_ubs_tx(d: date) -> str | None:
    maria = [t for t in MARIA_UBS_TX if t[0] == d]
    manoel = [t for t in MANOEL_UBS_TX if t[0] == d]
    if not maria and not manoel:
        return None

    def mv(acc, i, t):
        vd, kind, isin, units, px, amount, ccy = t
        return {
            "ref": f"{acc[-5:-3]}{vd:%m%d}{i:02d}",
            "valueDate": vd.isoformat(),
            "kind": kind,
            "isin": isin,
            "units": str(units),
            "px": None if px is None else str(px),
            "amount": str(amount),
            "currency": ccy,
        }

    doc = {
        "custodian": "UBS",
        "fileType": "TRANSACTIONS",
        "asOf": d.isoformat(),
        "portfolios": [
            {"accountId": acc, "movements": [mv(acc, i, t) for i, t in enumerate(txs, 1)]}
            for acc, txs in ((MARIA_UBS, maria), (MANOEL_UBS, manoel))
            if txs
        ],
    }
    name = f"ubs_transactions_{d:%Y%m%d}.json"
    (OUT / "ubs" / name).write_text(json.dumps(doc, indent=2))
    return f"ubs/{name}"


def next_business_day(d: date) -> date:
    n = d + timedelta(days=1)
    while n.weekday() >= 5 or n == D(7):
        n += timedelta(days=1)
    return n


def main() -> None:
    for sub in ("pershing", "ubs"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        for old in (OUT / sub).iterdir():
            old.unlink()

    # Manifesto: ordem em que os arquivos "chegam" (simula o S3 → SQS).
    arrivals: list[dict] = []

    def arrive(path: str | None, when: date, hhmm: str, delivered_as: str | None = None) -> None:
        if path:
            arrivals.append(
                {
                    "path": path,
                    "delivered_as": delivered_as or path.split("/")[-1],
                    "received_at": f"{when.isoformat()}T{hhmm}:00",
                }
            )

    for d in DAYS:
        recv = next_business_day(d)
        late_tx = d == D(14)  # movimentações da venda do Manoel chegam atrasadas

        arrive(write_pershing_tx(d), recv, "07:10")
        arrive(write_pershing(d, voo_qty=52 if d == D(22) else None), recv, "07:15")
        if d == D(30):  # custodiante reenviou o mesmo arquivo: deve ser ignorado
            arrive(f"pershing/pershing_positions_{d:%Y%m%d}.csv", recv, "07:16")

        if not late_tx:
            arrive(write_ubs_tx(d), recv, "07:38")
        if d == D(29):  # primeira versão corrompida, depois o reenvio correto
            arrive(write_ubs(d, corrupt=True), recv, "07:39", delivered_as=f"ubs_positions_{d:%Y%m%d}.json")
            arrive(write_ubs(d), recv, "08:05")
        else:
            arrive(write_ubs(d), recv, "07:40")
        if late_tx:
            arrive(write_ubs_tx(d), recv, "10:12")

    (OUT / "manifest.json").write_text(json.dumps(arrivals, indent=2))

    market = OUT / "market"
    market.mkdir(exist_ok=True)
    with open(market / "fx_eurusd.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "pair", "rate"])
        w.writerows([d.isoformat(), "EURUSD", EURUSD[d]] for d in DAYS)

    print(
        f"{len(arrivals)} arquivos no manifesto; {len(DAYS)} dias; VOO comprado a {voo_buy_px}; "
        f"T-Note vendido a {tnote_sell_px}%"
    )


if __name__ == "__main__":
    main()

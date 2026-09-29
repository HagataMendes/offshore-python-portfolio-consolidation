from datetime import date
from decimal import Decimal

import pytest

from app.adapters.base import FileKind, InvalidFileError
from app.domain.models import AssetClass, Custodian, TransactionType

PERSHING_CSV = b"""ACCOUNT,DATE,SEC_TYPE,TICKER,DESCRIPTION,QTY,PRICE,CCY
4PX-100231,09/28/2026,EQUITY,AAPL,APPLE INC,100,227.50,USD
4PX-100231,09/28/2026,CASH,USD,US DOLLAR,1500.25,1.00,USD
"""

UBS_JSON = b"""{
  "custodian": "UBS", "fileType": "POSITIONS", "asOf": "2026-09-28",
  "portfolios": [{"accountId": "CH-88.1042.01", "holdings": [
    {"isin": "XS0000000011", "description": "EUR CORP", "assetClass": "BOND",
     "units": "50000", "px": "98.50", "priceUnit": "PERCENT", "currency": "EUR"}
  ]}]
}"""


def test_pershing_traduz_ticker_para_isin_e_data_americana(registry):
    parsed = registry.for_file("pershing_positions_20260928.csv").parse(
        "pershing_positions_20260928.csv", PERSHING_CSV
    )
    apple, caixa = parsed.holdings
    assert parsed.kind is FileKind.POSITIONS
    assert apple.as_of == date(2026, 9, 28)  # 09/28/2026 → 28/09
    assert apple.security_id == "US0378331005"  # AAPL → ISIN pelo cadastro de ativos
    assert apple.client_id == "maria"  # conta da Pershing → cliente
    assert caixa.asset_class is AssetClass.CASH
    assert caixa.quantity == Decimal("1500.25")


def test_ubs_entende_preco_em_percentual(registry):
    parsed = registry.for_file("ubs_positions_20260928.json").parse("ubs_positions_20260928.json", UBS_JSON)
    [titulo] = parsed.holdings
    assert titulo.custodian is Custodian.UBS
    assert titulo.price_is_percent
    assert titulo.local_value == Decimal("49250")  # 50.000 × 98,50%
    assert titulo.currency == "EUR"


def test_os_dois_adapters_entregam_o_mesmo_formato(registry):
    p = registry.for_file("pershing_positions_20260928.csv").parse(
        "pershing_positions_20260928.csv", PERSHING_CSV
    )
    u = registry.for_file("ubs_positions_20260928.json").parse("ubs_positions_20260928.json", UBS_JSON)
    assert type(p.holdings[0]) is type(u.holdings[0])
    assert p.holdings[0].client_id == u.holdings[0].client_id == "maria"


def test_ubs_sem_asof_e_rejeitado(registry):
    with pytest.raises(InvalidFileError, match='"asOf" ausente'):
        registry.for_file("ubs_x.json").parse("ubs_x.json", b'{"fileType": "POSITIONS", "portfolios": []}')


def test_pershing_com_coluna_faltando_e_rejeitado(registry):
    csv = b"ACCOUNT,DATE,TICKER\n4PX-100231,09/28/2026,AAPL\n"
    with pytest.raises(InvalidFileError, match="Colunas ausentes"):
        registry.for_file("pershing_positions_x.csv").parse("pershing_positions_x.csv", csv)


def test_conta_desconhecida_e_rejeitada(registry):
    csv = PERSHING_CSV.replace(b"4PX-100231", b"9ZZ-000000")
    with pytest.raises(InvalidFileError, match="não está cadastrada"):
        registry.for_file("pershing_positions_x.csv").parse("pershing_positions_x.csv", csv)


def test_pershing_movimentacoes(registry):
    csv = b"""ACCOUNT,TRADE_DATE,TXN_TYPE,TICKER,QTY,PRICE,NET_AMOUNT,CCY,REF
4PX-100231,09/15/2026,DEP,,,,20000.00,USD,PSH091501
4PX-100231,09/16/2026,BUY,VOO,30,545.00,-16350.00,USD,PSH091601
"""
    parsed = registry.for_file("pershing_transactions_x.csv").parse("pershing_transactions_x.csv", csv)
    deposito, compra = parsed.transactions
    assert deposito.type is TransactionType.DEPOSIT and deposito.type.is_external_flow
    assert compra.type is TransactionType.BUY and not compra.type.is_external_flow
    assert compra.quantity == 30 and compra.amount == Decimal("-16350.00")


def test_arquivo_de_custodiante_desconhecido(registry):
    with pytest.raises(InvalidFileError, match="Nenhum custodiante"):
        registry.for_file("jpmorgan_positions.xml")

from collections import Counter
from datetime import date, datetime
from decimal import Decimal

from app.ingestion.records import FileStatus
from app.services import PortfolioService

AGORA = datetime(2026, 10, 1, 7, 0)
CSV = b"""ACCOUNT,DATE,SEC_TYPE,TICKER,DESCRIPTION,QTY,PRICE,CCY
4PX-100231,09/28/2026,EQUITY,AAPL,APPLE INC,100,227.50,USD
"""


def test_mesmo_arquivo_duas_vezes_e_ignorado(ingestion):
    primeiro = ingestion.ingest("pershing_positions_20260928.csv", CSV, AGORA)
    segundo = ingestion.ingest("pershing_positions_20260928.csv", CSV, AGORA)
    assert primeiro.status is FileStatus.PROCESSED
    assert segundo.status is FileStatus.DUPLICATE


def test_arquivo_invalido_vai_para_dlq_sem_derrubar_o_resto(ingestion):
    ruim = ingestion.ingest("ubs_positions_20260928.json", b"{ isso nao e json", AGORA)
    bom = ingestion.ingest("pershing_positions_20260928.csv", CSV, AGORA)
    assert ruim.status is FileStatus.FAILED and "JSON inválido" in ruim.error
    assert bom.status is FileStatus.PROCESSED


def test_arquivo_processado_publica_evento(ingestion):
    ingestion.ingest("pershing_positions_20260928.csv", CSV, AGORA)
    topic, payload = ingestion.events.events[-1]
    assert topic == "carteira-atualizada"
    assert payload["client_id"] == "maria"


def test_setembro_completo(loaded):
    status = Counter(f.status for f in loaded.repo.file_records())
    assert status == {FileStatus.PROCESSED: 51, FileStatus.DUPLICATE: 1, FileStatus.FAILED: 1}


def test_quebras_de_setembro(loaded):
    quebras = loaded.repo.load_book().breaks
    abertas = [q for q in quebras if not q.resolved]
    # Erro do custodiante: 2 cotas de VOO a mais em 22/09, continua aberta.
    assert [(q.day, q.asset_name, q.reported_quantity - q.expected_quantity) for q in abertas] == [
        (date(2026, 9, 22), "VOO", Decimal(2))
    ]
    # Movimentações da venda do Manoel chegaram atrasadas: quebras resolvidas sozinhas.
    assert {q.client_id for q in quebras if q.resolved} == {"manoel"}


def test_consolidado_bate_com_a_soma_das_posicoes(loaded, reference):
    service = PortfolioService(loaded.repo, reference)
    assert service.portfolio("maria", date(2026, 9, 30)).total_usd == Decimal("113994.25")
    assert service.portfolio("manoel", date(2026, 9, 30)).total_usd == Decimal("146000.00")


def test_extrato_fecha(loaded, reference):
    _, s = PortfolioService(loaded.repo, reference).statement("maria", "2026-09")
    assert s.opening_balance + s.deposits + s.withdrawals + s.investment_result == s.closing_balance
    assert s.deposits == Decimal("20000.00")


def test_twr_desconta_deposito_e_saque(loaded, reference):
    service = PortfolioService(loaded.repo, reference)
    maria = service.performance("maria", date(2026, 8, 31), date(2026, 9, 30))
    manoel = service.performance("manoel", date(2026, 8, 31), date(2026, 9, 30))
    # A conta ingênua infla a Maria (depósito) e derruba o Manoel (saque).
    assert maria.naive_return > Decimal("0.2") and maria.twr < Decimal("0.05")
    assert manoel.naive_return < Decimal("-0.2") and manoel.twr > 0
    assert len(maria.sub_periods) == 2

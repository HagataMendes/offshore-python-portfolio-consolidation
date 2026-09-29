from datetime import date
from decimal import Decimal

from app.domain.models import AssetClass, Custodian, Holding, Transaction, TransactionType
from app.domain.reconciliation import PositionBook

VOO = "US9229083632"


def posicao(dia: int, qtd: str, caixa: str) -> list[Holding]:
    d = date(2026, 9, dia)
    return [
        Holding(
            "maria",
            Custodian.PERSHING,
            d,
            VOO,
            "Vanguard S&P 500 ETF",
            AssetClass.EQUITY,
            Decimal(qtd),
            Decimal("545"),
            "USD",
            ticker="VOO",
        ),
        Holding(
            "maria",
            Custodian.PERSHING,
            d,
            "CASH:USD",
            "Caixa em dólar",
            AssetClass.CASH,
            Decimal(caixa),
            Decimal(1),
            "USD",
        ),
    ]


def compra(dia: int, qtd: str, valor: str) -> Transaction:
    return Transaction(
        f"tx-{dia}",
        "maria",
        Custodian.PERSHING,
        date(2026, 9, dia),
        TransactionType.BUY,
        Decimal(valor),
        "USD",
        VOO,
        Decimal(qtd),
        Decimal("545"),
        "VOO",
    )


def test_posicao_que_bate_nao_gera_quebra():
    book = PositionBook()
    book.open(posicao(15, "20", "20000"))
    book.apply(compra(16, "30", "-16350"))
    assert book.check(posicao(16, "50", "3650")) == []


def test_cota_a_mais_sem_movimentacao_gera_quebra():
    book = PositionBook()
    book.open(posicao(21, "50", "4000"))
    [quebra] = book.check(posicao(22, "52", "4000"))
    assert quebra.expected_quantity == Decimal(50)
    assert quebra.reported_quantity == Decimal(52)
    assert quebra.asset_name == "VOO"
    assert not quebra.resolved
    assert "2 a mais" in quebra.note


def test_book_nao_absorve_o_erro_do_custodiante():
    # Depois de uma quebra, o dia seguinte correto não deve gerar nova quebra.
    book = PositionBook()
    book.open(posicao(21, "50", "4000"))
    book.check(posicao(22, "52", "4000"))
    assert book.check(posicao(23, "50", "4000")) == []


def test_movimentacao_atrasada_resolve_a_quebra():
    book = PositionBook()
    book.open(posicao(15, "20", "20000"))
    quebras = book.check(posicao(16, "50", "3650"))  # compra ainda não chegou
    assert len(quebras) == 2  # VOO e caixa
    book.apply(compra(16, "30", "-16350"))  # arquivo atrasado chega
    assert all(q.resolved for q in book.breaks)

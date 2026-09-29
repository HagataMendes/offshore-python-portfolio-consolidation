from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.models import ValuationPoint
from app.domain.performance import compound, naive_return, split_sub_periods, time_weighted_return

D0 = date(2026, 8, 31)


def serie(*pontos: tuple[str, str]) -> list[ValuationPoint]:
    """Monta uma série a partir de pares (valor, fluxo_externo)."""
    return [ValuationPoint(D0 + timedelta(days=i), Decimal(v), Decimal(f)) for i, (v, f) in enumerate(pontos)]


def test_exemplo_do_manoel_mais_5_e_menos_2_da_2_9():
    # 200 mil → 210 mil (+5%); saca 60 mil, sobram 150 mil → 147 mil (−2%)
    historico = serie(("200000", "0"), ("210000", "0"), ("147000", "-60000"))
    assert time_weighted_return(historico) == Decimal("0.029")


def test_conta_ingenua_erra_quando_ha_saque():
    historico = serie(("200000", "0"), ("210000", "0"), ("147000", "-60000"))
    assert naive_return(historico) == Decimal("-0.265")


def test_twr_nao_depende_do_tamanho_do_deposito():
    pequeno = serie(("100", "0"), ("110", "0"), ("126", "10"))
    grande = serie(("100", "0"), ("110", "0"), ("1155", "990"))
    assert time_weighted_return(pequeno) == time_weighted_return(grande)


def test_sem_fluxo_twr_igual_a_conta_simples():
    historico = serie(("1000", "0"), ("1010", "0"), ("1030", "0"))
    assert time_weighted_return(historico) == naive_return(historico)


def test_quebra_em_subperiodos_no_dia_do_fluxo():
    historico = serie(("200000", "0"), ("210000", "0"), ("147000", "-60000"))
    pedacos = split_sub_periods(historico)
    assert [p.ret for p in pedacos] == [Decimal("0.05"), Decimal("-0.02")]
    assert pedacos[1].flow_before == Decimal("-60000")
    assert compound(p.ret for p in pedacos) == time_weighted_return(historico)


def test_carteira_zerada_gera_erro_claro():
    with pytest.raises(ValueError, match="zerada"):
        time_weighted_return(serie(("100", "0"), ("0", "-100"), ("0", "0")))


def test_decimal_nao_tem_erro_de_arredondamento_do_float():
    assert 0.1 + 0.2 != 0.3
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")

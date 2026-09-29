from datetime import date

import pandas as pd
import pytest

from app.analytics import build_overview, concentration, risk_metrics
from app.services import PortfolioService

INICIO, FIM = date(2026, 8, 31), date(2026, 9, 30)


@pytest.fixture
def overview(loaded, reference):
    return build_overview(loaded.repo, reference, INICIO, FIM)


def test_twr_do_pandas_bate_com_o_do_dominio(overview, loaded, reference):
    """Dois caminhos independentes (Decimal no domínio, float no pandas) têm que concordar."""
    service = PortfolioService(loaded.repo, reference)
    for c in overview.clients:
        oficial = service.performance(c["client_id"], INICIO, FIM).twr
        # Diferença esperada só na 8ª casa: o domínio arredonda cada posição em centavos; o pandas não.
        assert c["twr"] == pytest.approx(float(oficial), abs=1e-7)


def test_contribuicoes_somam_o_twr(overview):
    for c in overview.clients:
        total = sum(x["contribution"] for x in overview.contributions[c["client_id"]])
        assert total == pytest.approx(c["twr"], abs=1e-12)


def test_patrimonio_total_e_alocacao(overview):
    assert overview.total_aum_usd == pytest.approx(113994.25 + 146000.00)
    for group in overview.allocation.values():
        assert sum(x["weight"] for x in group) == pytest.approx(1)
        assert sum(x["value_usd"] for x in group) == pytest.approx(overview.total_aum_usd, abs=0.01)


def test_exposicao_ao_euro_da_maria(overview):
    maria = next(c for c in overview.clients if c["client_id"] == "maria")
    manoel = next(c for c in overview.clients if c["client_id"] == "manoel")
    assert 0.4 < maria["foreign_currency_weight"] < 0.6  # título e caixa em euro
    assert maria["shock_impact_pct"] == pytest.approx(maria["foreign_currency_weight"] * -0.10)
    assert manoel["foreign_currency_weight"] == 0  # tudo em dólar


def test_drawdown_comeca_em_zero_e_nunca_e_positivo(overview):
    for series in overview.drawdown.values():
        assert series[0]["drawdown"] == 0
        assert all(p["drawdown"] <= 1e-12 for p in series)


def test_concentracao_com_quatro_ativos_iguais():
    snap = pd.DataFrame({"label": list("ABCD"), "value_usd": [25.0] * 4})
    c = concentration(snap)
    assert c["hhi"] == pytest.approx(0.25)
    assert c["effective_positions"] == pytest.approx(4)


def test_metricas_de_risco_em_serie_conhecida():
    r = pd.Series([None, 0.10, -0.20, 0.05], index=pd.date_range("2026-09-01", periods=4))
    m = risk_metrics(r)
    assert m["twr"] == pytest.approx(1.10 * 0.80 * 1.05 - 1)
    assert m["max_drawdown"] == pytest.approx(-0.20)  # caiu 20% a partir do topo
    assert m["best_day_return"] == pytest.approx(0.10)
    assert m["days"] == 3

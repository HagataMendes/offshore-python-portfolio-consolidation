import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from tests.conftest import SAMPLE, make_settings


@pytest.fixture(scope="module")
def api():
    with TestClient(create_app(make_settings())) as client:
        yield client


def test_health(api):
    assert api.get("/health").json()["status"] == "ok"


def test_carteira_consolidada_da_maria(api):
    body = api.get("/clients/maria/positions", params={"date": "2026-09-30"}).json()
    assert body["total_usd"] == 113994.25
    assert {p["custodian"] for p in body["positions"]} == {"Pershing", "UBS"}
    assert body["history"][0]["date"] == "2026-08-31"
    assert round(sum(p["market_value_usd"] for p in body["positions"]), 2) == body["total_usd"]


def test_extrato_do_manoel(api):
    body = api.get("/clients/manoel/statement", params={"month": "2026-09"}).json()
    assert body["withdrawals_usd"] == -60000.0
    saque = next(t for t in body["transactions"] if t["type"] == "saque")
    assert saque["is_external_flow"] is True


def test_rentabilidade_tem_subperiodos_com_campo_return(api):
    body = api.get("/clients/maria/performance", params={"from": "2026-08-31", "to": "2026-09-30"}).json()
    assert len(body["sub_periods"]) == 2
    assert "return" in body["sub_periods"][0]
    assert [m["month"] for m in body["monthly"]][-1] == "2026-09"


def test_cliente_inexistente_da_404(api):
    assert api.get("/clients/joao/positions", params={"date": "2026-09-30"}).status_code == 404


def test_operacoes(api):
    files = api.get("/ingestion/files").json()
    assert {f["status"] for f in files} == {"processado", "duplicado", "erro_dlq"}
    breaks = api.get("/reconciliation/breaks").json()
    assert breaks[0]["status"] == "aberta"


def test_upload_de_arquivo_duplicado(api):
    content = (SAMPLE / "pershing" / "pershing_positions_20260930.csv").read_bytes()
    r = api.post("/ingestion/files", files={"file": ("pershing_positions_20260930.csv", content, "text/csv")})
    assert r.status_code == 201
    assert r.json()["status"] == "duplicado"


def test_analise_geral(api):
    body = api.get("/analytics/overview", params={"from": "2026-08-31", "to": "2026-09-30"}).json()
    assert body["total_aum_usd"] == 259994.25
    assert [c["client_id"] for c in body["clients"]] == ["maria", "manoel"]
    assert body["contributions"]["maria"][-1]["label"] == "Outros efeitos"

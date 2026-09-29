"""API REST (FastAPI): a porta de saída que o front e o Portal do Cliente consomem.

Rodar:   uvicorn app.api.main:app --reload
Docs:    http://localhost:8000/docs  (Swagger gerado automaticamente)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import Settings
from ..container import Container
from ..logging_setup import setup_logging
from ..services import NotFoundError
from .schemas import (
    AnalyticsOverviewOut,
    BreakOut,
    ClientOut,
    IngestedFileOut,
    PerformanceOut,
    PortfolioOut,
    StatementOut,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        app.state.c = Container(settings)
        yield

    app = FastAPI(
        title="Offshore Portfolio API",
        version="0.1.0",
        description="Consolidação multi-custodiante: posições, extrato, rentabilidade (TWR) e ingestão.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def c() -> Container:
        return app.state.c

    def not_found(e: NotFoundError) -> HTTPException:
        return HTTPException(status_code=404, detail=str(e))

    @app.get("/health", tags=["infra"])
    def health() -> dict:
        return {
            "status": "ok",
            "storage": "postgres" if settings.database_url else "memória",
            "aws": settings.use_aws,
            "files_ingested": len(c().repository.file_records()),
        }

    @app.get("/clients", response_model=list[ClientOut], tags=["clientes"])
    def list_clients():
        return [ClientOut.of(cl) for cl in c().reference.clients.values()]

    @app.get("/clients/{client_id}/positions", response_model=PortfolioOut, tags=["carteira"])
    def positions(client_id: str, date_: Annotated[date, Query(alias="date")]):
        """Carteira consolidada numa data, somando todos os custodiantes."""
        try:
            return PortfolioOut.of(c().portfolio.portfolio(client_id, date_))
        except NotFoundError as e:
            raise not_found(e) from e

    @app.get("/clients/{client_id}/statement", response_model=StatementOut, tags=["carteira"])
    def statement(
        client_id: str, month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$", examples=["2026-09"])]
    ):
        """Extrato consolidado do mês."""
        try:
            client, s = c().portfolio.statement(client_id, month)
        except NotFoundError as e:
            raise not_found(e) from e
        return StatementOut.of(client, s)

    @app.get("/clients/{client_id}/performance", response_model=PerformanceOut, tags=["carteira"])
    def performance(client_id: str, from_: Annotated[date, Query(alias="from")], to: date):
        """Rentabilidade pelo método TWR, com os sub-períodos e o histórico mensal."""
        try:
            return PerformanceOut.of(c().portfolio.performance(client_id, from_, to))
        except NotFoundError as e:
            raise not_found(e) from e

    @app.get("/analytics/overview", response_model=AnalyticsOverviewOut, tags=["análise"])
    def analytics_overview(from_: Annotated[date, Query(alias="from")], to: date):
        """Análise geral com pandas: risco, concentração, exposição cambial e contribuição por ativo."""
        from ..analytics import RISK_FREE_ANNUAL, build_overview

        try:
            o = build_overview(c().repository, c().reference, from_, to)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return {**o.__dict__, "risk_free_annual": RISK_FREE_ANNUAL}

    @app.get("/ingestion/files", response_model=list[IngestedFileOut], tags=["operações"])
    def ingested_files():
        """Log da ingestão, do mais recente para o mais antigo."""
        files = sorted(c().repository.file_records(), key=lambda f: (f.received_at, f.id), reverse=True)
        return [IngestedFileOut.of(f) for f in files]

    @app.post("/ingestion/files", tags=["operações"], response_model=None)
    def upload_file(file: UploadFile):
        """Envio manual de um arquivo de custodiante.

        Com AWS ligada, o arquivo vai para o S3 e segue o mesmo caminho da fila (202).
        Sem AWS, é processado na hora (201).
        """
        name = file.filename or "sem_nome"
        content = file.file.read()
        if settings.use_aws:
            from ..infra.aws import aws_client

            key = f"inbox/manual/{datetime.now():%Y%m%dT%H%M%S}/{name}"
            aws_client("s3").put_object(Bucket=settings.bucket, Key=key, Body=content)
            return JSONResponse({"status": "enfileirado", "s3_key": key}, status_code=202)
        record = c().ingestion.ingest(name, content, datetime.now())
        return JSONResponse(IngestedFileOut.of(record).model_dump(mode="json"), status_code=201)

    @app.get("/reconciliation/breaks", response_model=list[BreakOut], tags=["operações"])
    def breaks():
        items = sorted(c().repository.load_book().breaks, key=lambda b: (b.resolved, b.day), reverse=False)
        return [
            BreakOut(
                id=b.id,
                date=b.day,
                client_id=b.client_id,
                custodian=b.custodian.value,
                asset=b.asset_name,
                expected_quantity=float(b.expected_quantity),
                reported_quantity=float(b.reported_quantity),
                status="resolvida" if b.resolved else "aberta",
                note=b.note,
            )
            for b in items
        ]

    return app


app = create_app()

import logging
import os
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.adapters.registry import AdapterRegistry
from app.config import Settings
from app.infra.memory import InMemoryEventBus, InMemoryFileRegistry, InMemoryRepository
from app.infra.sql import SqlRepository, metadata
from app.ingestion.loader import load_sample_files
from app.ingestion.pipeline import IngestionService
from app.reference import ReferenceData

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"

# Postgres de verdade é opcional: no CI (e com Docker) defina TEST_DATABASE_URL.
PG_URL = os.getenv("TEST_DATABASE_URL")
BACKENDS = ["memoria", "sqlite"] + (["postgres"] if PG_URL else [])


def make_settings(**overrides) -> Settings:
    base = replace(Settings.from_env(), data_dir=SAMPLE, database_url=None, use_aws=False, load_samples=True)
    return replace(base, **overrides)


@pytest.fixture(autouse=True)
def _quiet_logs():
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture(scope="session")
def reference() -> ReferenceData:
    return ReferenceData.load(SAMPLE)


@pytest.fixture
def registry(reference) -> AdapterRegistry:
    return AdapterRegistry(reference)


@pytest.fixture(params=BACKENDS)
def repository(request):
    """Os testes de ingestão rodam em todos os bancos: o resultado tem que ser o mesmo."""
    if request.param == "memoria":
        yield InMemoryRepository()
        return
    if request.param == "sqlite":
        engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(PG_URL)
        metadata.drop_all(engine)
    yield SqlRepository(engine)
    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def ingestion(repository, registry) -> IngestionService:
    return IngestionService(repository, InMemoryFileRegistry(), registry, InMemoryEventBus())


@pytest.fixture
def loaded(ingestion) -> IngestionService:
    """Serviço com todos os arquivos de setembro já ingeridos."""
    load_sample_files(ingestion, SAMPLE)
    return ingestion

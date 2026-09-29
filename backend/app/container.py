"""Monta as peças do sistema conforme a configuração (injeção de dependência simples)."""

from __future__ import annotations

from sqlalchemy import create_engine

from .adapters.registry import AdapterRegistry
from .config import Settings
from .infra.memory import InMemoryEventBus, InMemoryFileRegistry, InMemoryRepository
from .ingestion.loader import load_sample_files
from .ingestion.pipeline import IngestionService
from .ports import EventPublisher, PortfolioRepository, ProcessedFileRegistry
from .reference import ReferenceData
from .services import PortfolioService


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.reference = ReferenceData.load(settings.data_dir)
        self.repository = self._repository()
        self.file_registry, self.events = self._aws_or_memory()
        self.ingestion = IngestionService(
            self.repository, self.file_registry, AdapterRegistry(self.reference), self.events
        )
        self.portfolio = PortfolioService(self.repository, self.reference)
        if settings.load_samples:
            load_sample_files(self.ingestion, settings.data_dir)

    def _repository(self) -> PortfolioRepository:
        if not self.settings.database_url:
            return InMemoryRepository()
        from .infra.sql import SqlRepository

        return SqlRepository(create_engine(self.settings.database_url, pool_pre_ping=True))

    def _aws_or_memory(self) -> tuple[ProcessedFileRegistry, EventPublisher]:
        if not self.settings.use_aws:
            return InMemoryFileRegistry(), InMemoryEventBus()
        from .infra.aws import DynamoFileRegistry, SnsEventPublisher, topic_arn_by_name

        return (
            DynamoFileRegistry(self.settings.files_table),
            SnsEventPublisher(topic_arn_by_name(self.settings.topic_name)),
        )

"""Contrato comum dos adapters de custodiante.

Cada custodiante manda arquivos num formato próprio. Cada adapter traduz o seu
formato para o mesmo modelo padrão (Holding e Transaction). O resto do sistema
nunca sabe de qual custodiante o dado veio.

Para plugar um novo custodiante, basta criar uma classe que siga este contrato
e registrá-la em registry.py. Nada mais precisa mudar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Protocol

from ..domain.models import Custodian, Holding, Transaction


class FileKind(StrEnum):
    POSITIONS = "positions"
    TRANSACTIONS = "transactions"


class InvalidFileError(ValueError):
    """O arquivo não segue o layout esperado. Vai para a fila de erros (DLQ)."""


@dataclass
class ParsedFile:
    custodian: Custodian
    kind: FileKind
    as_of: date
    holdings: list[Holding] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def records(self) -> int:
        return len(self.holdings) + len(self.transactions)


class CustodianAdapter(Protocol):
    custodian: Custodian
    file_format: str  # "CSV", "JSON"...

    def matches(self, file_name: str) -> bool: ...

    def parse(self, file_name: str, content: bytes) -> ParsedFile: ...

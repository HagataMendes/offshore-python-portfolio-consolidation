"""Escolhe o adapter certo para cada arquivo, pelo nome."""

from __future__ import annotations

from ..reference import ReferenceData
from .base import CustodianAdapter, InvalidFileError
from .pershing import PershingAdapter
from .ubs import UbsAdapter


class AdapterRegistry:
    def __init__(self, reference: ReferenceData) -> None:
        # Novo custodiante? Crie o adapter e adicione aqui.
        self.adapters: list[CustodianAdapter] = [PershingAdapter(reference), UbsAdapter(reference)]

    def for_file(self, file_name: str) -> CustodianAdapter:
        for adapter in self.adapters:
            if adapter.matches(file_name):
                return adapter
        raise InvalidFileError(f"Nenhum custodiante reconhece o arquivo {file_name}")

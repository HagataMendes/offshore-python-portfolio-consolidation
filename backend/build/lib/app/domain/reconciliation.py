"""Reconciliação de posições.

Mantemos uma "posição contábil" (book) por cliente, custodiante e ativo, que só
muda com movimentações. Todo dia comparamos o book com o que o custodiante diz:

    posição contábil (ontem + movimentações) == posição informada pelo custodiante?

Se não bate, registramos uma quebra em vez de confiar cegamente no arquivo.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from itertools import count

from .models import Custodian, Holding, ReconciliationBreak, Transaction, TransactionType, cash_key
from .text import fmt_number

BookKey = tuple[str, Custodian]  # (cliente, custodiante)


@dataclass
class BookState:
    """Tudo o que o book precisa para ser salvo no banco e recarregado depois."""

    quantities: dict[BookKey, dict[str, Decimal]] = field(default_factory=dict)
    initialized: set[BookKey] = field(default_factory=set)
    names: dict[str, str] = field(default_factory=dict)
    breaks: list[ReconciliationBreak] = field(default_factory=list)


class PositionBook:
    def __init__(self, state: BookState | None = None) -> None:
        state = state or BookState()
        self._qty: dict[BookKey, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for key, qty in state.quantities.items():
            self._qty[key].update(qty)
        self._initialized: set[BookKey] = set(state.initialized)
        self._names: dict[str, str] = dict(state.names)
        self._breaks: list[ReconciliationBreak] = list(state.breaks)
        self._ids = count(len(self._breaks) + 1)

    def snapshot(self) -> BookState:
        return BookState(
            quantities={k: dict(v) for k, v in self._qty.items() if k in self._initialized or v},
            initialized=set(self._initialized),
            names=dict(self._names),
            breaks=list(self._breaks),
        )

    # --- estado ---------------------------------------------------------------

    def is_initialized(self, client_id: str, custodian: Custodian) -> bool:
        return (client_id, custodian) in self._initialized

    def quantity(self, client_id: str, custodian: Custodian, security_id: str) -> Decimal:
        return self._qty[(client_id, custodian)][security_id]

    @property
    def breaks(self) -> list[ReconciliationBreak]:
        return list(self._breaks)

    # --- operações ------------------------------------------------------------

    def open(self, holdings: Iterable[Holding]) -> None:
        """Carga inicial: a primeira posição recebida vira o ponto de partida do book."""
        for h in holdings:
            key = (h.client_id, h.custodian)
            self._qty[key][h.security_id] = h.quantity
            self._names[h.security_id] = h.ticker or h.name
            self._initialized.add(key)

    def apply(self, tx: Transaction) -> None:
        """Atualiza o book com uma movimentação."""
        book = self._qty[(tx.client_id, tx.custodian)]
        book[cash_key(tx.currency)] += tx.amount
        if tx.type is TransactionType.BUY and tx.security_id:
            book[tx.security_id] += tx.quantity
        elif tx.type is TransactionType.SELL and tx.security_id:
            book[tx.security_id] -= tx.quantity
        self._resolve_breaks_fixed_by(tx)

    def check(self, holdings: list[Holding]) -> list[ReconciliationBreak]:
        """Compara o book com a posição do custodiante e registra as diferenças."""
        if not holdings:
            return []
        first = holdings[0]
        key = (first.client_id, first.custodian)
        reported = {h.security_id: h.quantity for h in holdings}
        for h in holdings:
            self._names.setdefault(h.security_id, h.ticker or h.name)

        already_open = {
            (b.day, b.client_id, b.custodian, b.security_id) for b in self._breaks if not b.resolved
        }
        new_breaks: list[ReconciliationBreak] = []
        for security_id in sorted(set(reported) | set(self._qty[key])):
            expected = self._qty[key][security_id]
            got = reported.get(security_id, Decimal(0))
            if (first.as_of, first.client_id, first.custodian, security_id) in already_open:
                continue  # o mesmo arquivo reprocessado não duplica a quebra
            if expected != got:
                brk = ReconciliationBreak(
                    id=f"rb-{next(self._ids)}",
                    day=first.as_of,
                    client_id=first.client_id,
                    custodian=first.custodian,
                    security_id=security_id,
                    asset_name=self._names.get(security_id, security_id),
                    expected_quantity=expected,
                    reported_quantity=got,
                    note=_describe(expected, got),
                )
                new_breaks.append(brk)
        self._breaks.extend(new_breaks)
        return new_breaks

    def _resolve_breaks_fixed_by(self, tx: Transaction) -> None:
        """Um arquivo de movimentações atrasado pode explicar uma quebra já aberta."""
        for i, brk in enumerate(self._breaks):
            if brk.resolved or brk.client_id != tx.client_id or brk.custodian != tx.custodian:
                continue
            if brk.day < tx.trade_date:
                continue
            now = self.quantity(brk.client_id, brk.custodian, brk.security_id)
            if now == brk.reported_quantity:
                self._breaks[i] = replace(
                    brk,
                    resolved=True,
                    note=f"Arquivo de movimentações de {tx.trade_date:%d/%m} chegou atrasado; "
                    "a posição bateu após o reprocessamento",
                )


def _describe(expected: Decimal, got: Decimal) -> str:
    if expected == 0:
        return "Custodiante informou um ativo que não consta na posição contábil"
    if got == 0:
        return "Ativo sumiu do arquivo do custodiante sem movimentação correspondente"
    diff = got - expected
    direction = "a mais" if diff > 0 else "a menos"
    return f"Custodiante reportou {fmt_number(abs(diff))} {direction} sem movimentação correspondente"

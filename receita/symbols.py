"""Tabela de símbolos com escopos encadeados: global (unidades e receitas) e um por receita."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Iterator

from receita.ast import format_number, format_servings
from receita.types import Amount
from receita.units import Dimension, UnitTable


class SymbolKind(Enum):
    UNIDADE = "unidade"
    RECEITA = "receita"
    INGREDIENTE = "ingrediente"


@dataclass
class Symbol:
    """Nome declarado. `value` fica na unidade base: fator da unidade ou quantidade do
    ingrediente; para receitas, é o rendimento. `line` é None para unidades nativas."""

    name: str
    kind: SymbolKind
    line: int | None = None
    dimension: Dimension | None = None
    value: Fraction | None = None
    scope: Scope | None = None

    @property
    def amount(self) -> Amount | None:
        if self.dimension is None or self.value is None:
            return None
        return Amount(self.value, self.dimension)


class Scope:
    """Escopo com nomes únicos; a busca sobe pela cadeia de escopos pais."""

    def __init__(self, name: str, parent: Scope | None = None) -> None:
        self.name = name
        self.parent = parent
        self.children: list[Scope] = []
        self._symbols: dict[str, Symbol] = {}
        if parent is not None:
            parent.children.append(self)

    def __iter__(self) -> Iterator[Symbol]:
        return iter(self._symbols.values())

    def declare(self, symbol: Symbol) -> Symbol | None:
        """Registra `symbol`; se o nome já existe neste escopo, não altera nada e retorna o anterior."""
        existing = self._symbols.get(symbol.name)
        if existing is None:
            self._symbols[symbol.name] = symbol
        return existing

    def lookup_local(self, name: str) -> Symbol | None:
        return self._symbols.get(name)

    def lookup(self, name: str) -> Symbol | None:
        scope: Scope | None = self
        while scope is not None:
            symbol = scope.lookup_local(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None


class SymbolTable:
    """Escopo global, pré-carregado com as unidades nativas, e os escopos das receitas."""

    def __init__(self, units: UnitTable | None = None) -> None:
        self.global_scope = Scope("global")
        for unit in units or UnitTable():
            self.global_scope.declare(
                Symbol(unit.name, SymbolKind.UNIDADE, None, unit.dimension, unit.factor)
            )

    def new_scope(self, name: str) -> Scope:
        return Scope(name, self.global_scope)

    def format(self) -> str:
        """Listagem de todos os escopos, para a flag --simbolos."""
        sections = [_format_scope("Escopo global", self.global_scope)]
        for scope in self.global_scope.children:
            sections.append(_format_scope(f"Escopo receita {scope.name} (pai: global)", scope))
        return "\n\n".join(sections)


def _format_scope(title: str, scope: Scope) -> str:
    header = ("NOME", "CATEGORIA", "DIMENSÃO", "VALOR", "LINHA")
    rows = [
        (
            s.name,
            s.kind.value,
            _format_dimension(s),
            _format_value(s),
            "nativa" if s.line is None else str(s.line),
        )
        for s in scope
    ]
    if not rows:
        return f"{title}\n  (vazio)"
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
    lines = [title]
    for row in [header, *rows]:
        lines.append("  " + "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())
    return "\n".join(lines)


def _format_dimension(symbol: Symbol) -> str:
    if symbol.kind is SymbolKind.RECEITA:
        return "-"
    return symbol.dimension.value if symbol.dimension is not None else "?"


def _format_value(symbol: Symbol) -> str:
    if symbol.value is None:
        return "?"
    if symbol.kind is SymbolKind.RECEITA:
        return format_servings(symbol.value)
    base = symbol.dimension.base_unit if symbol.dimension is not None else None
    return f"{format_number(symbol.value)} {base}" if base else format_number(symbol.value)

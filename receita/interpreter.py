"""Interpretação: executa escalar, compras e cronograma sobre um programa já validado."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Union

from receita.ast import (
    Ingredient,
    NodeVisitor,
    Program,
    Recipe,
    ScaleCommand,
    ScheduleCommand,
    ShoppingCommand,
    UnitDef,
    format_number,
    format_servings,
)
from receita.display import format_amount, format_clock, format_decimal, format_duration
from receita.evaluator import evaluate
from receita.types import Amount
from receita.units import Unit, UnitTable


@dataclass(frozen=True)
class RecipeValue:
    """Receita avaliada: quantidades na unidade base, na ordem de declaração."""

    name: str
    servings: Fraction
    ingredients: tuple[tuple[str, Amount], ...]
    steps: tuple[tuple[str, Amount], ...]

    def scaled_ingredients(self, servings: Fraction) -> tuple[tuple[str, Amount], ...]:
        factor = servings / self.servings
        return tuple((name, amount.scaled(factor)) for name, amount in self.ingredients)


@dataclass(frozen=True)
class ScaleResult:
    recipe: str
    base_servings: Fraction
    servings: Fraction
    ingredients: tuple[tuple[str, Amount], ...]

    @property
    def factor(self) -> Fraction:
        return self.servings / self.base_servings


@dataclass(frozen=True)
class ShoppingResult:
    targets: tuple[tuple[str, Fraction], ...]
    items: tuple[tuple[str, Amount], ...]


@dataclass(frozen=True)
class ScheduleEntry:
    recipe: str
    description: str
    start: Fraction
    end: Fraction


@dataclass(frozen=True)
class ScheduleResult:
    recipes: tuple[str, ...]
    start: tuple[int, int] | None
    entries: tuple[ScheduleEntry, ...]

    @property
    def total(self) -> Fraction:
        return self.entries[-1].end if self.entries else Fraction(0)


CommandResult = Union[ScaleResult, ShoppingResult, ScheduleResult]


class Interpreter(NodeVisitor):
    """Visitor de execução. Pressupõe um programa sem erros semânticos."""

    def __init__(self) -> None:
        self.units = UnitTable()
        self.recipes: dict[str, RecipeValue] = {}
        self.results: list[CommandResult] = []

    def run(self, program: Program) -> list[CommandResult]:
        self.visit(program)
        return self.results

    def visit_Program(self, node: Program) -> None:
        for declaration in node.declarations:
            self.visit(declaration)

    def visit_UnitDef(self, node: UnitDef) -> None:
        amount = evaluate(node.expr, self.units)
        self.units.register(Unit(node.name, amount.dimension, amount.value))

    def visit_Recipe(self, node: Recipe) -> None:
        if node.name in self.recipes:
            return
        ingredients: dict[str, Amount] = {}
        steps: list[tuple[str, Amount]] = []
        for item in node.items:
            if isinstance(item, Ingredient):
                ingredients[item.name] = evaluate(item.expr, self.units, ingredients)
            else:
                steps.append((item.description, evaluate(item.duration, self.units, ingredients)))
        self.recipes[node.name] = RecipeValue(
            node.name, node.servings, tuple(ingredients.items()), tuple(steps)
        )

    def visit_ScaleCommand(self, node: ScaleCommand) -> None:
        recipe = self.recipes[node.recipe]
        self.results.append(
            ScaleResult(
                recipe.name, recipe.servings, node.servings, recipe.scaled_ingredients(node.servings)
            )
        )

    def visit_ShoppingCommand(self, node: ShoppingCommand) -> None:
        targets: list[tuple[str, Fraction]] = []
        totals: dict[str, Amount] = {}
        for target in node.targets:
            recipe = self.recipes[target.recipe]
            servings = target.servings if target.servings is not None else recipe.servings
            targets.append((recipe.name, servings))
            for name, amount in recipe.scaled_ingredients(servings):
                totals[name] = totals[name].apply("+", amount) if name in totals else amount
        self.results.append(ShoppingResult(tuple(targets), tuple(sorted(totals.items()))))

    def visit_ScheduleCommand(self, node: ScheduleCommand) -> None:
        clock = Fraction(0)
        entries: list[ScheduleEntry] = []
        for name in node.recipes:
            for description, duration in self.recipes[name].steps:
                entries.append(ScheduleEntry(name, description, clock, clock + duration.value))
                clock += duration.value
        self.results.append(ScheduleResult(node.recipes, node.start, tuple(entries)))


def interpret(program: Program) -> list[CommandResult]:
    """Executa os comandos de `program`, que deve ter passado pela análise semântica."""
    return Interpreter().run(program)


def format_result(result: CommandResult) -> str:
    """Texto exibido para o resultado de um comando."""
    match result:
        case ScaleResult():
            header = (
                f"Receita {result.recipe} para {format_servings(result.servings)} "
                f"(rende {format_number(result.base_servings)}, fator {format_decimal(result.factor)})"
            )
            return _with_rows(header, [(name, format_amount(a)) for name, a in result.ingredients])
        case ShoppingResult():
            targets = ", ".join(f"{name} ({format_servings(s)})" for name, s in result.targets)
            rows = [(name, format_amount(a)) for name, a in result.items]
            return _with_rows(f"Lista de compras: {targets}", rows)
        case ScheduleResult():
            header = f"Cronograma: {', '.join(result.recipes)}"
            if result.start is not None:
                header += f" (início {result.start[0]:02d}:{result.start[1]:02d})"
            rows = [
                (
                    f"{format_clock(e.start, result.start)} - {format_clock(e.end, result.start)}",
                    e.recipe,
                    e.description,
                )
                for e in result.entries
            ]
            footer = f"  Tempo total: {format_duration(result.total)}"
            return _with_rows(header, rows) + "\n" + footer
    raise TypeError(f"resultado desconhecido: {result!r}")


def _with_rows(header: str, rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return f"{header}\n  (nada)"
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    lines = [header]
    for row in rows:
        cells = [cell.ljust(width) for cell, width in zip(row, widths)] + [row[-1]]
        lines.append("  " + "  ".join(cells))
    return "\n".join(lines)

"""Nós da árvore sintática abstrata. Todo nó guarda a linha em que começa."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Union


@dataclass(frozen=True, kw_only=True)
class Node:
    line: int


# Expressões


@dataclass(frozen=True)
class Quantity(Node):
    """Literal numérico, com unidade opcional: `300 g` ou `0.01`."""

    value: Fraction
    unit: str | None


@dataclass(frozen=True)
class Reference(Node):
    """Referência a um ingrediente já declarado na receita."""

    name: str


@dataclass(frozen=True)
class BinaryOp(Node):
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Negation(Node):
    operand: Expr


Expr = Union[Quantity, Reference, BinaryOp, Negation]


# Declarações


@dataclass(frozen=True)
class UnitDef(Node):
    name: str
    expr: Expr


@dataclass(frozen=True)
class Ingredient(Node):
    name: str
    expr: Expr


@dataclass(frozen=True)
class Step(Node):
    description: str
    duration: Expr
    uses: tuple[str, ...]


RecipeItem = Union[Ingredient, Step]


@dataclass(frozen=True)
class Recipe(Node):
    name: str
    servings: Fraction
    items: tuple[RecipeItem, ...]

    @property
    def ingredients(self) -> tuple[Ingredient, ...]:
        return tuple(item for item in self.items if isinstance(item, Ingredient))

    @property
    def steps(self) -> tuple[Step, ...]:
        return tuple(item for item in self.items if isinstance(item, Step))


# Comandos


@dataclass(frozen=True)
class ScaleCommand(Node):
    recipe: str
    servings: Fraction


@dataclass(frozen=True)
class ShoppingTarget(Node):
    recipe: str
    servings: Fraction | None


@dataclass(frozen=True)
class ShoppingCommand(Node):
    targets: tuple[ShoppingTarget, ...]


@dataclass(frozen=True)
class ScheduleCommand(Node):
    recipes: tuple[str, ...]
    start: tuple[int, int] | None


Declaration = Union[UnitDef, Recipe, ScaleCommand, ShoppingCommand, ScheduleCommand]


@dataclass(frozen=True)
class Program(Node):
    declarations: tuple[Declaration, ...]

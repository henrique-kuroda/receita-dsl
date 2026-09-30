"""Nós da árvore sintática abstrata. Todo nó guarda a linha em que começa."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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


def format_number(value: Fraction) -> str:
    """Representação exata: decimal quando finita (0.5), fração caso contrário (1/3)."""
    if value.denominator == 1:
        return str(value.numerator)
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    if Fraction(decimal) == value:
        return format(decimal, "f")
    return f"{value.numerator}/{value.denominator}"


def format_tree(node: Node) -> str:
    """AST em árvore indentada, com a linha de cada declaração."""
    lines = [_label(node)]
    _append_children(node, "", lines)
    return "\n".join(lines)


def _append_children(node: Node, prefix: str, lines: list[str]) -> None:
    children = _children(node)
    for index, child in enumerate(children):
        last = index == len(children) - 1
        lines.append(f"{prefix}{'└── ' if last else '├── '}{_label(child)}")
        _append_children(child, prefix + ("    " if last else "│   "), lines)


def _children(node: Node) -> tuple[Node, ...]:
    match node:
        case Program(declarations=declarations):
            return declarations
        case Recipe(items=items):
            return items
        case ShoppingCommand(targets=targets):
            return targets
        case UnitDef(expr=expr) | Ingredient(expr=expr):
            return (expr,)
        case Step(duration=duration):
            return (duration,)
        case BinaryOp(left=left, right=right):
            return (left, right)
        case Negation(operand=operand):
            return (operand,)
    return ()


def _label(node: Node) -> str:
    match node:
        case Program():
            return "Programa"
        case UnitDef(name=name):
            text = f"Unidade {name}"
        case Recipe(name=name, servings=servings):
            text = f"Receita {name} rende {format_servings(servings)}"
        case Ingredient(name=name):
            text = f"Ingrediente {name}"
        case Step(description=description, uses=uses):
            text = f'Passo "{description}"' + (f" usa {', '.join(uses)}" if uses else "")
        case ScaleCommand(recipe=recipe, servings=servings):
            text = f"Escalar {recipe} para {format_servings(servings)}"
        case ShoppingCommand():
            text = "Compras"
        case ShoppingTarget(recipe=recipe, servings=servings):
            return recipe + (f" para {format_servings(servings)}" if servings is not None else " (rendimento base)")
        case ScheduleCommand(recipes=recipes, start=start):
            text = f"Cronograma {', '.join(recipes)}"
            if start is not None:
                text += f" início {start[0]:02d}:{start[1]:02d}"
        case Quantity(value=value, unit=unit):
            return f"Quantidade {format_number(value)}" + (f" {unit}" if unit else "")
        case Reference(name=name):
            return f"Referência {name}"
        case BinaryOp(op=op):
            return f"Operação {op}"
        case Negation():
            return "Negação"
        case _:
            return type(node).__name__
    return f"{text}  [linha {node.line}]"


def format_servings(value: Fraction) -> str:
    """Rendimento por extenso: 8 porções, 1 porção."""
    return f"{format_number(value)} {'porção' if value == 1 else 'porções'}"


class NodeVisitor:
    """Despacha `visit(node)` para `visit_<NomeDoNó>`."""

    def visit(self, node: Node):
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise NotImplementedError(f"{type(self).__name__} não trata {type(node).__name__}")
        return method(node)

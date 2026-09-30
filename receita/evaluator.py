"""Avaliação de expressões para valores tipados (Amount)."""

from __future__ import annotations

from typing import Mapping

from receita.ast import BinaryOp, Expr, Negation, NodeVisitor, Quantity, Reference
from receita.types import Amount
from receita.units import Dimension, UnitTable


class ExpressionEvaluator(NodeVisitor):
    """Calcula o valor de uma expressão já verificada pela análise semântica."""

    def __init__(self, units: UnitTable, ingredients: Mapping[str, Amount]) -> None:
        self.units = units
        self.ingredients = ingredients

    def visit_Quantity(self, node: Quantity) -> Amount:
        if node.unit is None:
            return Amount(node.value, Dimension.ESCALAR)
        unit = self.units.lookup(node.unit)
        return Amount(unit.to_base(node.value), unit.dimension)

    def visit_Reference(self, node: Reference) -> Amount:
        return self.ingredients[node.name]

    def visit_BinaryOp(self, node: BinaryOp) -> Amount:
        return self.visit(node.left).apply(node.op, self.visit(node.right))

    def visit_Negation(self, node: Negation) -> Amount:
        return -self.visit(node.operand)


def evaluate(expr: Expr, units: UnitTable, ingredients: Mapping[str, Amount] | None = None) -> Amount:
    """Valor de `expr` na unidade base; lança ZeroDivisionError em divisão por zero."""
    return ExpressionEvaluator(units, ingredients or {}).visit(expr)

"""Tipos dimensionais: regras de operação entre dimensões e valores tipados."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from receita.units import Dimension

INGREDIENT_DIMENSIONS = frozenset({Dimension.MASSA, Dimension.VOLUME, Dimension.CONTAGEM})


class DimensionError(Exception):
    """Operação entre dimensões incompatíveis."""


_OPERATION_TEMPLATES = {
    "+": "não é possível somar {left} com {right}",
    "-": "não é possível subtrair {right} de {left}",
    "*": "não é possível multiplicar {left} por {right} (produto entre quantidades não é suportado)",
    "/": "não é possível dividir {left} por {right}",
}


def binary_result(op: str, left: Dimension, right: Dimension) -> Dimension:
    """Dimensão do resultado de `left op right`; lança DimensionError se a operação não é válida.

    - `+` e `-`: mesma dimensão (inclusive escalar com escalar).
    - `*`: ao menos um operando escalar.
    - `/`: divisor escalar mantém a dimensão; mesma dimensão resulta em escalar.
    """
    scalar = Dimension.ESCALAR
    if op in ("+", "-") and left is right:
        return left
    if op == "*" and scalar in (left, right):
        return right if left is scalar else left
    if op == "/":
        if right is scalar:
            return left
        if left is right:
            return scalar
    raise DimensionError(
        _OPERATION_TEMPLATES[op].format(left=left.describe(), right=right.describe())
    )


@dataclass(frozen=True)
class Amount:
    """Valor tipado: magnitude na unidade base da dimensão (g, ml, un, min)."""

    value: Fraction
    dimension: Dimension

    def apply(self, op: str, other: Amount) -> Amount:
        dimension = binary_result(op, self.dimension, other.dimension)
        if op == "+":
            value = self.value + other.value
        elif op == "-":
            value = self.value - other.value
        elif op == "*":
            value = self.value * other.value
        else:
            value = self.value / other.value
        return Amount(value, dimension)

    def __neg__(self) -> Amount:
        return Amount(-self.value, self.dimension)

    def scaled(self, factor: Fraction) -> Amount:
        return Amount(self.value * factor, self.dimension)

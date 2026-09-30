from fractions import Fraction

import pytest

from receita.evaluator import evaluate
from receita.parser import parse
from receita.types import Amount, DimensionError, binary_result
from receita.units import Dimension, UnitTable

M, V, C, T, E = (
    Dimension.MASSA, Dimension.VOLUME, Dimension.CONTAGEM, Dimension.TEMPO, Dimension.ESCALAR,
)


@pytest.mark.parametrize(
    ("op", "left", "right", "result"),
    [
        ("+", M, M, M),
        ("-", T, T, T),
        ("+", E, E, E),
        ("*", E, V, V),
        ("*", C, E, C),
        ("*", E, E, E),
        ("/", M, E, M),
        ("/", V, V, E),
        ("/", E, E, E),
    ],
)
def test_operacoes_validas(op, left, right, result):
    assert binary_result(op, left, right) is result


@pytest.mark.parametrize(
    ("op", "left", "right", "message"),
    [
        ("+", M, V, "não é possível somar massa (g) com volume (ml)"),
        ("+", E, M, "não é possível somar escalar com massa (g)"),
        ("-", T, C, "não é possível subtrair contagem (un) de tempo (min)"),
        ("*", M, M, "não é possível multiplicar massa (g) por massa (g) (produto entre quantidades não é suportado)"),
        ("/", M, V, "não é possível dividir massa (g) por volume (ml)"),
        ("/", E, T, "não é possível dividir escalar por tempo (min)"),
    ],
)
def test_operacoes_invalidas(op, left, right, message):
    with pytest.raises(DimensionError) as info:
        binary_result(op, left, right)
    assert str(info.value) == message


def expr(source: str):
    return parse(f"unidade u = {source};").program.declarations[0].expr


@pytest.mark.parametrize(
    ("source", "value", "dimension"),
    [
        ("300 g", Fraction(300), M),
        ("0.5 kg + 200 g", Fraction(700), M),
        ("1 h - 20 min", Fraction(40), T),
        ("2 xicara / 4", Fraction(120), V),
        ("1 kg / 250 g", Fraction(4), E),
        ("-(1 duzia) * 2", Fraction(-24), C),
        ("90 s", Fraction(3, 2), T),
        ("0.1 + 0.2", Fraction(3, 10), E),
    ],
)
def test_avalia_para_unidade_base(source, value, dimension):
    assert evaluate(expr(source), UnitTable()) == Amount(value, dimension)


def test_avalia_referencia_a_ingrediente():
    farinha = Amount(Fraction(480), V)
    assert evaluate(expr("farinha * 0.01"), UnitTable(), {"farinha": farinha}) == Amount(Fraction(24, 5), V)


def test_avaliacao_com_unidade_declarada():
    units = UnitTable()
    units.define("pitada", Fraction(1, 2), "g")
    assert evaluate(expr("4 pitada"), units) == Amount(Fraction(2), M)


def test_divisao_por_zero():
    with pytest.raises(ZeroDivisionError):
        evaluate(expr("1 g / (2 - 2)"), UnitTable())


def test_escala_mantem_dimensao():
    assert Amount(Fraction(3), C).scaled(Fraction(5, 2)) == Amount(Fraction(15, 2), C)

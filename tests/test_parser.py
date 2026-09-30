from fractions import Fraction

import pytest

from receita.ast import (
    BinaryOp,
    Ingredient,
    Negation,
    Program,
    Quantity,
    Recipe,
    Reference,
    ScaleCommand,
    ScheduleCommand,
    ShoppingCommand,
    ShoppingTarget,
    Step,
    UnitDef,
    format_number,
)
from receita.parser import parse


def parse_ok(source: str) -> Program:
    result = parse(source)
    assert result.errors == []
    return result.program


def parse_expr(expr: str):
    [ingredient] = parse_ok(f"receita r rende 1 porcao {{ ingrediente x = {expr}; }}").declarations[0].items
    return ingredient.expr


def q(value, unit=None, line=1) -> Quantity:
    return Quantity(Fraction(value), unit, line=line)


def test_programa_vazio():
    assert parse_ok("") == Program((), line=1)
    assert parse_ok("# só comentário\n") == Program((), line=1)


def test_def_unidade():
    [decl] = parse_ok("unidade pitada = 0.5 g;").declarations
    assert decl == UnitDef("pitada", q("0.5", "g"), line=1)


def test_receita_com_ingredientes_e_passos_em_ordem():
    source = """receita bolo rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    passo "Misturar" dura 10 min usa farinha, ovos;
    ingrediente ovos = 3 un;
    passo "Assar" dura 40 min;
}"""
    [recipe] = parse_ok(source).declarations
    assert recipe == Recipe(
        "bolo",
        Fraction(8),
        (
            Ingredient("farinha", q(2, "xicara", 2), line=2),
            Step("Misturar", q(10, "min", 3), ("farinha", "ovos"), line=3),
            Ingredient("ovos", q(3, "un", 4), line=4),
            Step("Assar", q(40, "min", 5), (), line=5),
        ),
        line=1,
    )
    assert [i.name for i in recipe.ingredients] == ["farinha", "ovos"]
    assert [s.description for s in recipe.steps] == ["Misturar", "Assar"]


def test_receita_vazia_e_sintaticamente_valida():
    [recipe] = parse_ok("receita nada rende 1 porcao { }").declarations
    assert recipe.items == ()


def test_comando_escalar():
    [cmd] = parse_ok("escalar bolo para 20 porcoes;").declarations
    assert cmd == ScaleCommand("bolo", Fraction(20), line=1)


def test_comando_compras_com_e_sem_porcoes():
    [cmd] = parse_ok("compras bolo para 20 porcoes, cobertura;").declarations
    assert cmd == ShoppingCommand(
        (
            ShoppingTarget("bolo", Fraction(20), line=1),
            ShoppingTarget("cobertura", None, line=1),
        ),
        line=1,
    )


def test_comando_cronograma():
    first, second = parse_ok("cronograma bolo, cobertura inicio 14:00;\ncronograma bolo;").declarations
    assert first == ScheduleCommand(("bolo", "cobertura"), (14, 0), line=1)
    assert second == ScheduleCommand(("bolo",), None, line=2)


def test_quantidade_sem_unidade_e_referencia():
    assert parse_expr("0.01") == q("0.01")
    assert parse_expr("farinha") == Reference("farinha", line=1)


def test_multiplicacao_tem_precedencia_sobre_soma():
    assert parse_expr("1 kg + 2 * 3 g") == BinaryOp(
        "+", q(1, "kg"), BinaryOp("*", q(2), q(3, "g"), line=1), line=1
    )


def test_operadores_de_mesma_precedencia_associam_a_esquerda():
    assert parse_expr("1 h - 20 min - 5 min") == BinaryOp(
        "-", BinaryOp("-", q(1, "h"), q(20, "min"), line=1), q(5, "min"), line=1
    )
    assert parse_expr("farinha / 2 / 3") == BinaryOp(
        "/", BinaryOp("/", Reference("farinha", line=1), q(2), line=1), q(3), line=1
    )


def test_parenteses_alteram_a_precedencia():
    assert parse_expr("(1 kg + 200 g) * 2") == BinaryOp(
        "*", BinaryOp("+", q(1, "kg"), q(200, "g"), line=1), q(2), line=1
    )


def test_menos_unario():
    assert parse_expr("-2 g * 3") == BinaryOp("*", Negation(q(2, "g"), line=1), q(3), line=1)
    assert parse_expr("- -1 un") == Negation(Negation(q(1, "un"), line=1), line=1)


def test_linha_de_cada_declaracao():
    source = "\n# receitas\nunidade p = 1 g;\n\nescalar a para 2 porcoes;\ncompras a;\n"
    assert [d.line for d in parse_ok(source).declarations] == [3, 5, 6]


def test_programa_do_enunciado():
    source = """
unidade pitada = 0.5 g;
unidade xicara_farinha = 120 g;

receita bolo_cenoura rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    ingrediente acucar  = 300 g;
    ingrediente ovos    = 3 un;
    ingrediente cenoura = 0.5 kg;
    ingrediente oleo    = 200 ml;
    ingrediente sal     = farinha * 0.01;

    passo "Bater cenoura, ovos e óleo no liquidificador" dura 5 min usa cenoura, ovos, oleo;
    passo "Misturar com farinha e açúcar" dura 10 min usa farinha, acucar, sal;
    passo "Assar a 180 graus" dura 1 h - 20 min;
}

receita cobertura rende 8 porcoes {
    ingrediente acucar = 1 xicara;
    ingrediente chocolate = 4 colher_sopa;
    passo "Levar ao fogo mexendo" dura 8 min usa acucar, chocolate;
}

escalar bolo_cenoura para 20 porcoes;
compras bolo_cenoura para 20 porcoes, cobertura para 20 porcoes;
cronograma bolo_cenoura, cobertura inicio 14:00;
"""
    declarations = parse_ok(source).declarations
    assert [type(d).__name__ for d in declarations] == [
        "UnitDef", "UnitDef", "Recipe", "Recipe",
        "ScaleCommand", "ShoppingCommand", "ScheduleCommand",
    ]
    bolo = declarations[2]
    assert len(bolo.ingredients) == 6
    assert bolo.steps[2].duration == BinaryOp("-", q(1, "h", 15), q(20, "min", 15), line=15)


@pytest.mark.parametrize(
    ("value", "text"),
    [(Fraction(3), "3"), (Fraction(1, 2), "0.5"), (Fraction(1, 100), "0.01"), (Fraction(1, 3), "1/3")],
)
def test_format_number_e_exato(value, text):
    assert format_number(value) == text

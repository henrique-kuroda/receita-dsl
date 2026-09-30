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
    format_tree,
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


def errors(source: str) -> list[str]:
    result = parse(source)
    assert result.program is None
    return [str(e) for e in result.errors]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "unidade pitada = ;",
            "encontrou símbolo ';' quando esperava identificador, número, '(' ou '-'",
        ),
        (
            "receita bolo rende porcoes { }",
            "encontrou palavra reservada 'porcoes' quando esperava número",
        ),
        (
            "receita bolo rende 8 porcoes ingrediente a = 1 g; }",
            "encontrou palavra reservada 'ingrediente' quando esperava '{'",
        ),
        (
            'receita bolo rende 8 porcoes { passo "Assar" 40 min; }',
            "encontrou número '40' quando esperava 'dura'",
        ),
        (
            'receita bolo rende 8 porcoes { passo "Assar" dura 40 min usa; }',
            "encontrou símbolo ';' quando esperava identificador",
        ),
        (
            "escalar bolo para 20;",
            "encontrou símbolo ';' quando esperava 'porcoes'",
        ),
        (
            "compras bolo, ;",
            "encontrou símbolo ';' quando esperava identificador",
        ),
        (
            "cronograma bolo inicio 14;",
            "encontrou número '14' quando esperava hora (HH:MM)",
        ),
        (
            "bolo para 2 porcoes;",
            "encontrou identificador 'bolo' quando esperava 'compras', 'cronograma', "
            "'escalar', 'receita', 'unidade' ou fim do arquivo",
        ),
        (
            "unidade p = 1 g * * 2;",
            "encontrou símbolo '*' quando esperava identificador, número, '(' ou '-'",
        ),
        (
            'unidade p = "meio grama";',
            "encontrou texto \"meio grama\" quando esperava identificador, número, '(' ou '-'",
        ),
    ],
)
def test_erro_sintatico_informa_encontrado_e_esperado(source, message):
    assert errors(source) == [f"erro sintático [linha 1]: {message}"]


def test_ponto_e_virgula_faltando_aponta_a_linha_seguinte():
    source = "receita bolo rende 8 porcoes {\n    ingrediente a = 2 g\n    ingrediente b = 1 g;\n}"
    assert errors(source) == [
        "erro sintático [linha 3]: encontrou palavra reservada 'ingrediente' "
        "quando esperava '+', '-', '*', '/' ou ';'"
    ]


def test_fim_de_arquivo_inesperado_usa_a_ultima_linha():
    assert errors("receita r rende 2 porcoes {\n  ingrediente a = 1 g;\n\n# fim") == [
        "erro sintático [linha 2]: encontrou o fim do arquivo "
        "quando esperava '}', 'ingrediente' ou 'passo'"
    ]


def test_fim_de_arquivo_em_programa_de_uma_linha():
    assert errors("unidade p = 1 g") == [
        "erro sintático [linha 1]: encontrou o fim do arquivo quando esperava '+', '-', '*', '/' ou ';'"
    ]


def test_chave_sobrando():
    assert errors("receita r rende 2 porcoes { } }") == [
        "erro sintático [linha 1]: encontrou símbolo '}' quando esperava 'compras', 'cronograma', "
        "'escalar', 'receita', 'unidade' ou fim do arquivo"
    ]


def test_recupera_e_reporta_erros_em_declaracoes_diferentes():
    source = "unidade p = ;\nunidade q = 1 g;\nescalar bolo para porcoes;\ncompras bolo;"
    assert [e.split("]")[0] for e in errors(source)] == [
        "erro sintático [linha 1", "erro sintático [linha 3",
    ]


def test_recupera_dentro_da_receita():
    source = """receita bolo rende 8 porcoes {
    ingrediente a = ;
    ingrediente b = 2 g;
    passo "Assar" dura min 40;
}
escalar bolo para 2 porcoes;"""
    assert errors(source) == [
        "erro sintático [linha 2]: encontrou símbolo ';' quando esperava identificador, número, '(' ou '-'",
        "erro sintático [linha 4]: encontrou número '40' quando esperava '+', '-', '*', '/', ';' ou 'usa'",
    ]


def test_erro_lexico_interrompe_antes_do_parser():
    result = parse("unidade p = 1 g @;\nunidade = ;")
    assert result.program is None
    assert [str(e) for e in result.errors] == ["erro léxico [linha 1]: caractere inesperado '@'"]


def test_format_tree():
    source = """receita bolo rende 1 porcao {
    ingrediente sal = -(farinha * 0.01);
    passo "Assar" dura 1 h - 20 min usa sal;
}
compras bolo para 20 porcoes, bolo;
cronograma bolo inicio 9:05;"""
    assert format_tree(parse_ok(source)) == """\
Programa
├── Receita bolo rende 1 porção  [linha 1]
│   ├── Ingrediente sal  [linha 2]
│   │   └── Negação
│   │       └── Operação *
│   │           ├── Referência farinha
│   │           └── Quantidade 0.01
│   └── Passo "Assar" usa sal  [linha 3]
│       └── Operação -
│           ├── Quantidade 1 h
│           └── Quantidade 20 min
├── Compras  [linha 5]
│   ├── bolo para 20 porções
│   └── bolo (rendimento base)
└── Cronograma bolo início 09:05  [linha 6]"""

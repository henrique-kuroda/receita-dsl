from fractions import Fraction

import pytest

from receita.lexer import tokenize


def types(source: str) -> list[str]:
    return [t.type for t in tokenize(source)]


@pytest.mark.parametrize(
    ("word", "token_type"),
    [
        ("unidade", "UNIDADE"),
        ("receita", "RECEITA"),
        ("rende", "RENDE"),
        ("porcoes", "PORCOES"),
        ("porcao", "PORCOES"),
        ("ingrediente", "INGREDIENTE"),
        ("passo", "PASSO"),
        ("dura", "DURA"),
        ("usa", "USA"),
        ("escalar", "ESCALAR"),
        ("para", "PARA"),
        ("compras", "COMPRAS"),
        ("cronograma", "CRONOGRAMA"),
        ("inicio", "INICIO"),
    ],
)
def test_palavra_reservada(word, token_type):
    assert types(word) == [token_type]


@pytest.mark.parametrize("word", ["receitas", "Receita", "passo2", "_usa", "g", "min", "colher_sopa"])
def test_identificador_que_parece_palavra_reservada(word):
    [token] = tokenize(word)
    assert (token.type, token.value) == ("ID", word)


@pytest.mark.parametrize(
    ("lexeme", "value"),
    [("3", Fraction(3)), ("0.5", Fraction(1, 2)), ("0.1", Fraction(1, 10)), ("120", Fraction(120))],
)
def test_numero_vira_fracao_exata(lexeme, value):
    [token] = tokenize(lexeme)
    assert token.type == "NUM"
    assert token.value == value
    assert isinstance(token.value, Fraction)


def test_quantidade_e_numero_seguido_de_unidade():
    tokens = tokenize("300 g 2xicara")
    assert [(t.type, t.value) for t in tokens] == [
        ("NUM", 300), ("ID", "g"), ("NUM", 2), ("ID", "xicara"),
    ]


def test_string_aceita_acentos_e_perde_as_aspas():
    [token] = tokenize('"Misturar com farinha e açúcar"')
    assert token.type == "STRING"
    assert token.value == "Misturar com farinha e açúcar"


def test_string_vazia():
    [token] = tokenize('""')
    assert (token.type, token.value) == ("STRING", "")


@pytest.mark.parametrize(("lexeme", "value"), [("14:00", (14, 0)), ("9:30", (9, 30)), ("00:05", (0, 5))])
def test_hora(lexeme, value):
    [token] = tokenize(lexeme)
    assert (token.type, token.value) == ("HORA", value)


def test_literais():
    assert types("= ; { } , + - * / ( )") == list("=;{},+-*/()")


def test_comentario_e_ignorado():
    assert types("# só comentário\nunidade # outro\n# fim") == ["UNIDADE"]


def test_contagem_de_linhas():
    source = "unidade\n\n# comentário\n  receita\r\n\tpasso\n"
    assert [(t.type, t.lineno) for t in tokenize(source)] == [
        ("UNIDADE", 1), ("RECEITA", 4), ("PASSO", 5),
    ]


def test_posicao_do_token_recupera_o_lexema():
    source = "ingrediente ovos = 3 un;"
    lexemes = [source[t.index:t.end] for t in tokenize(source)]
    assert lexemes == ["ingrediente", "ovos", "=", "3", "un", ";"]


def test_programa_completo():
    source = """
unidade pitada = 0.5 g;
receita bolo rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    passo "Assar" dura 1 h - 20 min usa farinha;
}
escalar bolo para 20 porcoes;
compras bolo para 20 porcoes, bolo;
cronograma bolo inicio 14:00;
"""
    assert types(source) == [
        "UNIDADE", "ID", "=", "NUM", "ID", ";",
        "RECEITA", "ID", "RENDE", "NUM", "PORCOES", "{",
        "INGREDIENTE", "ID", "=", "NUM", "ID", ";",
        "PASSO", "STRING", "DURA", "NUM", "ID", "-", "NUM", "ID", "USA", "ID", ";",
        "}",
        "ESCALAR", "ID", "PARA", "NUM", "PORCOES", ";",
        "COMPRAS", "ID", "PARA", "NUM", "PORCOES", ",", "ID", ";",
        "CRONOGRAMA", "ID", "INICIO", "HORA", ";",
    ]

from fractions import Fraction

import pytest

from receita.lexer import tokenize as lex


def tokenize(source: str):
    tokens, errors = lex(source)
    assert errors == []
    return tokens


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


def messages(source: str) -> list[str]:
    _, errors = lex(source)
    return [str(e) for e in errors]


def test_caractere_inesperado():
    assert messages("unidade @ pitada") == ["erro léxico [linha 1]: caractere inesperado '@'"]


def test_erro_informa_a_linha_correta():
    assert messages("receita\n# comentário\n\n  $") == ["erro léxico [linha 4]: caractere inesperado '$'"]


def test_coleta_varios_erros_e_continua():
    tokens, errors = lex("ingrediente @ ovos = 3 un; %\nreceita")
    assert [e.line for e in errors] == [1, 1]
    assert [t.type for t in tokens] == ["INGREDIENTE", "ID", "=", "NUM", "ID", ";", "RECEITA"]


def test_identificador_com_acento():
    assert messages("ingrediente açúcar = 300 g;") == [
        "erro léxico [linha 1]: identificador 'açúcar' tem caracteres não permitidos "
        "(use letras sem acento, dígitos e _)"
    ]


def test_string_nao_terminada_descarta_o_resto_da_linha():
    tokens, errors = lex('passo "Assar dura 5 min;\nreceita')
    assert [str(e) for e in errors] == ["erro léxico [linha 1]: string não terminada"]
    assert [(t.type, t.lineno) for t in tokens] == [("PASSO", 1), ("RECEITA", 2)]


def test_string_nao_atravessa_linhas():
    assert messages('"primeira\nsegunda"') == [
        "erro léxico [linha 1]: string não terminada",
        "erro léxico [linha 2]: string não terminada",
    ]


@pytest.mark.parametrize("lexeme", ["24:00", "12:60", "99:99"])
def test_hora_invalida(lexeme):
    assert messages(lexeme) == [f"erro léxico [linha 1]: hora inválida '{lexeme}'"]


def test_decimal_sem_parte_inteira_e_erro():
    assert messages(".5 g") == ["erro léxico [linha 1]: caractere inesperado '.'"]


def test_virgula_decimal_nao_forma_um_numero():
    assert types("1,5 kg") == ["NUM", ",", "NUM", "ID"]

"""Análise léxica da linguagem Receita."""

from __future__ import annotations

from fractions import Fraction

from sly import Lexer
from sly.lex import Token


class RecipeLexer(Lexer):
    """Lexer SLY: converte o texto-fonte em tokens com número de linha."""

    tokens = {
        ID, NUM, STRING, HORA,
        UNIDADE, RECEITA, RENDE, PORCOES, INGREDIENTE, PASSO, DURA, USA,
        ESCALAR, PARA, COMPRAS, CRONOGRAMA, INICIO,
    }
    literals = {"=", ";", "{", "}", ",", "+", "-", "*", "/", "(", ")"}

    ignore = " \t\r"
    ignore_comment = r"\#[^\n]*"

    HORA = r"\d{1,2}:\d{2}"
    NUM = r"\d+(\.\d+)?"
    STRING = r'"[^"\n]*"'
    ID = r"[a-zA-Z_][a-zA-Z0-9_]*"
    ID["unidade"] = UNIDADE
    ID["receita"] = RECEITA
    ID["rende"] = RENDE
    ID["porcoes"] = PORCOES
    ID["porcao"] = PORCOES
    ID["ingrediente"] = INGREDIENTE
    ID["passo"] = PASSO
    ID["dura"] = DURA
    ID["usa"] = USA
    ID["escalar"] = ESCALAR
    ID["para"] = PARA
    ID["compras"] = COMPRAS
    ID["cronograma"] = CRONOGRAMA
    ID["inicio"] = INICIO

    @_(r"\n+")
    def ignore_newline(self, t: Token) -> None:
        self.lineno += len(t.value)

    def HORA(self, t: Token) -> Token:
        hours, minutes = t.value.split(":")
        t.value = (int(hours), int(minutes))
        return t

    def NUM(self, t: Token) -> Token:
        t.value = Fraction(t.value)
        return t

    def STRING(self, t: Token) -> Token:
        t.value = t.value[1:-1]
        return t


def tokenize(source: str) -> list[Token]:
    """Retorna a lista de tokens de `source`."""
    return list(RecipeLexer().tokenize(source))

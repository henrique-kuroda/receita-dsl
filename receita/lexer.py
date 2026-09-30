"""Análise léxica da linguagem Receita."""

from __future__ import annotations

from fractions import Fraction

from sly import Lexer
from sly.lex import Token

from receita.errors import LexicalError


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
    ID = r"[^\W\d]\w*"
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

    def __init__(self) -> None:
        self.errors: list[LexicalError] = []

    @_(r"\n+")
    def ignore_newline(self, t: Token) -> None:
        self.lineno += len(t.value)

    def ID(self, t: Token) -> Token:
        if not t.value.isascii():
            self._report(
                f"identificador '{t.value}' tem caracteres não permitidos "
                "(use letras sem acento, dígitos e _)",
                t.lineno,
            )
        return t

    def HORA(self, t: Token) -> Token:
        hours, minutes = (int(part) for part in t.value.split(":"))
        if hours > 23 or minutes > 59:
            self._report(f"hora inválida '{t.value}'", t.lineno)
        t.value = (hours, minutes)
        return t

    def NUM(self, t: Token) -> Token:
        t.value = Fraction(t.value)
        return t

    def STRING(self, t: Token) -> Token:
        t.value = t.value[1:-1]
        return t

    def error(self, t: Token) -> None:
        if t.value.startswith('"'):
            self._report("string não terminada", self.lineno)
            line_end = self.text.find("\n", self.index)
            self.index = len(self.text) if line_end == -1 else line_end
        else:
            self._report(f"caractere inesperado '{t.value[0]}'", self.lineno)
            self.index += 1

    def _report(self, message: str, line: int) -> None:
        self.errors.append(LexicalError(message, line))


def tokenize(source: str) -> tuple[list[Token], list[LexicalError]]:
    """Retorna os tokens de `source` e todos os erros léxicos encontrados."""
    lexer = RecipeLexer()
    tokens = list(lexer.tokenize(source))
    return tokens, lexer.errors

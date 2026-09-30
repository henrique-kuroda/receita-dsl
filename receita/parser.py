"""Análise sintática da linguagem Receita (LALR, gerada com SLY)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sly import Parser
from sly.lex import Token

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
from receita.errors import ReceitaError, SyntacticError
from receita.lexer import RecipeLexer, tokenize


class RecipeParser(Parser):
    """Parser SLY: constrói a AST a partir da lista de tokens."""

    tokens = RecipeLexer.tokens
    start = "programa"

    @_("declaracoes")
    def programa(self, p):
        return Program(tuple(p.declaracoes), line=1)

    @_("declaracoes declaracao")
    def declaracoes(self, p):
        p.declaracoes.append(p.declaracao)
        return p.declaracoes

    @_("")
    def declaracoes(self, p):
        return []

    @_("def_unidade", "def_receita", "comando")
    def declaracao(self, p):
        return p[0]

    @_("UNIDADE ID '=' expr ';'")
    def def_unidade(self, p):
        return UnitDef(p.ID, p.expr, line=p.lineno)

    @_("RECEITA ID RENDE NUM PORCOES '{' itens '}'")
    def def_receita(self, p):
        return Recipe(p.ID, p.NUM, tuple(p.itens), line=p.lineno)

    @_("itens item_receita")
    def itens(self, p):
        p.itens.append(p.item_receita)
        return p.itens

    @_("")
    def itens(self, p):
        return []

    @_("ingrediente", "passo")
    def item_receita(self, p):
        return p[0]

    @_("INGREDIENTE ID '=' expr ';'")
    def ingrediente(self, p):
        return Ingredient(p.ID, p.expr, line=p.lineno)

    @_("PASSO STRING DURA expr ';'")
    def passo(self, p):
        return Step(p.STRING, p.expr, (), line=p.lineno)

    @_("PASSO STRING DURA expr USA lista_ids ';'")
    def passo(self, p):
        return Step(p.STRING, p.expr, tuple(p.lista_ids), line=p.lineno)

    @_("ESCALAR ID PARA NUM PORCOES ';'")
    def comando(self, p):
        return ScaleCommand(p.ID, p.NUM, line=p.lineno)

    @_("COMPRAS alvos ';'")
    def comando(self, p):
        return ShoppingCommand(tuple(p.alvos), line=p.lineno)

    @_("CRONOGRAMA lista_ids ';'")
    def comando(self, p):
        return ScheduleCommand(tuple(p.lista_ids), None, line=p.lineno)

    @_("CRONOGRAMA lista_ids INICIO HORA ';'")
    def comando(self, p):
        return ScheduleCommand(tuple(p.lista_ids), p.HORA, line=p.lineno)

    @_("alvos ',' alvo")
    def alvos(self, p):
        p.alvos.append(p.alvo)
        return p.alvos

    @_("alvo")
    def alvos(self, p):
        return [p.alvo]

    @_("ID")
    def alvo(self, p):
        return ShoppingTarget(p.ID, None, line=p.lineno)

    @_("ID PARA NUM PORCOES")
    def alvo(self, p):
        return ShoppingTarget(p.ID, p.NUM, line=p.lineno)

    @_("lista_ids ',' ID")
    def lista_ids(self, p):
        p.lista_ids.append(p.ID)
        return p.lista_ids

    @_("ID")
    def lista_ids(self, p):
        return [p.ID]

    @_("expr '+' termo", "expr '-' termo")
    def expr(self, p):
        return BinaryOp(p[1], p.expr, p.termo, line=p.expr.line)

    @_("termo")
    def expr(self, p):
        return p.termo

    @_("termo '*' fator", "termo '/' fator")
    def termo(self, p):
        return BinaryOp(p[1], p.termo, p.fator, line=p.termo.line)

    @_("fator")
    def termo(self, p):
        return p.fator

    @_("NUM ID")
    def fator(self, p):
        return Quantity(p.NUM, p.ID, line=p.lineno)

    @_("NUM")
    def fator(self, p):
        return Quantity(p.NUM, None, line=p.lineno)

    @_("ID")
    def fator(self, p):
        return Reference(p.ID, line=p.lineno)

    @_("'(' expr ')'")
    def fator(self, p):
        return p.expr

    @_("'-' fator")
    def fator(self, p):
        return Negation(p.fator, line=p.lineno)

    def error(self, token: Token | None) -> None:
        expected = describe_expected(self._acceptable_tokens())
        if token is None:
            found, line = "o fim do arquivo", self._last_line
        else:
            found, line = describe_token(token), token.lineno
        raise SyntacticError(f"encontrou {found} quando esperava {expected}", line)

    def _acceptable_tokens(self) -> list[str]:
        """Tokens que o parser aceitaria agora.

        Na tabela LALR os lookaheads de estados com o mesmo núcleo são fundidos, então as
        ações do estado atual podem incluir tokens que só valem em outro contexto. Para cada
        candidato, as reduções são simuladas sobre uma cópia da pilha até haver um shift.
        """
        candidates = [t for t in self._grammar.Terminals if t != "error"] + ["$end"]
        return [t for t in candidates if self._would_shift(t)]

    def _would_shift(self, token_type: str) -> bool:
        actions = self._lrtable.lr_action
        goto = self._lrtable.lr_goto
        stack = list(self.statestack)
        while True:
            action = actions[stack[-1]].get(token_type)
            if action is None:
                return False
            if action >= 0:
                return True
            production = self._grammar.Productions[-action]
            if production.len:
                del stack[-production.len:]
            stack.append(goto[stack[-1]][production.name])

    def parse_tokens(self, tokens: Sequence[Token]) -> Program:
        self._last_line = tokens[-1].lineno if tokens else 1
        return self.parse(iter(tokens))


def describe_token(token: Token) -> str:
    """Descrição do token para mensagens de erro: "identificador 'x'", "símbolo ';'"."""
    if token.type == "STRING":
        return f'texto "{token.value}"'
    if token.type == "NUM":
        return f"número '{format_number(token.value)}'"
    if token.type == "HORA":
        hours, minutes = token.value
        return f"hora '{hours:02d}:{minutes:02d}'"
    if token.type == "ID":
        return f"identificador '{token.value}'"
    if token.type.isupper():
        return f"palavra reservada '{token.value}'"
    return f"símbolo '{token.value}'"


_EXPECTED_ORDER = [
    "ID", "NUM", "STRING", "HORA", "(", "+", "-", "*", "/", ")", "=", ",", ";", "{", "}",
]
_EXPECTED_NAMES = {
    "ID": "identificador",
    "NUM": "número",
    "STRING": "texto entre aspas",
    "HORA": "hora (HH:MM)",
    "$end": "fim do arquivo",
}


def _expected_sort_key(token_type: str) -> tuple[int, bool, str]:
    position = _EXPECTED_ORDER.index(token_type) if token_type in _EXPECTED_ORDER else len(_EXPECTED_ORDER)
    return position, token_type == "$end", token_type


def describe_expected(token_types: Iterable[str]) -> str:
    """Lista legível dos tokens aceitos num estado do parser: "';', '+' ou '-'"."""
    types = [t for t in token_types if t != "error"]
    types.sort(key=_expected_sort_key)
    names = [_EXPECTED_NAMES.get(t) or f"'{t.lower()}'" for t in types]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " ou " + names[-1]


@dataclass
class ParseResult:
    program: Program | None
    errors: list[ReceitaError] = field(default_factory=list)


def parse(source: str) -> ParseResult:
    """Executa as análises léxica e sintática; para se houver erro léxico."""
    tokens, lexical_errors = tokenize(source)
    if lexical_errors:
        return ParseResult(None, list(lexical_errors))
    try:
        return ParseResult(RecipeParser().parse_tokens(tokens))
    except SyntacticError as error:
        return ParseResult(None, [error])

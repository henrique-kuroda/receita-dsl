"""Interface de linha de comando: python -m receita arquivo.rec [opções]."""

from __future__ import annotations

import argparse
import sys
from fractions import Fraction
from pathlib import Path
from typing import Sequence

from sly.lex import Token

from receita.lexer import tokenize

EXIT_OK = 0
EXIT_SYNTAX_ERROR = 1
EXIT_SEMANTIC_ERROR = 2


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m receita",
        description="Interpretador da linguagem Receita.",
    )
    parser.add_argument("arquivo", help="programa-fonte (.rec)")
    parser.add_argument("--tokens", action="store_true", help="lista os tokens reconhecidos")
    return parser


def format_tokens(tokens: Sequence[Token], source: str) -> str:
    """Tabela de tokens com linha, tipo, lexema e valor interpretado."""
    header = ("LINHA", "TIPO", "LEXEMA", "VALOR")
    rows = [
        (str(t.lineno), t.type, source[t.index:t.end], _format_value(t))
        for t in tokens
    ]
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(3)]
    lines = []
    for line, kind, lexeme, value in [header, *rows]:
        cells = [line.rjust(widths[0]), kind.ljust(widths[1]), lexeme.ljust(widths[2]), value]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def _format_value(token: Token) -> str:
    if token.type == "NUM":
        return str(Fraction(token.value))
    if token.type == "HORA":
        hours, minutes = token.value
        return f"{hours:02d}:{minutes:02d}"
    if token.type == "STRING":
        return token.value
    return ""


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        source = Path(args.arquivo).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"erro: não foi possível ler '{args.arquivo}': {exc}", file=sys.stderr)
        return EXIT_SYNTAX_ERROR

    tokens, errors = tokenize(source)
    if args.tokens:
        print(format_tokens(tokens, source))
    for error in errors:
        print(error, file=sys.stderr)
    return EXIT_SYNTAX_ERROR if errors else EXIT_OK


def _use_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


if __name__ == "__main__":
    _use_utf8_output()
    sys.exit(main())

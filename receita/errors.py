"""Erros de compilação reportados ao usuário."""

from __future__ import annotations

from typing import ClassVar


class ReceitaError(Exception):
    """Erro associado a uma linha do programa-fonte."""

    kind: ClassVar[str] = ""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return f"erro {self.kind} [linha {self.line}]: {self.message}"


class LexicalError(ReceitaError):
    kind = "léxico"


class SyntacticError(ReceitaError):
    kind = "sintático"


class SemanticError(ReceitaError):
    kind = "semântico"


class SemanticWarning(ReceitaError):
    """Problema que não impede a execução."""

    def __str__(self) -> str:
        return f"aviso [linha {self.line}]: {self.message}"

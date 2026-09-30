"""Análise semântica: escopos, tipos dimensionais e restrições de valor.

Roda sobre o programa inteiro antes de qualquer comando executar e coleta todos os erros.
Uma expressão com erro tem tipo desconhecido (None), que se propaga sem gerar novos erros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from receita.ast import (
    BinaryOp,
    Expr,
    Ingredient,
    Negation,
    NodeVisitor,
    Program,
    Quantity,
    Recipe,
    Reference,
    ScaleCommand,
    ScheduleCommand,
    ShoppingCommand,
    Step,
    UnitDef,
)
from receita.errors import SemanticError, SemanticWarning
from receita.evaluator import evaluate
from receita.symbols import Scope, Symbol, SymbolKind, SymbolTable
from receita.types import INGREDIENT_DIMENSIONS, Amount, DimensionError, binary_result
from receita.units import Dimension, Unit, UnitTable


@dataclass
class SemanticResult:
    symbols: SymbolTable
    units: UnitTable
    errors: list[SemanticError] = field(default_factory=list)
    warnings: list[SemanticWarning] = field(default_factory=list)


class SemanticAnalyzer(NodeVisitor):
    """Visitor que verifica declarações, referências e tipos, preenchendo a tabela de símbolos."""

    def __init__(self) -> None:
        self.units = UnitTable()
        self.symbols = SymbolTable(self.units)
        self.errors: list[SemanticError] = []
        self.warnings: list[SemanticWarning] = []
        self._global = self.symbols.global_scope
        self._scope: Scope = self._global
        self._recipe: Recipe | None = None
        self._unit_lines: dict[str, int] = {}
        self._recipe_lines: dict[str, int] = {}
        self._ingredient_owners: dict[str, list[str]] = {}
        self._ingredient_lines: dict[str, int] = {}
        self._used: set[str] = set()

    def analyze(self, program: Program) -> SemanticResult:
        self._collect_declarations(program)
        self.visit(program)
        self.errors.sort(key=lambda e: e.line)
        self.warnings.sort(key=lambda w: w.line)
        return SemanticResult(self.symbols, self.units, self.errors, self.warnings)

    def _collect_declarations(self, program: Program) -> None:
        """Pré-passagem que só registra onde cada nome aparece, para mensagens mais precisas."""
        for declaration in program.declarations:
            if isinstance(declaration, UnitDef):
                self._unit_lines.setdefault(declaration.name, declaration.line)
            elif isinstance(declaration, Recipe):
                self._recipe_lines.setdefault(declaration.name, declaration.line)
                for ingredient in declaration.ingredients:
                    owners = self._ingredient_owners.setdefault(ingredient.name, [])
                    if declaration.name not in owners:
                        owners.append(declaration.name)

    # Declarações

    def visit_Program(self, node: Program) -> None:
        for declaration in node.declarations:
            self.visit(declaration)

    def visit_UnitDef(self, node: UnitDef) -> None:
        dimension = self.visit(node.expr)
        symbol = Symbol(node.name, SymbolKind.UNIDADE, node.line)
        existing = self._global.declare(symbol)
        if existing is not None:
            self._report_global_redeclaration(symbol, existing)
            return
        if dimension is None:
            return
        if dimension is Dimension.ESCALAR:
            self._error(f"unidade '{node.name}' precisa ter dimensão não escalar", node.line)
            return
        amount = self._evaluate(node.expr)
        if amount is None:
            return
        if amount.value <= 0:
            self._error(f"unidade '{node.name}' precisa ter valor positivo", node.line)
            return
        symbol.dimension, symbol.value = dimension, amount.value
        self.units.register(Unit(node.name, dimension, amount.value))

    def visit_Recipe(self, node: Recipe) -> None:
        symbol = Symbol(node.name, SymbolKind.RECEITA, node.line, value=node.servings)
        existing = self._global.declare(symbol)
        if existing is not None:
            self._report_global_redeclaration(symbol, existing)
        if node.servings <= 0:
            self._error(f"receita '{node.name}' precisa render mais que zero porções", node.line)

        scope = self.symbols.new_scope(node.name)
        if existing is None:
            symbol.scope = scope
        self._scope, self._recipe = scope, node
        self._ingredient_lines = {}
        for ingredient in node.ingredients:
            self._ingredient_lines.setdefault(ingredient.name, ingredient.line)
        self._used = set()
        for item in node.items:
            self.visit(item)
        self._warn_unused_ingredients(node, scope)
        self._scope, self._recipe = self._global, None

    def visit_Ingredient(self, node: Ingredient) -> None:
        dimension = self.visit(node.expr)
        symbol = Symbol(node.name, SymbolKind.INGREDIENTE, node.line)
        existing = self._scope.declare(symbol)
        if existing is not None:
            self._error(
                f"ingrediente '{node.name}' já declarado na receita '{self._recipe.name}' "
                f"(linha {existing.line})",
                node.line,
            )
            return
        if dimension is None:
            return
        if dimension not in INGREDIENT_DIMENSIONS:
            self._error(
                f"ingrediente '{node.name}' precisa ser massa, volume ou contagem, "
                f"não {dimension.describe()}",
                node.line,
            )
            return
        amount = self._evaluate(node.expr)
        if amount is None:
            return
        if amount.value <= 0:
            self._error(f"ingrediente '{node.name}' precisa ter quantidade positiva", node.line)
        symbol.dimension, symbol.value = dimension, amount.value

    def visit_Step(self, node: Step) -> None:
        label = f'passo "{node.description}"'
        dimension = self.visit(node.duration)
        if dimension is not None and dimension is not Dimension.TEMPO:
            self._error(f"duração do {label} precisa ser tempo, não {dimension.describe()}", node.line)
        elif dimension is not None:
            amount = self._evaluate(node.duration)
            if amount is not None and amount.value <= 0:
                self._error(f"duração do {label} precisa ser positiva", node.line)
        for name in node.uses:
            if self._resolve_ingredient(name, node.line, context=f"{label}: ") is not None:
                self._used.add(name)

    # Comandos

    def visit_ScaleCommand(self, node: ScaleCommand) -> None:
        self._resolve_recipe(node.recipe, node.line)
        self._check_servings(node.servings, node.line)

    def visit_ShoppingCommand(self, node: ShoppingCommand) -> None:
        recipes: dict[str, Symbol] = {}
        for target in node.targets:
            symbol = self._resolve_recipe(target.recipe, target.line)
            if symbol is not None:
                recipes.setdefault(symbol.name, symbol)
            if target.servings is not None:
                self._check_servings(target.servings, target.line)
        self._check_shopping_dimensions(list(recipes.values()), node.line)

    def visit_ScheduleCommand(self, node: ScheduleCommand) -> None:
        for name in node.recipes:
            self._resolve_recipe(name, node.line)

    # Expressões: cada visita retorna a dimensão, ou None se houve erro

    def visit_Quantity(self, node: Quantity) -> Dimension | None:
        if node.unit is None:
            return Dimension.ESCALAR
        symbol = self._global.lookup_local(node.unit)
        if symbol is None:
            declared_at = self._unit_lines.get(node.unit)
            if declared_at is not None:
                self._error(
                    f"unidade '{node.unit}' usada antes da declaração (linha {declared_at})", node.line
                )
            else:
                self._error(f"unidade '{node.unit}' inexistente", node.line)
            return None
        if symbol.kind is not SymbolKind.UNIDADE:
            self._error(f"'{node.unit}' é uma receita, não uma unidade", node.line)
            return None
        return symbol.dimension

    def visit_Reference(self, node: Reference) -> Dimension | None:
        symbol = self._resolve_ingredient(node.name, node.line)
        return symbol.dimension if symbol is not None else None

    def visit_BinaryOp(self, node: BinaryOp) -> Dimension | None:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if left is None or right is None:
            return None
        try:
            result = binary_result(node.op, left, right)
        except DimensionError as error:
            self._error(str(error), node.line)
            return None
        if node.op == "/" and _is_literal_zero(node.right):
            self._error("divisão por zero", node.line)
            return None
        return result

    def visit_Negation(self, node: Negation) -> Dimension | None:
        return self.visit(node.operand)

    # Auxiliares

    def _resolve_ingredient(self, name: str, line: int, context: str = "") -> Symbol | None:
        symbol = self._scope.lookup(name)
        if symbol is not None and symbol.kind is SymbolKind.INGREDIENTE:
            return symbol
        if symbol is not None:
            self._error(f"{context}'{name}' é uma {symbol.kind.value}, não um ingrediente", line)
        elif self._recipe is None:
            self._error(f"{context}ingrediente '{name}' referenciado fora de uma receita", line)
        elif name in self._ingredient_lines:
            self._error(
                f"{context}ingrediente '{name}' usado antes da declaração "
                f"(linha {self._ingredient_lines[name]})",
                line,
            )
        else:
            message = f"{context}ingrediente '{name}' não declarado na receita '{self._recipe.name}'"
            owners = [r for r in self._ingredient_owners.get(name, []) if r != self._recipe.name]
            if owners:
                message += f" (pertence à receita '{owners[0]}')"
            self._error(message, line)
        return None

    def _resolve_recipe(self, name: str, line: int) -> Symbol | None:
        symbol = self._global.lookup_local(name)
        if symbol is None:
            declared_at = self._recipe_lines.get(name)
            if declared_at is not None:
                self._error(f"receita '{name}' usada antes da declaração (linha {declared_at})", line)
            else:
                self._error(f"receita '{name}' inexistente", line)
            return None
        if symbol.kind is not SymbolKind.RECEITA:
            self._error(f"'{name}' é uma unidade, não uma receita", line)
            return None
        return symbol

    def _check_servings(self, servings: Fraction, line: int) -> None:
        if servings <= 0:
            self._error("número de porções precisa ser maior que zero", line)

    def _check_shopping_dimensions(self, recipes: list[Symbol], line: int) -> None:
        """Ingredientes de mesmo nome só podem ser somados se tiverem a mesma dimensão."""
        seen: dict[str, tuple[Dimension, str]] = {}
        reported: set[str] = set()
        for recipe in recipes:
            for ingredient in recipe.scope or ():
                if ingredient.dimension is None:
                    continue
                previous = seen.setdefault(ingredient.name, (ingredient.dimension, recipe.name))
                if previous[0] is not ingredient.dimension and ingredient.name not in reported:
                    reported.add(ingredient.name)
                    self._error(
                        f"ingrediente '{ingredient.name}' tem dimensões diferentes nas receitas "
                        f"'{previous[1]}' ({previous[0].describe()}) e '{recipe.name}' "
                        f"({ingredient.dimension.describe()}); sem densidade não há conversão",
                        line,
                    )

    def _warn_unused_ingredients(self, recipe: Recipe, scope: Scope) -> None:
        if not any(step.uses for step in recipe.steps):
            return
        for symbol in scope:
            if symbol.name not in self._used:
                self.warnings.append(
                    SemanticWarning(
                        f"ingrediente '{symbol.name}' não é usado em nenhum passo "
                        f"da receita '{recipe.name}'",
                        symbol.line,
                    )
                )

    def _report_global_redeclaration(self, symbol: Symbol, existing: Symbol) -> None:
        if existing.line is None:
            message = f"'{symbol.name}' já existe como unidade nativa"
        elif existing.kind is symbol.kind:
            message = f"{symbol.kind.value} '{symbol.name}' já declarada na linha {existing.line}"
        else:
            message = (
                f"nome '{symbol.name}' já usado por uma {existing.kind.value} "
                f"na linha {existing.line}"
            )
        self._error(message, symbol.line)

    def _evaluate(self, expr: Expr) -> Amount | None:
        ingredients = {s.name: s.amount for s in self._scope if s.amount is not None}
        try:
            return evaluate(expr, self.units, ingredients if self._recipe else {})
        except ZeroDivisionError:
            self._error("divisão por zero", expr.line)
            return None

    def _error(self, message: str, line: int) -> None:
        self.errors.append(SemanticError(message, line))


def _is_literal_zero(expr: Expr) -> bool:
    if isinstance(expr, Negation):
        return _is_literal_zero(expr.operand)
    return isinstance(expr, Quantity) and expr.value == 0


def analyze(program: Program) -> SemanticResult:
    """Executa a análise semântica completa de `program`."""
    return SemanticAnalyzer().analyze(program)

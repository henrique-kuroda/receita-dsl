from fractions import Fraction

from receita.symbols import Scope, Symbol, SymbolKind, SymbolTable
from receita.types import Amount
from receita.units import Dimension


def ingredient(name: str, line: int = 1) -> Symbol:
    return Symbol(name, SymbolKind.INGREDIENTE, line, Dimension.MASSA, Fraction(10))


def test_escopo_global_contem_unidades_nativas():
    table = SymbolTable()
    kg = table.global_scope.lookup("kg")
    assert (kg.kind, kg.dimension, kg.value, kg.line) == (
        SymbolKind.UNIDADE, Dimension.MASSA, Fraction(1000), None,
    )


def test_declarar_nome_repetido_no_mesmo_escopo_retorna_o_anterior():
    scope = Scope("bolo")
    first = ingredient("farinha", 2)
    assert scope.declare(first) is None
    assert scope.declare(ingredient("farinha", 5)) is first
    assert scope.lookup_local("farinha").line == 2


def test_busca_sobe_pela_cadeia_de_escopos():
    table = SymbolTable()
    recipe = table.new_scope("bolo")
    recipe.declare(ingredient("farinha"))
    assert recipe.lookup("farinha").kind is SymbolKind.INGREDIENTE
    assert recipe.lookup("g").kind is SymbolKind.UNIDADE
    assert recipe.lookup_local("g") is None


def test_escopos_irmaos_sao_isolados():
    table = SymbolTable()
    bolo = table.new_scope("bolo")
    cobertura = table.new_scope("cobertura")
    bolo.declare(ingredient("manteiga"))
    assert cobertura.lookup("manteiga") is None
    assert table.global_scope.lookup("manteiga") is None
    assert table.global_scope.children == [bolo, cobertura]


def test_nome_local_oculta_o_global():
    table = SymbolTable()
    recipe = table.new_scope("bolo")
    recipe.declare(Symbol("g", SymbolKind.INGREDIENTE, 3, Dimension.CONTAGEM, Fraction(2)))
    assert recipe.lookup("g").kind is SymbolKind.INGREDIENTE
    assert table.global_scope.lookup("g").kind is SymbolKind.UNIDADE


def test_amount_do_simbolo():
    assert ingredient("sal").amount == Amount(Fraction(10), Dimension.MASSA)
    assert Symbol("x", SymbolKind.INGREDIENTE).amount is None


def test_format_lista_escopos():
    table = SymbolTable()
    table.global_scope.declare(Symbol("pitada", SymbolKind.UNIDADE, 1, Dimension.MASSA, Fraction(1, 2)))
    table.global_scope.declare(Symbol("bolo", SymbolKind.RECEITA, 2, None, Fraction(8)))
    scope = table.new_scope("bolo")
    scope.declare(Symbol("farinha", SymbolKind.INGREDIENTE, 3, Dimension.VOLUME, Fraction(480)))
    scope.declare(Symbol("ruim", SymbolKind.INGREDIENTE, 4))
    table.new_scope("vazia")
    text = table.format()
    lines = text.splitlines()
    assert lines[0] == "Escopo global"
    assert lines[1].split() == ["NOME", "CATEGORIA", "DIMENSÃO", "VALOR", "LINHA"]
    assert lines[2].split() == ["mg", "unidade", "massa", "0.001", "g", "nativa"]
    assert "  pitada  " in text
    assert text.endswith(
        "Escopo receita bolo (pai: global)\n"
        "  NOME     CATEGORIA    DIMENSÃO  VALOR   LINHA\n"
        "  farinha  ingrediente  volume    480 ml  3\n"
        "  ruim     ingrediente  ?         ?       4\n"
        "\n"
        "Escopo receita vazia (pai: global)\n"
        "  (vazio)"
    )
    assert [line.split() for line in lines if line.startswith("  bolo ")] == [
        ["bolo", "receita", "-", "8", "porções", "2"]
    ]

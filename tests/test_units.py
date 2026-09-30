from fractions import Fraction

import pytest

from receita.units import NATIVE_UNITS, Dimension, UnitError, UnitTable


@pytest.fixture
def table() -> UnitTable:
    return UnitTable()


@pytest.mark.parametrize(
    ("name", "dimension"),
    [
        ("mg", Dimension.MASSA),
        ("g", Dimension.MASSA),
        ("kg", Dimension.MASSA),
        ("ml", Dimension.VOLUME),
        ("l", Dimension.VOLUME),
        ("xicara", Dimension.VOLUME),
        ("colher_sopa", Dimension.VOLUME),
        ("colher_cha", Dimension.VOLUME),
        ("un", Dimension.CONTAGEM),
        ("duzia", Dimension.CONTAGEM),
        ("s", Dimension.TEMPO),
        ("min", Dimension.TEMPO),
        ("h", Dimension.TEMPO),
    ],
)
def test_unidade_nativa_tem_dimensao_correta(table, name, dimension):
    assert table.lookup(name).dimension is dimension


def test_tabela_contem_todas_as_nativas(table):
    assert len(table) == len(NATIVE_UNITS)
    assert all(unit.name in table for unit in NATIVE_UNITS)


@pytest.mark.parametrize(
    ("dimension", "base"),
    [
        (Dimension.MASSA, "g"),
        (Dimension.VOLUME, "ml"),
        (Dimension.CONTAGEM, "un"),
        (Dimension.TEMPO, "min"),
        (Dimension.ESCALAR, None),
    ],
)
def test_unidade_base_por_dimensao(dimension, base):
    assert dimension.base_unit == base


def test_unidade_base_tem_fator_um(table):
    for dimension in Dimension:
        if dimension.base_unit is not None:
            assert table.lookup(dimension.base_unit).factor == 1


@pytest.mark.parametrize(
    ("value", "source", "target", "expected"),
    [
        (Fraction(1, 2), "kg", "g", Fraction(500)),
        (Fraction(250), "g", "kg", Fraction(1, 4)),
        (Fraction(1500), "mg", "g", Fraction(3, 2)),
        (Fraction(2), "l", "ml", Fraction(2000)),
        (Fraction(1), "xicara", "colher_sopa", Fraction(16)),
        (Fraction(1), "colher_sopa", "colher_cha", Fraction(3)),
        (Fraction(2), "duzia", "un", Fraction(24)),
        (Fraction(90), "s", "min", Fraction(3, 2)),
        (Fraction(1), "h", "s", Fraction(3600)),
        (Fraction(7), "g", "g", Fraction(7)),
    ],
)
def test_conversao_na_mesma_dimensao(table, value, source, target, expected):
    assert table.convert(value, source, target) == expected


def test_conversao_para_base(table):
    assert table.to_base(Fraction(3, 4), "h") == 45
    assert table.to_base(Fraction(1, 2), "xicara") == 120


def test_conversao_e_exata_sem_erro_de_ponto_flutuante(table):
    total = sum((table.to_base(Fraction(1, 10), "kg") for _ in range(3)), Fraction(0))
    assert total == 300
    assert table.convert(total, "g", "kg") == Fraction(3, 10)


def test_ida_e_volta_preserva_valor(table):
    value = Fraction(7, 3)
    ida = table.convert(value, "colher_cha", "xicara")
    assert table.convert(ida, "xicara", "colher_cha") == value


@pytest.mark.parametrize(
    ("source", "target"),
    [("g", "ml"), ("xicara", "g"), ("un", "kg"), ("min", "l"), ("duzia", "h")],
)
def test_conversao_entre_dimensoes_diferentes_e_erro(table, source, target):
    with pytest.raises(UnitError, match="não é possível converter"):
        table.convert(Fraction(1), source, target)


def test_mensagem_de_conversao_cita_dimensoes(table):
    with pytest.raises(UnitError) as info:
        table.convert(Fraction(1), "g", "ml")
    assert str(info.value) == "não é possível converter massa (g) em volume (ml)"


def test_unidade_inexistente_e_erro(table):
    assert table.get("libra") is None
    with pytest.raises(UnitError, match="unidade 'libra' inexistente"):
        table.convert(Fraction(1), "libra", "g")

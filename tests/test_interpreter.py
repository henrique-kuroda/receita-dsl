from fractions import Fraction

import pytest

from receita.display import format_amount, format_clock, format_decimal, format_duration
from receita.interpreter import (
    ScaleResult,
    ScheduleResult,
    ShoppingResult,
    format_result,
    interpret,
)
from receita.parser import parse
from receita.semantic import analyze
from receita.types import Amount
from receita.units import Dimension

M, V, C, T = Dimension.MASSA, Dimension.VOLUME, Dimension.CONTAGEM, Dimension.TEMPO


def run(source: str) -> list:
    program = parse(source).program
    assert analyze(program).errors == []
    return interpret(program)


BOLO = """\
unidade pitada = 0.5 g;
receita bolo rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    ingrediente acucar  = 300 g;
    ingrediente ovos    = 3 un;
    ingrediente cenoura = 0.5 kg;
    ingrediente sal     = 4 pitada;
    passo "Bater" dura 5 min usa cenoura, ovos;
    passo "Misturar" dura 10 min usa farinha, acucar, sal;
    passo "Assar" dura 1 h - 20 min;
}
receita cobertura rende 4 porcoes {
    ingrediente acucar = 0.1 kg;
    ingrediente chocolate = 4 colher_sopa;
    ingrediente ovos = 1 un;
    passo "Levar ao fogo" dura 90 s;
}
"""


# Exibição


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("2.345", "2.35"),
        ("2.344", "2.34"),
        ("1.2", "1.2"),
        ("750", "750"),
        ("1/3", "0.33"),
        ("2/3", "0.67"),
        ("0.001", "0"),
    ],
)
def test_format_decimal_arredonda_para_duas_casas(value, text):
    assert format_decimal(Fraction(value)) == text


@pytest.mark.parametrize(
    ("value", "dimension", "text"),
    [
        ("999", M, "999 g"),
        ("1000", M, "1 kg"),
        ("1250", M, "1.25 kg"),
        ("0.5", M, "0.5 g"),
        ("4.8", V, "4.8 ml"),
        ("1200", V, "1.2 l"),
        ("8", C, "8 un"),
        ("7.5", C, "8 un (7.5)"),
        ("1/3", C, "1 un (0.33)"),
        ("40", T, "40 min"),
        ("60", T, "1 h"),
        ("100", T, "1 h 40 min"),
        ("1.5", T, "1.5 min"),
        ("0.25", Dimension.ESCALAR, "0.25"),
    ],
)
def test_format_amount_normaliza_unidade(value, dimension, text):
    assert format_amount(Amount(Fraction(value), dimension)) == text


def test_format_duration():
    assert format_duration(Fraction(150)) == "2 h 30 min"
    assert format_duration(Fraction(185, 2)) == "1 h 32.5 min"


@pytest.mark.parametrize(
    ("minutes", "start", "text"),
    [
        (Fraction(0), None, "T+0:00"),
        (Fraction(65), None, "T+1:05"),
        (Fraction(3, 2), None, "T+0:01:30"),
        (Fraction(65), (14, 0), "15:05"),
        (Fraction(0), (9, 5), "09:05"),
        (Fraction(120), (23, 30), "01:30 (+1d)"),
    ],
)
def test_format_clock(minutes, start, text):
    assert format_clock(minutes, start) == text


# escalar


def test_escalar_multiplica_ingredientes_pelo_fator():
    [result] = run(BOLO + "escalar bolo para 20 porcoes;")
    assert isinstance(result, ScaleResult)
    assert result.factor == Fraction(5, 2)
    assert dict(result.ingredients) == {
        "farinha": Amount(Fraction(1200), V),
        "acucar": Amount(Fraction(750), M),
        "ovos": Amount(Fraction(15, 2), C),
        "cenoura": Amount(Fraction(1250), M),
        "sal": Amount(Fraction(5), M),
    }


def test_escalar_para_menos_porcoes():
    [result] = run(BOLO + "escalar bolo para 2 porcoes;")
    assert dict(result.ingredients)["ovos"] == Amount(Fraction(3, 4), C)


def test_escalar_mantem_ordem_de_declaracao_e_formata():
    [result] = run(BOLO + "escalar bolo para 20 porcoes;")
    assert format_result(result) == (
        "Receita bolo para 20 porções (rende 8, fator 2.5)\n"
        "  farinha  1.2 l\n"
        "  acucar   750 g\n"
        "  ovos     8 un (7.5)\n"
        "  cenoura  1.25 kg\n"
        "  sal      5 g"
    )


def test_ingrediente_que_depende_de_outro_escala_junto():
    source = (
        "receita r rende 2 porcoes { ingrediente farinha = 1 xicara; "
        "ingrediente sal = farinha * 0.01; }\nescalar r para 4 porcoes;"
    )
    [result] = run(source)
    assert dict(result.ingredients)["sal"] == Amount(Fraction(24, 5), V)


# compras


def test_compras_soma_ingredientes_de_mesmo_nome_convertendo_unidades():
    [result] = run(BOLO + "compras bolo para 16 porcoes, cobertura;")
    assert isinstance(result, ShoppingResult)
    assert result.targets == (("bolo", Fraction(16)), ("cobertura", Fraction(4)))
    assert result.items == (
        ("acucar", Amount(Fraction(700), M)),
        ("cenoura", Amount(Fraction(1000), M)),
        ("chocolate", Amount(Fraction(60), V)),
        ("farinha", Amount(Fraction(960), V)),
        ("ovos", Amount(Fraction(7), C)),
        ("sal", Amount(Fraction(4), M)),
    )


def test_compras_sem_porcoes_usa_o_rendimento_base():
    [result] = run(BOLO + "compras cobertura;")
    assert dict(result.items)["acucar"] == Amount(Fraction(100), M)


def test_compras_arredonda_contagem_so_depois_de_somar():
    [result] = run(BOLO + "compras bolo para 4 porcoes, cobertura para 2 porcoes;")
    assert dict(result.items)["ovos"] == Amount(Fraction(2), C)
    assert "  ovos       2 un" in format_result(result).splitlines()


def test_compras_da_mesma_receita_duas_vezes():
    [result] = run(BOLO + "compras cobertura, cobertura para 2 porcoes;")
    assert dict(result.items)["ovos"] == Amount(Fraction(3, 2), C)


def test_compras_formata_em_ordem_alfabetica():
    [result] = run(BOLO + "compras bolo para 20 porcoes, cobertura para 20 porcoes;")
    assert format_result(result) == (
        "Lista de compras: bolo (20 porções), cobertura (20 porções)\n"
        "  acucar     1.25 kg\n"
        "  cenoura    1.25 kg\n"
        "  chocolate  300 ml\n"
        "  farinha    1.2 l\n"
        "  ovos       13 un (12.5)\n"
        "  sal        5 g"
    )


# cronograma


def test_cronograma_sequencial_relativo():
    [result] = run(BOLO + "cronograma bolo, cobertura;")
    assert isinstance(result, ScheduleResult)
    assert [(e.recipe, e.start, e.end) for e in result.entries] == [
        ("bolo", 0, 5),
        ("bolo", 5, 15),
        ("bolo", 15, 55),
        ("cobertura", 55, Fraction(113, 2)),
    ]
    assert result.total == Fraction(113, 2)
    assert format_result(result) == (
        "Cronograma: bolo, cobertura\n"
        "  T+0:00 - T+0:05     bolo       Bater\n"
        "  T+0:05 - T+0:15     bolo       Misturar\n"
        "  T+0:15 - T+0:55     bolo       Assar\n"
        "  T+0:55 - T+0:56:30  cobertura  Levar ao fogo\n"
        "  Tempo total: 56.5 min"
    )


def test_cronograma_com_horario_de_inicio():
    [result] = run(BOLO + "cronograma bolo inicio 14:00;")
    assert format_result(result) == (
        "Cronograma: bolo (início 14:00)\n"
        "  14:00 - 14:05  bolo  Bater\n"
        "  14:05 - 14:15  bolo  Misturar\n"
        "  14:15 - 14:55  bolo  Assar\n"
        "  Tempo total: 55 min"
    )


def test_tempos_nao_escalam():
    results = run(BOLO + "escalar bolo para 80 porcoes;\ncronograma bolo;")
    assert results[1].total == 55


def test_cronograma_de_receita_sem_passos():
    [result] = run("receita r rende 1 porcao { }\ncronograma r;")
    assert format_result(result) == "Cronograma: r\n  (nada)\n  Tempo total: 0 min"


def test_comandos_executam_na_ordem_do_programa():
    results = run(BOLO + "cronograma bolo;\nescalar bolo para 1 porcao;\ncompras bolo;")
    assert [type(r) for r in results] == [ScheduleResult, ScaleResult, ShoppingResult]


def test_programa_sem_comandos_nao_produz_resultados():
    assert run(BOLO) == []

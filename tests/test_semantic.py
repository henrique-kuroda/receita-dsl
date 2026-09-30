from fractions import Fraction

import pytest

from receita.parser import parse
from receita.semantic import SemanticResult, analyze
from receita.symbols import SymbolKind
from receita.units import Dimension


def run(source: str) -> SemanticResult:
    result = parse(source)
    assert result.errors == []
    return analyze(result.program)


def errors(source: str) -> list[str]:
    return [str(e) for e in run(source).errors]


def warnings(source: str) -> list[str]:
    return [str(w) for w in run(source).warnings]


def recipe(body: str, name: str = "bolo") -> str:
    return f"receita {name} rende 8 porcoes {{\n{body}\n}}\n"


VALID_PROGRAM = """\
unidade pitada = 0.5 g;
receita bolo rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    ingrediente sal = farinha * 0.01;
    ingrediente fermento = 4 pitada;
    ingrediente ovos = 1 duzia / 4;
    passo "Misturar" dura 10 min usa farinha, sal, fermento, ovos;
    passo "Assar" dura 1 h - 20 min;
}
receita cobertura rende 4 porcoes {
    ingrediente acucar = 200 g;
    ingrediente ovos = 2 un;
}
escalar bolo para 20 porcoes;
compras bolo para 16 porcoes, cobertura;
cronograma bolo, cobertura inicio 14:00;
"""


def test_programa_valido_nao_tem_erros_nem_avisos():
    result = run(VALID_PROGRAM)
    assert result.errors == []
    assert result.warnings == []


def test_simbolos_do_programa_valido():
    result = run(VALID_PROGRAM)
    global_scope = result.symbols.global_scope
    pitada = global_scope.lookup("pitada")
    assert (pitada.kind, pitada.dimension, pitada.value, pitada.line) == (
        SymbolKind.UNIDADE, Dimension.MASSA, Fraction(1, 2), 1,
    )
    bolo = global_scope.lookup("bolo")
    assert (bolo.kind, bolo.value) == (SymbolKind.RECEITA, Fraction(8))
    sal = bolo.scope.lookup_local("sal")
    assert (sal.dimension, sal.value) == (Dimension.VOLUME, Fraction(24, 5))
    assert bolo.scope.lookup_local("ovos").value == 3
    assert result.units.lookup("pitada").factor == Fraction(1, 2)


# 1. Redeclaração no mesmo escopo


def test_unidade_redeclarada():
    assert errors("unidade p = 1 g;\nunidade p = 2 g;") == [
        "erro semântico [linha 2]: unidade 'p' já declarada na linha 1"
    ]


def test_unidade_nativa_redeclarada():
    assert errors("unidade kg = 1000 g;") == ["erro semântico [linha 1]: 'kg' já existe como unidade nativa"]


def test_receita_redeclarada():
    assert errors(recipe("") + recipe("")) == [
        "erro semântico [linha 4]: receita 'bolo' já declarada na linha 1"
    ]


def test_receita_com_nome_de_unidade():
    assert errors("unidade p = 1 g;\n" + recipe("", name="p")) == [
        "erro semântico [linha 2]: nome 'p' já usado por uma unidade na linha 1"
    ]


def test_ingrediente_redeclarado():
    assert errors(recipe("ingrediente ovos = 3 un;\ningrediente ovos = 4 un;")) == [
        "erro semântico [linha 3]: ingrediente 'ovos' já declarado na receita 'bolo' (linha 2)"
    ]


def test_mesmo_ingrediente_em_receitas_diferentes_e_permitido():
    source = recipe("ingrediente ovos = 3 un;") + recipe("ingrediente ovos = 1 un;", name="outra")
    assert errors(source) == []


def test_ingrediente_pode_ter_nome_de_unidade():
    assert errors(recipe("ingrediente g = 2 un;\ningrediente farinha = 300 g;")) == []


# 2. Unidade inexistente


def test_unidade_inexistente():
    assert errors(recipe("ingrediente farinha = 2 xicaras;")) == [
        "erro semântico [linha 2]: unidade 'xicaras' inexistente"
    ]


def test_unidade_usada_antes_da_declaracao():
    assert errors(recipe("ingrediente sal = 2 pitada;") + "unidade pitada = 0.5 g;") == [
        "erro semântico [linha 2]: unidade 'pitada' usada antes da declaração (linha 4)"
    ]


def test_receita_usada_como_unidade():
    assert errors(recipe("") + "unidade x = 2 bolo;") == [
        "erro semântico [linha 4]: 'bolo' é uma receita, não uma unidade"
    ]


# 3. Ingrediente não declarado, usado antes da declaração ou de outra receita


def test_ingrediente_nao_declarado():
    assert errors(recipe("ingrediente sal = manteiga * 0.01;", name="cobertura")) == [
        "erro semântico [linha 2]: ingrediente 'manteiga' não declarado na receita 'cobertura'"
    ]


def test_ingrediente_usado_antes_da_declaracao():
    assert errors(recipe("ingrediente sal = farinha * 0.01;\ningrediente farinha = 1 xicara;")) == [
        "erro semântico [linha 2]: ingrediente 'farinha' usado antes da declaração (linha 3)"
    ]


def test_ingrediente_usado_na_propria_declaracao():
    assert errors(recipe("ingrediente x = x * 2;")) == [
        "erro semântico [linha 2]: ingrediente 'x' usado antes da declaração (linha 2)"
    ]


def test_ingrediente_de_outra_receita():
    source = recipe("ingrediente manteiga = 50 g;") + recipe(
        "ingrediente creme = manteiga * 2;", name="cobertura"
    )
    assert errors(source) == [
        "erro semântico [linha 5]: ingrediente 'manteiga' não declarado na receita 'cobertura' "
        "(pertence à receita 'bolo')"
    ]


def test_ingrediente_referenciado_fora_de_receita():
    assert errors("unidade p = farinha * 2;") == [
        "erro semântico [linha 1]: ingrediente 'farinha' referenciado fora de uma receita"
    ]


def test_unidade_usada_como_ingrediente():
    assert errors(recipe("ingrediente x = g * 2;")) == [
        "erro semântico [linha 2]: 'g' é uma unidade, não um ingrediente"
    ]


# 4. Incompatibilidade dimensional


@pytest.mark.parametrize(
    ("expr", "message"),
    [
        ("300 g + 200 ml", "não é possível somar massa (g) com volume (ml)"),
        ("1 kg - 3 un", "não é possível subtrair contagem (un) de massa (g)"),
        ("2 + 3 g", "não é possível somar escalar com massa (g)"),
        ("2 g * 3 g", "não é possível multiplicar massa (g) por massa (g) (produto entre quantidades não é suportado)"),
        ("1 l / 2 g", "não é possível dividir volume (ml) por massa (g)"),
        ("2 / 1 g", "não é possível dividir escalar por massa (g)"),
    ],
)
def test_incompatibilidade_dimensional(expr, message):
    assert errors(recipe(f"ingrediente x = {expr};")) == [f"erro semântico [linha 2]: {message}"]


def test_divisao_por_literal_zero():
    assert errors(recipe("ingrediente x = 1 kg / 0;")) == ["erro semântico [linha 2]: divisão por zero"]


def test_divisao_por_expressao_nula():
    assert errors(recipe("ingrediente x = 1 kg / (2 - 2);")) == ["erro semântico [linha 2]: divisão por zero"]


def test_ingrediente_precisa_ser_massa_volume_ou_contagem():
    assert errors(recipe("ingrediente espera = 5 min;\ningrediente fator = 2;")) == [
        "erro semântico [linha 2]: ingrediente 'espera' precisa ser massa, volume ou contagem, não tempo (min)",
        "erro semântico [linha 3]: ingrediente 'fator' precisa ser massa, volume ou contagem, não escalar",
    ]


def test_ingrediente_precisa_ter_quantidade_positiva():
    assert errors(recipe("ingrediente x = 1 g - 2 g;")) == [
        "erro semântico [linha 2]: ingrediente 'x' precisa ter quantidade positiva"
    ]


def test_duracao_precisa_ser_tempo():
    assert errors(recipe('passo "Assar" dura 200 g;')) == [
        'erro semântico [linha 2]: duração do passo "Assar" precisa ser tempo, não massa (g)'
    ]


def test_duracao_precisa_ser_positiva():
    assert errors(recipe('passo "Esperar" dura 10 min - 1 h;')) == [
        'erro semântico [linha 2]: duração do passo "Esperar" precisa ser positiva'
    ]


def test_unidade_precisa_ter_dimensao_nao_escalar():
    assert errors("unidade vezes = 3;") == [
        "erro semântico [linha 1]: unidade 'vezes' precisa ter dimensão não escalar"
    ]


@pytest.mark.parametrize("expr", ["0 g", "1 g - 2 g"])
def test_unidade_precisa_ter_valor_positivo(expr):
    assert errors(f"unidade nada = {expr};") == [
        "erro semântico [linha 1]: unidade 'nada' precisa ter valor positivo"
    ]


def test_unidade_derivada_de_derivada():
    result = run("unidade pitada = 0.5 g;\nunidade punhado = 10 pitada;")
    assert result.errors == []
    assert result.units.lookup("punhado").factor == 5


# 5. `usa` com ingrediente inexistente


def test_usa_ingrediente_inexistente():
    source = recipe('ingrediente farinha = 1 xicara;\npasso "Misturar" dura 5 min usa farinha, manteiga;')
    assert errors(source) == [
        "erro semântico [linha 3]: passo \"Misturar\": ingrediente 'manteiga' não declarado na receita 'bolo'"
    ]


def test_usa_ingrediente_declarado_depois():
    source = recipe('passo "Misturar" dura 5 min usa farinha;\ningrediente farinha = 1 xicara;')
    assert errors(source) == [
        "erro semântico [linha 2]: passo \"Misturar\": ingrediente 'farinha' usado antes da declaração (linha 3)"
    ]


# 6. Receita inexistente em comando


def test_escalar_receita_inexistente():
    assert errors("escalar torta para 2 porcoes;") == ["erro semântico [linha 1]: receita 'torta' inexistente"]


def test_compras_e_cronograma_com_receita_inexistente():
    assert errors(recipe("") + "compras bolo, torta;\ncronograma pudim;") == [
        "erro semântico [linha 4]: receita 'torta' inexistente",
        "erro semântico [linha 5]: receita 'pudim' inexistente",
    ]


def test_comando_antes_da_receita():
    assert errors("escalar bolo para 2 porcoes;\n" + recipe("")) == [
        "erro semântico [linha 1]: receita 'bolo' usada antes da declaração (linha 2)"
    ]


def test_comando_com_unidade_no_lugar_de_receita():
    assert errors("cronograma kg;") == ["erro semântico [linha 1]: 'kg' é uma unidade, não uma receita"]


# 7. Rendimento ou porções <= 0


def test_rendimento_zero():
    assert errors("receita bolo rende 0 porcoes { }") == [
        "erro semântico [linha 1]: receita 'bolo' precisa render mais que zero porções"
    ]


def test_porcoes_zero_em_comandos():
    assert errors(recipe("") + "escalar bolo para 0 porcoes;\ncompras bolo para 0 porcoes;") == [
        "erro semântico [linha 4]: número de porções precisa ser maior que zero",
        "erro semântico [linha 5]: número de porções precisa ser maior que zero",
    ]


# 8. Compras com dimensões diferentes para o mesmo ingrediente


def test_compras_com_dimensoes_diferentes():
    source = (
        recipe("ingrediente acucar = 300 g;")
        + recipe("ingrediente acucar = 1 xicara;", name="cobertura")
        + "compras bolo para 20 porcoes, cobertura;"
    )
    assert errors(source) == [
        "erro semântico [linha 7]: ingrediente 'acucar' tem dimensões diferentes nas receitas "
        "'bolo' (massa (g)) e 'cobertura' (volume (ml)); sem densidade não há conversão"
    ]


def test_compras_com_mesma_dimensao_em_unidades_diferentes_e_valido():
    source = (
        recipe("ingrediente acucar = 300 g;")
        + recipe("ingrediente acucar = 0.2 kg;", name="cobertura")
        + "compras bolo, cobertura;"
    )
    assert errors(source) == []


def test_dimensoes_diferentes_sem_compras_nao_e_erro():
    source = recipe("ingrediente acucar = 300 g;") + recipe("ingrediente acucar = 1 xicara;", name="cobertura")
    assert errors(source) == []


# Avisos


def test_aviso_ingrediente_nao_usado():
    source = recipe(
        "ingrediente farinha = 1 xicara;\ningrediente sal = 1 g;\n"
        'passo "Misturar" dura 5 min usa farinha;'
    )
    result = run(source)
    assert result.errors == []
    assert [str(w) for w in result.warnings] == [
        "aviso [linha 3]: ingrediente 'sal' não é usado em nenhum passo da receita 'bolo'"
    ]


def test_sem_aviso_quando_nenhum_passo_usa_usa():
    assert warnings(recipe('ingrediente sal = 1 g;\npasso "Assar" dura 40 min;')) == []


# Coleta de erros


def test_coleta_todos_os_erros_em_ordem_de_linha():
    source = "escalar torta para 2 porcoes;\nunidade p = 3;\n" + recipe("ingrediente a = 1 g + 1 ml;")
    assert [e.split(":")[0] for e in errors(source)] == [
        "erro semântico [linha 1]", "erro semântico [linha 2]", "erro semântico [linha 4]",
    ]


def test_erro_nao_se_propaga_para_quem_depende_dele():
    source = recipe(
        "ingrediente a = 1 g + 1 ml;\n"
        "ingrediente b = a * 2;\n"
        "ingrediente c = b + 1 un;\n"
        'passo "Misturar" dura 5 min usa a, b, c;'
    )
    assert errors(source) == ["erro semântico [linha 2]: não é possível somar massa (g) com volume (ml)"]


def test_unidade_com_erro_nao_gera_unidade_inexistente():
    source = "unidade p = 1 g + 1 ml;\n" + recipe("ingrediente sal = 2 p;")
    assert errors(source) == ["erro semântico [linha 1]: não é possível somar massa (g) com volume (ml)"]

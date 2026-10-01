from pathlib import Path

import pytest

from receita.__main__ import EXIT_OK, EXIT_SEMANTIC_ERROR, EXIT_SYNTAX_ERROR, main


@pytest.fixture
def write_program(tmp_path: Path):
    def write(source: str) -> str:
        path = tmp_path / "programa.rec"
        path.write_text(source, encoding="utf-8")
        return str(path)

    return write


def test_programa_valido_sai_com_zero(write_program, capsys):
    assert main([write_program("unidade pitada = 0.5 g;")]) == EXIT_OK
    assert capsys.readouterr().err == ""


def test_flag_tokens_lista_linha_tipo_lexema_e_valor(write_program, capsys):
    main([write_program('# comentário\npasso "Bater ovos" dura 0.5 h;'), "--tokens"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["LINHA", "TIPO", "LEXEMA", "VALOR"]
    assert lines[1].split() == ["2", "PASSO", "passo"]
    assert lines[2].split() == ["2", "STRING", '"Bater', 'ovos"', "Bater", "ovos"]
    assert lines[4].split() == ["2", "NUM", "0.5", "1/2"]
    assert lines[-1].split() == ["2", ";", ";"]


def test_erro_lexico_sai_com_um_e_vai_para_stderr(write_program, capsys):
    assert main([write_program("receita\n@")]) == EXIT_SYNTAX_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "erro léxico [linha 2]: caractere inesperado '@'"


def test_arquivo_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe.rec")]) == EXIT_SYNTAX_ERROR
    assert "não foi possível ler" in capsys.readouterr().err


def test_flag_ast_mostra_arvore(write_program, capsys):
    assert main([write_program("unidade p = 1 g;"), "--ast"]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "Programa",
        "└── Unidade p  [linha 1]",
        "    └── Quantidade 1 g",
    ]


def test_erro_sintatico_sai_com_um(write_program, capsys):
    assert main([write_program("unidade p = 1 g\nescalar"), "--ast"]) == EXIT_SYNTAX_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("erro sintático [linha 2]: encontrou palavra reservada 'escalar'")


def test_varios_erros_sintaticos_sao_todos_reportados(write_program, capsys):
    main([write_program("unidade p = ;\nunidade q = 1 g;\nescalar x para;\n")])
    assert len(capsys.readouterr().err.splitlines()) == 2


def test_tokens_sao_listados_mesmo_com_erro_sintatico(write_program, capsys):
    assert main([write_program("receita ;"), "--tokens"]) == EXIT_SYNTAX_ERROR
    assert "RECEITA" in capsys.readouterr().out


def test_flag_simbolos_mostra_escopos(write_program, capsys):
    source = 'unidade pitada = 0.5 g;\nreceita bolo rende 8 porcoes {\n    ingrediente sal = 2 pitada;\n}'
    assert main([write_program(source), "--simbolos"]) == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("Escopo global\n")
    assert "Escopo receita bolo (pai: global)" in out
    assert [line.split() for line in out.splitlines() if line.startswith("  sal ")] == [
        ["sal", "ingrediente", "massa", "1", "g", "3"]
    ]


def test_erro_semantico_sai_com_dois(write_program, capsys):
    assert main([write_program("unidade p = 1 g + 1 ml;\nescalar torta para 2 porcoes;")]) == EXIT_SEMANTIC_ERROR
    assert capsys.readouterr().err.splitlines() == [
        "erro semântico [linha 1]: não é possível somar massa (g) com volume (ml)",
        "erro semântico [linha 2]: receita 'torta' inexistente",
    ]


def test_simbolos_sao_mostrados_mesmo_com_erro_semantico(write_program, capsys):
    assert main([write_program("unidade p = 3;"), "--simbolos"]) == EXIT_SEMANTIC_ERROR
    assert "  p " in capsys.readouterr().out


def test_aviso_nao_bloqueia(write_program, capsys):
    source = """receita r rende 1 porcao {
    ingrediente a = 1 g;
    ingrediente b = 1 g;
    passo "Misturar" dura 1 min usa b;
}"""
    assert main([write_program(source)]) == EXIT_OK
    assert capsys.readouterr().err.strip() == (
        "aviso [linha 2]: ingrediente 'a' não é usado em nenhum passo da receita 'r'"
    )


EXECUTABLE = """\
receita bolo rende 8 porcoes {
    ingrediente ovos = 3 un;
    passo "Assar" dura 40 min usa ovos;
}
escalar bolo para 4 porcoes;
cronograma bolo inicio 9:00;
"""


def test_executa_comandos(write_program, capsys):
    assert main([write_program(EXECUTABLE)]) == EXIT_OK
    assert capsys.readouterr().out == (
        "Receita bolo para 4 porções (rende 8, fator 0.5)\n"
        "  ovos  2 un (1.5)\n"
        "\n"
        "Cronograma: bolo (início 09:00)\n"
        "  09:00 - 09:40  bolo  Assar\n"
        "  Tempo total: 40 min\n"
    )


@pytest.mark.parametrize("flag", ["--tokens", "--ast", "--simbolos"])
def test_flags_de_inspecao_nao_executam(write_program, capsys, flag):
    assert main([write_program(EXECUTABLE), flag]) == EXIT_OK
    assert "Receita bolo para" not in capsys.readouterr().out


def test_erro_semantico_impede_execucao(write_program, capsys):
    assert main([write_program(EXECUTABLE + "escalar torta para 2 porcoes;")]) == EXIT_SEMANTIC_ERROR
    assert capsys.readouterr().out == ""

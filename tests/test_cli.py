from pathlib import Path

import pytest

from receita.__main__ import EXIT_OK, EXIT_SYNTAX_ERROR, main


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
    assert main([write_program("escalar bolo para 2 porcoes;"), "--ast"]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "Programa",
        "└── Escalar bolo para 2 porções  [linha 1]",
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

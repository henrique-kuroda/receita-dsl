"""Compara a saída de cada programa em exemplos/ com exemplos/saidas/<nome>.txt.

Para regenerar as saídas depois de uma mudança intencional: python -m tests.test_exemplos
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from receita.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "exemplos").glob("*.rec"))
OUTPUTS = ROOT / "exemplos" / "saidas"


def transcript(example: Path) -> str:
    """O que o usuário vê no terminal: comando, saída, erros e código de saída."""
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        exit_code = main([str(example)])
    command = f"$ python -m receita exemplos/{example.name}\n"
    return command + out.getvalue() + err.getvalue() + f"(código de saída: {exit_code})\n"


def test_ha_exemplos():
    assert len(EXAMPLES) >= 6


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.stem)
def test_saida_do_exemplo(example):
    expected = (OUTPUTS / f"{example.stem}.txt").read_text(encoding="utf-8")
    assert transcript(example) == expected


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True)
    for example in EXAMPLES:
        (OUTPUTS / f"{example.stem}.txt").write_text(transcript(example), encoding="utf-8", newline="\n")
        print(f"gerado: exemplos/saidas/{example.stem}.txt")

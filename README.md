# Receita

DSL para receitas escaláveis em que o sistema de unidades de medida é o sistema de tipos:
massa, volume, contagem e tempo são dimensões distintas, e misturá-las é erro detectado
antes da execução.

Trabalho final de Teoria da Computação e Compiladores.

## Ambiente

Requer Python 3.10+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

## Testes

```bash
python -m pytest
```

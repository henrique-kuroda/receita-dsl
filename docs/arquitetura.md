# Arquitetura

## Pipeline

```
            texto (.rec)
                 │
          ┌──────▼──────┐   tokens com linha               erro léxico ──► código 1
          │   lexer.py  │──────────────────┐
          └─────────────┘                  │
                                    ┌──────▼──────┐        erro sintático ──► código 1
                                    │  parser.py  │
                                    └──────┬──────┘
                                           │ AST (ast.py)
                                    ┌──────▼──────┐        erro semântico ──► código 2
                                    │ semantic.py │──► tabela de símbolos (--simbolos)
                                    └──────┬──────┘
                                           │ mesma AST, já validada
                                   ┌───────▼────────┐
                                   │ interpreter.py │──► resultados ──► display.py ──► saída
                                   └────────────────┘
```

Cada fase coleta todos os erros que encontra e a seguinte só roda se não houver nenhum. As
fases se comunicam por estruturas de dados imutáveis: a lista de tokens, a AST (dataclasses
congeladas) e os resultados dos comandos. Nenhuma fase altera a AST.

## Módulos

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `units.py` | dimensões, tabela de unidades nativas e declaradas, conversões | — |
| `types.py` | regras de `+ - * /` entre dimensões; `Amount`, o valor tipado na unidade base | units |
| `errors.py` | `LexicalError`, `SyntacticError`, `SemanticError`, `SemanticWarning`, todos com linha | — |
| `lexer.py` | tokens, palavras reservadas, contagem de linhas, erros léxicos | errors |
| `ast.py` | nós da AST, `NodeVisitor`, impressão em árvore (`--ast`) | — |
| `parser.py` | gramática LALR, construção da AST, tokens esperados e recuperação de erros | lexer, ast, errors |
| `evaluator.py` | avaliação de expressões para `Amount` | ast, types, units |
| `symbols.py` | escopos encadeados e listagem `--simbolos` | ast, types, units |
| `semantic.py` | visitor de verificação: escopos, tipos, restrições de valor, avisos | ast, evaluator, symbols, types |
| `interpreter.py` | visitor de execução e formatação dos resultados | ast, evaluator, display |
| `display.py` | exibição normalizada (kg/l, h/min, arredondamento) | types, units |
| `__main__.py` | CLI: encadeia as fases, flags de inspeção e códigos de saída | todos |

As dependências formam um grafo acíclico. `units.py` e `types.py`, que definem o sistema de
tipos, não conhecem a AST, e a AST não conhece nenhuma fase.

## Decisões de projeto

### Um visitor por fase

`NodeVisitor` (`ast.py`) despacha `visit(node)` para `visit_<Classe>`. A análise semântica
(`SemanticAnalyzer`) e a execução (`Interpreter`) são visitors independentes sobre a mesma AST.
O analisador retorna a **dimensão** de cada expressão, que é a tipagem estática; o interpretador
e o `ExpressionEvaluator` retornam **valores** (`Amount`). As mesmas regras de `types.py` valem
nas duas fases: `binary_result` decide a dimensão do resultado, e `Amount.apply` a reutiliza
ao calcular.

### Aritmética exata

Números viram `fractions.Fraction` já no lexer, e todo valor é guardado na unidade base da sua
dimensão. Conversões entre unidades viram multiplicações exatas (`1 s` = `1/60 min`), e somas
como `0.1 kg + 0.2 kg` não acumulam erro de ponto flutuante. O arredondamento acontece num
único lugar: `display.py`, no momento de exibir.

### Erros sem cascata

- **Léxico:** registra e pula o caractere inválido.
- **Sintático:** produções `error ';'` resincronizam no próximo `;`. A lista de tokens esperados
  vem de uma simulação das reduções sobre a pilha LALR.
- **Semântico:** uma expressão com erro recebe tipo desconhecido (`None`), que se propaga em
  silêncio para quem depende dela.

Assim cada problema real aparece uma única vez. Detalhes em [gramatica.md](gramatica.md) e
[semantica.md](semantica.md).

### Unidades são dados, não código

As unidades nativas são uma tupla de `Unit(nome, dimensão, fator)`, e as declaradas pelo
usuário entram na mesma tabela. Acrescentar uma unidade nativa (onça, colher de sobremesa) é
acrescentar uma linha em `NATIVE_UNITS`. Uma dimensão nova exige um item em `Dimension`, a
unidade base e a regra de exibição em `display.py`.

## Ponto de extensão: sub-receitas

O brief deixa sub-receitas (`inclui outra_receita`) para depois. A arquitetura comporta a
extensão sem mudar a estrutura das fases:

1. **Sintaxe:** uma nova alternativa em `item_receita`,
   `"inclui" ID [ "para" NUM "porcoes" ] ";"`, e um nó `Include(recipe, servings)` em
   `ast.py`.
2. **Semântica:** `visit_Include` resolve a receita no escopo global com `_resolve_recipe`
   (que já existe), exigindo declaração anterior. Isso também impede ciclos, porque uma
   receita não pode incluir a si mesma nem uma receita posterior. Os ingredientes incluídos
   passam pela mesma verificação de dimensões que hoje vale para `compras`
   (`_check_shopping_dimensions`).
3. **Execução:** `RecipeValue` ganha a lista de inclusões. `scaled_ingredients` soma os
   ingredientes da sub-receita escalados pelo fator dela, com a mesma soma por nome que
   `visit_ShoppingCommand` já faz, e o cronograma insere os passos da sub-receita antes dos
   da receita que a inclui.

Nenhuma das três mudanças altera lexer, tipos, tabela de símbolos ou exibição.

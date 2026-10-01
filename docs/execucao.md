# Semântica de execução

O interpretador (`receita/interpreter.py`) é um visitor sobre a mesma AST das fases
anteriores. Ele só roda quando a análise semântica não encontrou erros, e por isso não
verifica nada: toda referência existe e toda expressão é bem tipada.

## Pipeline

```
texto ─► lexer ─► tokens ─► parser ─► AST ─► análise semântica ─► interpretador ─► saída
```

Cada fase só começa se a anterior terminou sem erros. A CLI sai com código 1 em erro léxico
ou sintático e 2 em erro semântico. Com `--tokens`, `--ast` ou `--simbolos`, o programa é
analisado e a listagem pedida é impressa, mas os comandos não são executados: as flags servem
para inspeção.

## Avaliação

As declarações são percorridas em ordem:

- `unidade` é avaliada e registrada na tabela de unidades;
- cada `receita` vira um `RecipeValue`, com os ingredientes avaliados em ordem (um
  ingrediente pode usar os anteriores) e a duração de cada passo;
- cada comando produz um resultado (`ScaleResult`, `ShoppingResult` ou `ScheduleResult`),
  que depois é formatado como texto.

Todos os valores são `Amount`: uma `Fraction` exata na unidade base (g, ml, un, min) mais a
dimensão. O arredondamento acontece só na exibição.

## Comandos

### `escalar receita para N porcoes`

O fator é `N / rendimento`, e cada ingrediente é multiplicado por ele. Os ingredientes saem na
ordem de declaração. Tempos de preparo não escalam.

```
Receita bolo_cenoura para 20 porções (rende 8, fator 2.5)
  farinha  1.2 l
  acucar   750 g
  ovos     8 un (7.5)
  cenoura  1.25 kg
  oleo     500 ml
  sal      12 ml
```

### `compras alvo, alvo, ...`

Cada alvo é escalado para as porções pedidas; sem `para N porcoes`, vale o rendimento da
receita. Ingredientes de mesmo nome são somados, o que funciona porque estão na unidade base
(`300 g` + `0.1 kg` = `400 g`). A análise semântica já garantiu que nomes iguais têm a mesma
dimensão. A lista sai em ordem alfabética.

```
Lista de compras: bolo_cenoura (20 porções), cobertura (20 porções)
  acucar     1.35 kg
  cenoura    1.25 kg
  chocolate  150 ml
  farinha    1.2 l
  oleo       500 ml
  ovos       8 un (7.5)
  sal        12 ml
```

### `cronograma receita, ... [inicio HH:MM]`

Os passos são executados em sequência, receita após receita, na ordem informada. Cada passo
mostra início e fim: relativos (`T+0:05`) ou absolutos, se houver `inicio`. Ao final aparece o
tempo total.

```
Cronograma: bolo_cenoura, cobertura (início 14:00)
  14:00 - 14:05  bolo_cenoura  Bater cenoura, ovos e óleo no liquidificador
  14:05 - 14:15  bolo_cenoura  Misturar com farinha e açúcar
  14:15 - 14:55  bolo_cenoura  Assar a 180 graus
  14:55 - 15:03  cobertura     Levar ao fogo mexendo
  Tempo total: 1 h 3 min
```

## Exibição normalizada

As regras de exibição ficam em `receita/display.py`:

| Dimensão | Regra | Exemplos |
|---|---|---|
| massa | g; a partir de 1000 g, kg | `750 g`, `1.25 kg` |
| volume | ml; a partir de 1000 ml, l | `12 ml`, `1.2 l` |
| contagem | inteiro; fração arredondada para cima com o valor exato ao lado | `3 un`, `8 un (7.5)` |
| tempo | min; a partir de 60 min, h e min | `40 min`, `1 h`, `1 h 3 min` |

- Números têm no máximo duas casas decimais, com arredondamento "meio para cima"
  (`2.345` → `2.35`), e sem zeros à direita (`1.20` → `1.2`).
- Na lista de compras, a contagem é arredondada **depois** da soma: 1.5 ovo de uma receita mais
  0.5 de outra são `2 un`, não `3`.
- No cronograma, segundos só aparecem quando o instante não cai num minuto inteiro
  (`T+0:56:30`). Se o preparo passa da meia-noite, o horário indica o dia seguinte
  (`01:30 (+1d)`).

## Decisões

- **Unidade de exibição.** A quantidade é mostrada na unidade legível da sua dimensão, e não
  na unidade em que foi declarada. `2 xicara` escalado por 2.5 aparece como `1.2 l`. Converter
  de volta para xícaras exigiria escolher entre várias unidades da mesma dimensão, e o brief
  pede a normalização para g/kg, ml/l e h/min.
- **Unidades menores que a base** (mg, s) não são usadas na exibição: `0.5 g` e `1.5 min`
  continuam legíveis com duas casas.
- **Cronograma estritamente sequencial**, como pede o brief: não há paralelismo entre receitas
  (por exemplo, fazer a cobertura enquanto o bolo assa).
- **Receita citada duas vezes** em `compras` ou `cronograma` é contada duas vezes.

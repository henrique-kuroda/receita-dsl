# Gramática da linguagem Receita

## Léxico

O lexer (`receita/lexer.py`) é gerado com SLY. Espaços, tabulações e `\r` são ignorados;
quebras de linha são contadas para as mensagens de erro; comentários vão de `#` até o fim
da linha.

| Token | Expressão regular | Valor | Exemplos |
|---|---|---|---|
| `HORA` | `\d{1,2}:\d{2}` | `(horas, minutos)` | `14:00`, `9:30` |
| `NUM` | `\d+(\.\d+)?` | `Fraction` exata | `3`, `0.5` |
| `STRING` | `"[^"\n]*"` | texto sem as aspas | `"Assar a 180 graus"` |
| `ID` | `[^\W\d]\w*` (só ASCII é aceito) | o próprio nome | `farinha`, `colher_sopa` |
| literais | `= ; { } , + - * / ( )` | o próprio caractere | |

Palavras reservadas são reconhecidas como `ID` e remapeadas pelo SLY para o próprio tipo:

```
unidade  receita  rende  porcoes  porcao  ingrediente  passo  dura
usa  escalar  para  compras  cronograma  inicio
```

`HORA` vem antes de `NUM` na definição, porque o SLY testa os padrões na ordem em que foram
declarados. Assim, `14:00` é uma hora, e não `14` seguido de `:`.

### Decisões

- **`porcao` como sinônimo de `porcoes`**: as duas grafias geram o token `PORCOES`, para que
  `rende 1 porcao` seja válido. A gramática sintática só enxerga `PORCOES`.
- **Números sem ponto flutuante**: o lexema vira `fractions.Fraction`, então `0.1` é
  exatamente `1/10`. Não há vírgula decimal (`1,5` são dois números separados por vírgula) nem
  decimal sem parte inteira (`.5` é erro).
- **Identificadores ASCII**: a expressão regular aceita letras Unicode para que `açúcar` seja
  lido como uma palavra só e gere um erro claro ("identificador 'açúcar' tem caracteres não
  permitidos"), em vez de vários erros de caractere avulso. Acentos são permitidos apenas
  dentro de `STRING`.
- **Strings de uma linha, sem escapes**: não existe `\"`. Uma string sem aspas de fechamento
  gera o erro "string não terminada" e o lexer descarta o resto da linha.
- **Hora validada no léxico**: `24:00` ou `12:60` geram "hora inválida".

### Erros léxicos

O lexer não para no primeiro erro: registra cada um com a linha e continua a partir do
próximo caractere. A CLI imprime todos e sai com código 1.

```
erro léxico [linha 1]: caractere inesperado '@'
erro léxico [linha 2]: identificador 'açúcar' tem caracteres não permitidos (use letras sem acento, dígitos e _)
erro léxico [linha 3]: string não terminada
erro léxico [linha 4]: hora inválida '25:61'
```

A listagem de tokens para inspeção sai com `python -m receita arquivo.rec --tokens`.

## Sintaxe

### EBNF

```ebnf
programa      = { declaracao } ;
declaracao    = def_unidade | def_receita | comando ;

def_unidade   = "unidade" ID "=" expr ";" ;
def_receita   = "receita" ID "rende" NUM "porcoes" "{" { item_receita } "}" ;
item_receita  = ingrediente | passo ;
ingrediente   = "ingrediente" ID "=" expr ";" ;
passo         = "passo" STRING "dura" expr [ "usa" lista_ids ] ";" ;

comando       = "escalar" ID "para" NUM "porcoes" ";"
              | "compras" alvo { "," alvo } ";"
              | "cronograma" lista_ids [ "inicio" HORA ] ";" ;
alvo          = ID [ "para" NUM "porcoes" ] ;
lista_ids     = ID { "," ID } ;

expr          = termo { ( "+" | "-" ) termo } ;
termo         = fator { ( "*" | "/" ) fator } ;
fator         = NUM [ ID ]            (* literal de quantidade: 300 g *)
              | ID                    (* referência a ingrediente *)
              | "(" expr ")"
              | "-" fator ;
```

`"porcoes"` representa o token `PORCOES`, que também aceita a grafia `porcao` (ver
[Léxico](#decisões)). Em `cronograma`, `ID { "," ID }` foi escrito como `lista_ids`, que é a
mesma construção usada em `usa`.

### Da EBNF para as produções do SLY

O SLY recebe produções BNF, então cada construção da EBNF foi reescrita assim
(`receita/parser.py`):

| EBNF | BNF no SLY |
|---|---|
| `{ x }` | recursão à esquerda com produção vazia: `xs : xs x \| ε` |
| `x { "," x }` | recursão à esquerda: `xs : xs "," x \| x` |
| `[ x ]` | duas produções, com e sem `x` |
| `expr = termo { ("+" \| "-") termo }` | `expr : expr "+" termo \| expr "-" termo \| termo` |

A recursão à esquerda é a forma preferida em parsers LR: a pilha não cresce com o tamanho da
lista. Nas expressões, ela também deixa os operadores associativos à esquerda:
`1 h - 20 min - 5 min` é `(1 h - 20 min) - 5 min`.

### Conflitos

A gramática gera **83 estados LALR e nenhum conflito** shift/reduce ou reduce/reduce. Três
pontos poderiam gerar conflitos e foram tratados na própria gramática, sem declarar
`precedence` no SLY:

1. **Precedência e associatividade de `+ - * /`.** A estratificação em `expr` / `termo` /
   `fator` codifica a precedência (multiplicação e divisão ligam mais forte) e a recursão à
   esquerda codifica a associatividade. Uma gramática ambígua do tipo
   `expr : expr OP expr` exigiria uma tabela de precedência para resolver os conflitos.
2. **Literal de quantidade `NUM [ ID ]`.** Depois de um `NUM` com `ID` como lookahead, o parser
   poderia empilhar o `ID` (unidade) ou reduzir `fator → NUM` (número sem unidade). Isso não
   gera conflito porque nenhuma produção admite um `ID` logo após uma expressão: expressões são
   seguidas apenas por `+ - * / ) ;` e pela palavra reservada `usa`. Como `ID ∉ FOLLOW(fator)`,
   a única ação possível é o shift. Essa propriedade depende de `usa`, `para` e as demais
   palavras-chave serem reservadas, e não identificadores comuns.
3. **Menos unário e binário.** O `-` unário só aparece no início de `fator`, e o binário só
   depois de uma `expr` completa. Os dois nunca disputam o mesmo estado. O unário liga mais
   forte que qualquer binário: `-2 g * 3` é `(-2 g) * 3`.

Para conferir, basta gerar o relatório do SLY adicionando `debugfile = "parser.out"` à classe
`RecipeParser`.

### Erros sintáticos

O formato é o mesmo dos erros léxicos, com o token encontrado e os tokens esperados:

```
erro sintático [linha 3]: encontrou palavra reservada 'ingrediente' quando esperava '+', '-', '*', '/' ou ';'
erro sintático [linha 1]: encontrou número '14' quando esperava hora (HH:MM)
erro sintático [linha 2]: encontrou o fim do arquivo quando esperava '}', 'ingrediente' ou 'passo'
```

- **Tokens esperados.** Na tabela LALR, estados com o mesmo núcleo LR(0) têm os lookaheads
  fundidos, então as ações do estado atual podem incluir tokens que só são válidos em outro
  contexto (por exemplo `')'` e `'usa'` ao fim de `unidade p = 2 g`). Para cada terminal, o
  parser simula as reduções sobre uma cópia da pilha de estados e só lista os que chegariam a
  um shift. Limitação: como o LALR pode fazer reduções padrão antes de detectar o erro, a lista
  às vezes omite alternativas (em `(0.5 g * 2;` são listados `'+'`, `'-'` e `')'`, mas não
  `'*'`). Os tokens listados são sempre válidos.
- **Fim de arquivo.** O erro é atribuído à linha do último token, que é onde falta o
  complemento.
- **Recuperação.** As produções `declaracao : error ";"` e `item_receita : error ";"` fazem o
  parser descartar tokens até o próximo `;` e continuar, no nível do programa ou dentro da
  receita. Assim um único passe reporta erros em declarações diferentes. Como no yacc,
  novos erros só são reportados depois de três tokens aceitos, o que evita cascatas. Por isso
  um erro no cabeçalho de uma receita esconde erros até o fim dela.
- **Erro léxico interrompe.** Se o lexer encontrou erros, o parser não roda: os tokens
  descartados produziriam erros sintáticos em cascata sem relação com o problema real.

A árvore gerada pode ser inspecionada com `python -m receita arquivo.rec --ast`:

```
Programa
├── Unidade pitada  [linha 1]
│   └── Quantidade 0.5 g
├── Receita bolo rende 8 porções  [linha 2]
│   ├── Ingrediente farinha  [linha 3]
│   │   └── Quantidade 2 xicara
│   └── Passo "Assar" usa farinha  [linha 4]
│       └── Operação -
│           ├── Quantidade 1 h
│           └── Quantidade 20 min
└── Cronograma bolo início 14:00  [linha 6]
```

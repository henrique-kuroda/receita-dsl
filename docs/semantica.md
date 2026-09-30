# Sistema de tipos e análise semântica

A ideia central da linguagem é que **o sistema de unidades de medida é o sistema de tipos**.
Cada expressão tem uma *dimensão*, e combinar dimensões incompatíveis é um erro detectado antes
de qualquer comando executar. A abordagem segue a de Kennedy (*Dimension types*, 1994),
restrita a dimensões atômicas, sem produtos nem potências.

## Dimensões

| Dimensão | Unidade base | Unidades nativas |
|---|---|---|
| massa | g | mg, g, kg |
| volume | ml | ml, l, xicara (240 ml), colher_sopa (15 ml), colher_cha (5 ml) |
| contagem | un | un, duzia (12 un) |
| tempo | min | s, min, h |
| escalar | — | número sem unidade |

Internamente todo valor é um `Amount` (`receita/types.py`): magnitude na unidade base, como
`Fraction`, mais a dimensão. `2 xicara` é `Amount(480, volume)`. A conversão entre unidades da
mesma dimensão é implícita, porque toda aritmética acontece na unidade base.

## Regras de tipagem

Sejam `D` e `E` dimensões não escalares distintas e `S` a dimensão escalar:

| Expressão | Tipo | Exemplo |
|---|---|---|
| `NUM` | S | `0.01` |
| `NUM u` | dimensão de `u` | `300 g` : massa |
| `ingrediente` | dimensão declarada | `farinha` : volume |
| `-x` | tipo de `x` | |
| `D ± D`, `S ± S` | D, S | `1 h - 20 min` : tempo |
| `S * X`, `X * S` | X | `farinha * 0.01` : volume |
| `X / S` | X | `2 xicara / 4` : volume |
| `D / D` | S | `1 kg / 250 g` : escalar (= 4) |
| `D ± E`, `D ± S` | erro | `300 g + 200 ml` |
| `D * D`, `D * E` | erro | produto de dimensões não é suportado |
| `D / E`, `S / D` | erro | `S / D` exigiria a dimensão inversa |

As regras estão em `binary_result` (`receita/types.py`). Além delas:

- `ingrediente` precisa ser massa, volume ou contagem;
- a duração de `passo ... dura` precisa ser tempo;
- `unidade X = expr` cria `X` com a dimensão de `expr`, que não pode ser escalar.

## Escopos

A tabela de símbolos (`receita/symbols.py`) é uma cadeia de escopos:

- **global**: unidades nativas, unidades declaradas e receitas, num único espaço de nomes
  (uma receita não pode ter o nome de uma unidade);
- **receita**: um escopo por receita, filho do global, com os ingredientes daquela receita.

Referências a ingredientes são resolvidas a partir do escopo da receita, subindo pela cadeia.
Encontrar uma unidade ou uma receita no lugar de um ingrediente é erro. Unidades são sempre
buscadas no escopo global, porque a posição sintática já diz o que é unidade (`NUM ID`) e o
que é ingrediente (`ID`). Por isso um ingrediente pode se chamar `g` sem atrapalhar
`300 g` na mesma receita.

`python -m receita arquivo.rec --simbolos` mostra a tabela depois da análise. Os valores
aparecem na unidade base:

```
Escopo global
  NOME         CATEGORIA  DIMENSÃO  VALOR      LINHA
  mg           unidade    massa     0.001 g    nativa
  ...
  pitada       unidade    massa     0.5 g      1
  bolo         receita    -         8 porções  2

Escopo receita bolo (pai: global)
  NOME     CATEGORIA    DIMENSÃO  VALOR   LINHA
  farinha  ingrediente  volume    480 ml  3
  sal      ingrediente  massa     1 g     4
```

## Erros detectados

A análise (`receita/semantic.py`) é um visitor que percorre o programa inteiro. Todos os
erros são coletados e, se houver algum, nenhum comando executa (código de saída 2).

| # | Erro | Mensagem |
|---|---|---|
| 1 | redeclaração no mesmo escopo | `unidade 'p' já declarada na linha 1`<br>`'kg' já existe como unidade nativa`<br>`nome 'p' já usado por uma unidade na linha 1`<br>`ingrediente 'ovos' já declarado na receita 'bolo' (linha 2)` |
| 2 | unidade inexistente | `unidade 'xicaras' inexistente`<br>`unidade 'pitada' usada antes da declaração (linha 4)` |
| 3 | ingrediente não declarado, antes da declaração ou de outra receita | `ingrediente 'manteiga' não declarado na receita 'cobertura' (pertence à receita 'bolo')`<br>`ingrediente 'farinha' usado antes da declaração (linha 3)`<br>`'g' é uma unidade, não um ingrediente` |
| 4 | incompatibilidade dimensional | `não é possível somar massa (g) com volume (ml)`<br>`ingrediente 'espera' precisa ser massa, volume ou contagem, não tempo (min)`<br>`duração do passo "Assar" precisa ser tempo, não massa (g)`<br>`unidade 'vezes' precisa ter dimensão não escalar`<br>`divisão por zero` |
| 5 | `usa` com ingrediente inexistente | `passo "Misturar": ingrediente 'manteiga' não declarado na receita 'bolo'` |
| 6 | receita inexistente em comando | `receita 'torta' inexistente`<br>`receita 'bolo' usada antes da declaração (linha 2)` |
| 7 | rendimento ou porções ≤ 0 | `receita 'bolo' precisa render mais que zero porções`<br>`número de porções precisa ser maior que zero` |
| 8 | `compras` com dimensões diferentes | `ingrediente 'acucar' tem dimensões diferentes nas receitas 'bolo' (massa (g)) e 'cobertura' (volume (ml)); sem densidade não há conversão` |

O erro 8 só existe em `compras`, onde ingredientes de mesmo nome são somados. Duas receitas
podem ter `acucar` em dimensões diferentes, desde que não entrem na mesma lista de compras.

### Aviso

```
aviso [linha 4]: ingrediente 'sal' não é usado em nenhum passo da receita 'bolo'
```

Só é emitido quando a receita usa `usa` em pelo menos um passo: sem nenhum `usa`, a receita
não está declarando quais ingredientes cada passo consome. O aviso não bloqueia a execução.

## Decisões de projeto

- **Tipo desconhecido para evitar cascata.** Uma expressão com erro recebe tipo `None`, e
  quem depende dela (outras expressões, ingredientes que a referenciam, unidades definidas a
  partir dela) não gera novos erros. Assim cada problema aparece uma única vez:

  ```
  ingrediente massa = farinha + acucar;   # erro: não é possível somar volume (ml) com massa (g)
  ingrediente calda = massa * 2;          # sem erro adicional
  ```

- **Declaração antes do uso**, em todos os níveis: ingredientes (em expressões e em `usa`),
  unidades e receitas citadas em comandos. A análise é de uma passada. Uma pré-passagem só
  registra onde cada nome é declarado, para distinguir "inexistente" de "usado antes da
  declaração" e para indicar a qual receita pertence um ingrediente citado na receita errada.
- **Restrições de valor por avaliação constante.** O programa não tem entrada: toda
  expressão é constante. Depois que uma expressão passa pela tipagem, ela é avaliada
  (`receita/evaluator.py`) para verificar se a unidade tem valor positivo, conforme pede o
  brief. A mesma avaliação permite dois acréscimos ao brief:
  - ingredientes e durações também precisam ser positivos, porque `1 g - 2 g` de farinha ou
    `10 min - 1 h` de forno não fazem sentido;
  - divisão por zero é detectada em qualquer divisor que valha zero, não só no literal `0`.

  A tipagem continua separada da avaliação: as dimensões são verificadas sem olhar valores, e
  a avaliação só roda sobre expressões bem tipadas.
- **Receita redeclarada.** O corpo da segunda declaração ainda é analisado (os erros dele
  também aparecem), mas ela não é registrada: comandos se referem sempre à primeira.
- **Receita vazia** (`receita r rende 1 porcao { }`) é válida.
- **Erros ordenados por linha**, com os avisos listados depois dos erros.

### Observação sobre o exemplo do enunciado

No programa de exemplo do brief, `acucar` é `300 g` em `bolo_cenoura` e `1 xicara` em
`cobertura`. Por isso `compras bolo_cenoura para 20 porcoes, cobertura para 20 porcoes;` é
rejeitado com o erro 8, exatamente o caso que o próprio brief descreve. Os exemplos em
`exemplos/` usam `acucar` em gramas nas duas receitas.

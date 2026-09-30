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

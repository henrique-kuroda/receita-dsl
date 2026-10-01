# Receita

Receita é uma linguagem de domínio específico para receitas culinárias escaláveis, em que
**o sistema de unidades de medida é o sistema de tipos**. Massa, volume, contagem e tempo são
dimensões distintas. A conversão entre unidades da mesma dimensão é implícita, e combinar
dimensões diferentes, como somar gramas com mililitros, é um erro de tipo detectado antes da
execução (inspirado em Kennedy, *Dimension types*, 1994).

O interpretador executa três operações sobre as receitas:

1. **escalar** uma receita para N porções;
2. gerar a **lista de compras** que consolida várias receitas;
3. montar o **cronograma** de preparo a partir dos passos e de suas durações.

Trabalho final de Teoria da Computação e Compiladores (Engenharia de Computação): lexer e parser
LALR gerados com [SLY](https://github.com/dabeaz/sly), análise semântica com tabela de símbolos
em escopos e verificação de tipos dimensionais, e interpretação por visitors sobre a AST.

```
receita bolo rende 8 porcoes {
    ingrediente farinha = 2 xicara;
    ingrediente acucar  = 300 g;
    ingrediente ovos    = 3 un;
    passo "Misturar" dura 10 min usa farinha, acucar, ovos;
    passo "Assar" dura 1 h - 20 min;
}

escalar bolo para 20 porcoes;
```
```
$ python -m receita bolo.rec
Receita bolo para 20 porções (rende 8, fator 2.5)
  farinha  1.2 l
  acucar   750 g
  ovos     8 un (7.5)
```

## Instalação

Requer Python 3.10 ou mais recente. As únicas dependências são `sly` e `pytest`.

```bash
git clone https://github.com/henrique-kuroda/receita-dsl.git
cd receita-dsl
python -m venv .venv
.venv/Scripts/activate        # Windows; no Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

```bash
python -m receita arquivo.rec              # analisa e executa os comandos
python -m receita arquivo.rec --tokens     # lista de tokens
python -m receita arquivo.rec --ast        # árvore sintática indentada
python -m receita arquivo.rec --simbolos   # tabela de símbolos após a análise semântica
```

As flags de inspeção analisam o programa e mostram a listagem pedida, sem executar os comandos.

| Código de saída | Significado |
|---|---|
| 0 | sucesso (avisos não bloqueiam) |
| 1 | erro léxico ou sintático, ou arquivo ilegível |
| 2 | erro semântico |

## A linguagem

```
# comentário até o fim da linha

unidade pitada = 0.5 g;                     # unidade nova, com a dimensão da expressão

receita nome rende 8 porcoes {
    ingrediente farinha = 2 xicara;          # quantidade: número + unidade
    ingrediente sal     = farinha * 0.01;    # expressão com ingredientes já declarados
    passo "Descrição" dura 1 h - 20 min usa farinha, sal;
}

escalar nome para 20 porcoes;
compras nome para 20 porcoes, outra;        # sem "para", usa o rendimento da receita
cronograma nome, outra inicio 14:00;        # sem "inicio", horários relativos (T+0:05)
```

- Expressões: `+ - * /`, parênteses e menos unário, com a precedência usual.
- Números aceitam decimais com ponto (`0.5`), e toda a aritmética é exata, com frações.
- Strings ficam entre aspas duplas e podem ter acentos; identificadores não podem.
- `porcao` é sinônimo de `porcoes`.

### Unidades nativas

| Dimensão | Unidades |
|---|---|
| massa | `mg`, `g`, `kg` |
| volume | `ml`, `l`, `xicara` (240 ml), `colher_sopa` (15 ml), `colher_cha` (5 ml) |
| contagem | `un`, `duzia` (12 un) |
| tempo | `s`, `min`, `h` |

### Regras de tipo

- `+` e `-` exigem a mesma dimensão: `1 kg + 200 g` é válido, `300 g + 200 ml` não.
- `*` exige um escalar: `farinha * 0.01` é válido, `2 g * 3 g` não.
- `/` por escalar mantém a dimensão; entre duas quantidades da mesma dimensão, resulta em
  escalar (`1 kg / 250 g` = 4).
- Ingredientes são massa, volume ou contagem; durações de passo são tempo; unidades
  declaradas não podem ser escalares.
- Não há conversão entre massa e volume (falta a densidade). Para medir açúcar em
  xícaras, declare uma unidade de massa: `unidade xicara_acucar = 180 g;`.

## Exemplos

Os programas ficam em [`exemplos/`](exemplos), e a saída de cada um, conferida pela suíte de
testes, fica em [`exemplos/saidas/`](exemplos/saidas).

| Arquivo | O que demonstra | Código de saída |
|---|---|---|
| [`bolo.rec`](exemplos/bolo.rec) | escalar e cronograma relativo | 0 |
| [`festa_completa.rec`](exemplos/festa_completa.rec) | unidades declaradas, três receitas, as três operações | 0 |
| [`erros_tipos.rec`](exemplos/erros_tipos.rec) | todas as violações de tipo dimensional | 2 |
| [`erros_escopo.rec`](exemplos/erros_escopo.rec) | redeclarações, nomes inexistentes, uso antes da declaração | 2 |
| [`erros_sintaticos.rec`](exemplos/erros_sintaticos.rec) | erros sintáticos com recuperação | 1 |
| [`erros_lexicos.rec`](exemplos/erros_lexicos.rec) | erros léxicos | 1 |

Saída de `festa_completa.rec` (trecho):

```
Lista de compras: bolo_cenoura (20 porções), cobertura (20 porções), brigadeiro (45 porções)
  acucar            1.2 kg
  cenoura           1.25 kg
  chocolate         217.5 ml
  farinha           1.2 l
  forminhas         45 un
  leite             625 ml
  leite_condensado  592.5 g
  manteiga          60 ml
  oleo              500 ml
  ovos              8 un (7.5)
  sal               2.5 g

Cronograma: bolo_cenoura, cobertura, brigadeiro (início 14:00)
  14:00 - 14:05  bolo_cenoura  Bater cenoura, ovos e óleo no liquidificador
  14:05 - 14:15  bolo_cenoura  Misturar com farinha, açúcar e sal
  14:15 - 14:55  bolo_cenoura  Assar a 180 graus
  14:55 - 15:03  cobertura     Levar ao fogo mexendo até engrossar
  15:03 - 15:18  brigadeiro    Cozinhar mexendo até desgrudar da panela
  15:18 - 16:18  brigadeiro    Esfriar
  16:18 - 16:48  brigadeiro    Enrolar e colocar nas forminhas
  Tempo total: 2 h 48 min
```

As quantidades são exibidas na unidade legível da dimensão (kg e l a partir de 1000, h e min
a partir de 60 min), com até duas casas decimais. Contagens fracionárias são arredondadas para
cima, com o valor exato entre parênteses.

### Mensagens de erro

Cada fase relata todos os erros que encontra, com a linha:

```
erro léxico [linha 5]: identificador 'açúcar' tem caracteres não permitidos (use letras sem acento, dígitos e _)
erro sintático [linha 9]: encontrou número '40' quando esperava 'dura'
erro semântico [linha 10]: não é possível somar volume (ml) com massa (g)
erro semântico [linha 20]: ingrediente 'farinha' não declarado na receita 'cobertura' (pertence à receita 'bolo')
aviso [linha 10]: ingrediente 'sal' não é usado em nenhum passo da receita 'bolo'
```

## Testes

```bash
python -m pytest
```

São cerca de 280 testes: unidades e conversões, lexer, parser (programas válidos e inválidos),
tipos, tabela de símbolos, um teste por erro semântico, interpretador, CLI e as saídas dos
exemplos.

## Estrutura

```
receita/
  __main__.py      CLI
  lexer.py         análise léxica (SLY)
  parser.py        análise sintática LALR (SLY), mensagens e recuperação de erros
  ast.py           nós da AST, visitor base e impressão em árvore
  units.py         dimensões, unidades nativas e conversões
  types.py         regras de tipos dimensionais e valores tipados (Amount)
  symbols.py       tabela de símbolos com escopos encadeados
  semantic.py      visitor de análise semântica
  evaluator.py     avaliação de expressões
  interpreter.py   visitor de execução: escalar, compras, cronograma
  display.py       exibição normalizada das quantidades
  errors.py        erros e avisos com número de linha
exemplos/          programas de exemplo e saídas esperadas
tests/             suíte pytest
docs/              documentação técnica
```

## Documentação

- [`docs/gramatica.md`](docs/gramatica.md): tokens, EBNF, conversão para o SLY, conflitos e
  erros sintáticos.
- [`docs/semantica.md`](docs/semantica.md): sistema de tipos, escopos, catálogo de erros e
  decisões.
- [`docs/execucao.md`](docs/execucao.md): semântica de cada comando e regras de exibição.
- [`docs/arquitetura.md`](docs/arquitetura.md): pipeline, responsabilidades dos módulos e
  pontos de extensão.

## Limitações e trabalhos futuros

- Conversão entre massa e volume via densidade por ingrediente.
- Sub-receitas (`inclui massa_basica`), já previstas na arquitetura.
- Cronograma com passos em paralelo.
- Dimensões compostas (produtos e potências, como em Kennedy).

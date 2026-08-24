# Aspirador de Pó em 4 quartos — com visualizador de busca

Exercício 2 da Aula 03 de IA & Robótica (Insper): modelar como espaço de estados um
aspirador de pó num apartamento 2×2 e resolvê-lo com os algoritmos de busca da
[aigyminsper](https://github.com/fbarth/ia-gym-insper).

Junto da solução vai um **visualizador**: uma página onde você cola qualquer subclasse de
`State` e acompanha a árvore de busca sendo construída nó a nó, com a fronteira, o laço do
algoritmo e o estado de cada nó lado a lado.

> **Online:** _cole aqui o endereço do deploy no Netlify._

---

## O que tem nesta pasta

```
AspiradorPo.py     a solução do exercício — 4 quartos, pronta para rodar
site/index.html    o visualizador: uma página, sem instalação, sem servidor
netlify.toml       configuração do deploy (site estático, sem build)
```

## Rodando a solução

```bash
pip install aigyminsper
python3 AspiradorPo.py
```

```
Aspirador de po - 4 quartos (2x2)
[*o] [* ]
[* ] [* ]
estado inicial: A#1111

Achou em 7 acoes, custo 7:
  1. Aspirar        4. MoverBaixo      7. Aspirar
  2. MoverDireita   5. Aspirar
  3. Aspirar        6. MoverEsquerda
```

## Rodando o visualizador localmente

Ele não precisa de Python instalado — o interpretador roda **dentro do navegador**, via
[Pyodide](https://pyodide.org). Só precisa ser servido por HTTP (abrir por `file://` faz o
navegador bloquear o download do WebAssembly):

```bash
cd site
python3 -m http.server 8000
# abra http://localhost:8000
```

Na primeira visita ele baixa ~10 MB do interpretador; depois fica em cache. Cole o seu
código no editor da esquerda, aperte **Rodar** (ou `⌘⏎`) e use `←` `→` para andar passo a
passo. Nada é enviado para servidor nenhum.

---

## O problema, modelado

|  |  |
|---|---|
| **Estado** | posição do robô + quais quartos estão sujos |
| **Espaço de busca** | 4 posições × 2⁴ combinações de sujeira = **64 estados** |
| **Ações** | `MoverEsquerda`, `MoverDireita`, `MoverCima`, `MoverBaixo`, `Aspirar` |
| **Objetivo** | os quatro quartos limpos (a posição do robô não importa) |
| **Custo** | 1 por ação |
| **Heurística** | `h()` = número de quartos ainda sujos |

```
planta:   A | B      mover liga só quartos vizinhos:
          -----      A–B, C–D na horizontal
          C | D      A–C, B–D na vertical
```

Três decisões de modelagem que valem ser ditas:

- **A sujeira é um dicionário**, não quatro parâmetros posicionais. Isso elimina de vez a
  classe de erro mais comum aqui — trocar a ordem dos argumentos numa transição e
  embaralhar a sujeira dos quartos sem perceber. Mover repassa `self.sujeira` inteiro.
- **O construtor copia o dicionário** (`dict(sujeira)`). Sem a cópia, todos os estados
  compartilhariam a mesma referência e aspirar um quarto limparia a árvore inteira.
- **`h()` nunca superestima**: cada quarto sujo exige pelo menos um `Aspirar`, então a
  heurística é admissível e o A* devolve o caminho ótimo. Verificado por força bruta nos
  64 estados.

## Por que `pruning='general'`

A `aigyminsper` recebe a política de poda como parâmetro, e **o padrão é `'without'`** — sem
poda nenhuma. Nesse problema isso é a diferença entre resolver e não terminar:

Nós **gerados** por cada busca, deixando todas terminarem:

| algoritmo | `general` | `father-son` | `without` |
|---|---:|---:|---:|
| Busca em largura | **156** | 4026 | 4026 |
| Custo uniforme | 142 | 1709 | 1709 |
| Aprofundamento iterativo | 294 | 1053 | 1053 |
| A* | 78 | 134 | 134 |
| Gananciosa | 19 | 19 | 19 |
| Profundidade limitada | 19 | 19 | 19 |

Todas acham o mesmo caminho ótimo de custo 7 — a largura sem poda só faz **4026 nós de
trabalho para visitar 64 estados**. Repare também que `father-son` não ajuda nada aqui: ela
só descarta o filho cujo `env()` é igual ao do pai, e neste problema toda ação muda o estado,
então a condição nunca dispara. Por isso o `main()` chama:

```python
BuscaLargura().search(estado_inicial(), pruning='general')
```

A poda `general` descarta um sucessor cujo `env()` já apareceu antes — e é aí que o `env()`
deixa de ser detalhe: se ele esquecer de incluir algum quarto, dois estados diferentes
passam a ter a mesma assinatura e a busca descarta caminhos válidos.

### Nó não é estado

Os dois números não são a mesma coisa, e confundi-los é o erro de leitura mais fácil de
cometer. Um **estado** é uma configuração do mundo; um **nó** é uma vez que a busca chegou
nele por algum caminho. A largura com `general` fecha assim:

```
156  nós criados        (155 gerados por successors() + a raiz)
 −91  podados           env() já visto, descartados na hora
= 65  admitidos na fronteira
 −62  retirados         (61 expandidos + 1 que era o objetivo)
=  3  sobraram          A#0000, B#0000, D#0000
```

Três detalhes que valem entender:

- **Os 3 que sobram são os outros estados objetivo.** O robô pode terminar em qualquer
  quarto, então há quatro estados objetivo; a busca achou um e parou com os outros três na
  fila.
- **61 expandidos, não 62.** Expandir é chamar `successors()`. O nó objetivo sai da fronteira
  e é *inspecionado*, mas a busca devolve o caminho antes de expandi-lo.
- **65 admissões para 64 estados.** A poda `general` só registra em `vistos` os nós que ela
  *insere*, e a raiz entra na fronteira por fora desse caminho — então o estado inicial pode
  ser admitido uma segunda vez. Aqui isso acontece: `MoverDireita` e depois `MoverEsquerda`
  voltam a `A#1111`. É um detalhe da biblioteca, não muda o resultado.

A caixinha **só estados distintos**, no visualizador, colapsa essa diferença: ela mostra um
nó por `env()` — os 4026 nós da largura sem poda viram os mesmos 64 estados.

---

## Usando o visualizador com outro problema

O visualizador não é um Python de uso geral: ele procura no código colado **uma subclasse
concreta de `State`** e dirige a busca ele mesmo. Para funcionar, o código precisa de três
coisas:

1. Uma classe herdando de `State` ou `HeuristicState` com os cinco métodos implementados
   (`successors`, `is_goal`, `description`, `cost`, `env`). Faltando um, o Python considera
   a classe abstrata e ela sequer é encontrada.
2. Um estado inicial construível: ou existe `estado_inicial()`, ou `SuaClasse("")` funciona
   sozinho.
3. Um `successors()` que devolva estados.

O seu `main()` **não é chamado** — quem conduz a busca é a página, com o algoritmo e a poda
escolhidos na barra de cima.

Dois ganchos opcionais deixam a visualização melhor:

```python
def estado_inicial():        # se o construtor precisar de argumentos
    return MeuProblema('', ...)

def desenhar(estado):        # desenho em texto, mostrado no inspetor de cada nó
    return "[*o] [* ]\n[* ] [* ]"
```

Qualquer `print()` — inclusive dentro de `successors()` — aparece no painel *saída*, o que
torna a página um depurador razoável. Quando o código levanta exceção, a linha culpada fica
marcada em vermelho na régua do editor e a árvore mostra até onde a busca tinha chegado.

## Como o visualizador funciona por dentro

A página carrega o CPython compilado para WebAssembly e executa o seu código de verdade —
não é uma simulação em JavaScript. Como a `aigyminsper` importa `matplotlib` e `networkx`,
que não existem no navegador, o `site/index.html` embute uma reimplementação enxuta da
biblioteca com a mesma API: `State`, `HeuristicState`, `Node` e os seis algoritmos com o
parâmetro `pruning`. Seus `import` funcionam sem alteração.

Essa reimplementação foi conferida contra a `aigyminsper` instalada de verdade: mesmo
código, seis algoritmos × duas políticas de poda, **custo e caminho idênticos nos doze
casos**.

## Limitações — o que esse Python do navegador não faz

Vale saber antes de colar algo mais ambicioso.

**Não é um terminal, é um executor de arquivo.** Não há REPL nem prompt, nada persiste entre
execuções, e **`input()` não funciona** — código que peça entrada trava ou dá erro. Cada
*Rodar* executa o texto do zero, num módulo novo.

**A biblioteca é uma reimplementação, não a original.** Consequências concretas:

- os parâmetros de desenho de grafo da `aigyminsper` (`trace=True`, `trace_fullscreen`,
  `trace_display_as_states`…) caem no `**kwargs` e são **ignorados em silêncio** — você pede
  o trace e simplesmente não aparece nada, sem aviso;
- `ParallelSearch` e o módulo de CSP (`csp_algorithms`, `CspState`) **não foram portados**;
  importá-los quebra;
- a equivalência com a biblioteca real é testada, não garantida.

**A poda não compara custos.** A `general` descarta um estado já visto sem olhar por quanto
se chegou nele. Com `cost()` uniforme, como neste aspirador, isso é inofensivo — o primeiro
caminho encontrado já é o mais barato. Com custos variáveis, ela pode jogar fora um caminho
melhor descoberto depois, e aí **o custo uniforme e o A\* deixam de garantir o ótimo**. É o
comportamento da biblioteca da disciplina, reproduzido aqui de propósito: o visualizador
mostra o que o seu código realmente faz, não o algoritmo do livro.

**Só a biblioteca padrão.** `random`, `math`, `collections`, `itertools`, `json` e afins
funcionam normalmente. `numpy`, `pandas` e companhia existiriam no Pyodide, mas a página não
os carrega — hoje um `import numpy` falha.

**Sem disco e sem rede.** O navegador não enxerga os arquivos da sua máquina: `open("dados.txt")`
não acha nada, e `requests` não existe.

**A busca é síncrona: enquanto roda, a aba congela**, e não há botão de cancelar. O campo
*máx nós* (600 por padrão) freia a geração de nós, mas **não protege contra um laço infinito
dentro do seu `successors()`** — nesse caso, fechar a aba.

**Limites de tamanho**, todos do navegador e não da teoria: a árvore deixa de ser desenhada
acima de ~1400 nós, e a saída do `print()` é cortada em 20 mil caracteres.

**Primeira visita precisa de internet** (o interpretador vem de um CDN; depois fica em cache)
e a página precisa ser servida por HTTP — abrir por `file://` faz o navegador bloquear o
download do WebAssembly.

**Versão:** CPython 3.13 compilado para WebAssembly. Para esse tipo de código o comportamento
é o mesmo do Python local; recursão muito profunda é o ponto mais provável de divergir.

Por fim, a amarra de fundo: a tela inteira — fronteira, poda, `env()`, g/h/f — assume o
modelo de busca em espaço de estados. Um problema de outra natureza até *executaria*, mas não
teria o que mostrar aqui.

## Publicando

O `site/` é estático — não há etapa de build:

- arraste a pasta `site/` em [app.netlify.com/drop](https://app.netlify.com/drop); ou
- `netlify deploy --prod` (o `netlify.toml` já aponta `publish = "site"`).

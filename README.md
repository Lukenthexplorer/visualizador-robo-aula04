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

| algoritmo | `pruning='general'` | sem poda |
|---|---:|---:|
| Busca em largura | 156 nós | não termina em tempo útil |
| Custo uniforme | 142 nós | idem |
| Aprofundamento iterativo | 294 nós | idem |
| A* | 78 nós | 134 nós |
| Gananciosa | 19 nós | 19 nós |
| Profundidade limitada | 19 nós | 19 nós |

Todos chegam ao mesmo custo ótimo, 7. Por isso o `main()` chama:

```python
BuscaLargura().search(estado_inicial(), pruning='general')
```

A poda `general` descarta um sucessor cujo `env()` já apareceu antes — e é aí que o `env()`
deixa de ser detalhe: se ele esquecer de incluir algum quarto, dois estados diferentes
passam a ter a mesma assinatura e a busca descarta caminhos válidos.

---

## Usando o visualizador com outro problema

Cole qualquer subclasse de `State` (ou `HeuristicState`). Dois ganchos opcionais deixam a
visualização melhor:

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

## Publicando

O `site/` é estático — não há etapa de build:

- arraste a pasta `site/` em [app.netlify.com/drop](https://app.netlify.com/drop); ou
- `netlify deploy --prod` (o `netlify.toml` já aponta `publish = "site"`).

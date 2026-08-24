"""Aspirador de pó num ambiente 2x2 — Aula 03, exercício 2.

Modelagem do espaço de estados:

    posição do robô  ->  4 possibilidades (A, B, C, D)
    sujeira          ->  2^4 = 16 combinações
    espaço de busca  ->  4 x 16 = 64 estados

    planta:   A | B        mover só liga quartos vizinhos:
              -----        A-B, C-D (horizontal) e A-C, B-D (vertical)
              C | D

A sujeira fica num dicionário, e não em quatro parâmetros soltos. É o que
impede o erro mais comum aqui: trocar a ordem dos argumentos numa transição
e "embaralhar" a sujeira dos quartos sem querer.

Para ver a busca passo a passo, abra o visualizador em site/index.html
"""

from aigyminsper.search.graph import HeuristicState
from aigyminsper.search.search_algorithms import BuscaLargura

QUARTOS = ["A", "B", "C", "D"]

# Quem faz fronteira com quem. Cada chave é uma ação possível naquele quarto.
VIZINHOS = {
    "A": {"MoverDireita": "B", "MoverBaixo": "C"},
    "B": {"MoverEsquerda": "A", "MoverBaixo": "D"},
    "C": {"MoverCima": "A", "MoverDireita": "D"},
    "D": {"MoverEsquerda": "C", "MoverCima": "B"},
}

# Situação inicial — mexa aqui para testar outros cenários.
POSICAO_INICIAL = "A"
SUJEIRA_INICIAL = {"A": True, "B": True, "C": True, "D": True}


class AspiradorPo(HeuristicState):
    """Um estado = onde o robô está + quais quartos estão sujos."""

    def __init__(self, op, loc=POSICAO_INICIAL, sujeira=None):
        super().__init__(op)
        self.loc = loc
        # dict(...) faz uma cópia: sem isso todos os estados compartilhariam
        # o mesmo dicionário e limpar um quarto limparia a árvore inteira.
        self.sujeira = dict(sujeira) if sujeira is not None else dict(SUJEIRA_INICIAL)

    def successors(self):
        """Todos os estados alcançáveis com uma única ação."""
        filhos = []

        # Mover: muda a posição e nada mais — a sujeira vai igualzinha.
        for acao, destino in VIZINHOS[self.loc].items():
            filhos.append(AspiradorPo(acao, destino, self.sujeira))

        # Aspirar: só existe como ação se o quarto atual estiver sujo.
        if self.sujeira[self.loc]:
            limpo = dict(self.sujeira)
            limpo[self.loc] = False
            filhos.append(AspiradorPo("Aspirar", self.loc, limpo))

        return filhos

    def is_goal(self):
        """Objetivo = os QUATRO quartos limpos (a posição do robô não importa)."""
        return not any(self.sujeira.values())

    def description(self):
        return "Aspirador de po - 4 quartos (2x2)"

    def cost(self):
        """Custo de uma ação. Todas custam o mesmo aqui."""
        return 1

    def h(self):
        """Estimativa do que falta: um Aspirar por quarto sujo.

        Nunca superestima (é preciso pelo menos isso), então é admissível —
        é o que garante que o A* devolve o caminho ótimo.
        """
        return sum(1 for quarto in QUARTOS if self.sujeira[quarto])

    def env(self):
        """Assinatura única do estado: posição + sujeira dos quatro quartos.

        É por aqui que a busca reconhece que já passou por um estado. Se o
        env() esquecer um quarto, dois estados diferentes viram o mesmo e a
        poda descarta caminhos válidos.
        """
        marcas = "".join("1" if self.sujeira[q] else "0" for q in QUARTOS)
        return f"{self.loc}#{marcas}"


# --- ganchos opcionais usados pelo visualizador ----------------------------

def estado_inicial():
    """Estado de onde a busca parte."""
    return AspiradorPo("", POSICAO_INICIAL, SUJEIRA_INICIAL)


def desenhar(estado):
    """Planta do apartamento em texto: '*' = sujo, 'o' = robô."""
    linhas = []
    for esquerda, direita in (("A", "B"), ("C", "D")):
        linhas.append(" ".join(
            "[{}{}]".format("*" if estado.sujeira[q] else " ",
                            "o" if estado.loc == q else " ")
            for q in (esquerda, direita)
        ))
    return "\n".join(linhas)


# --- execução --------------------------------------------------------------

def main():
    inicial = estado_inicial()
    print(inicial.description())
    print(desenhar(inicial))
    print(f"estado inicial: {inicial.env()}\n")

    # pruning='general' descarta estados cujo env() já apareceu. Sem ele
    # (o padrão da biblioteca é 'without') a busca em largura reexplora os
    # mesmos 64 estados infinitas vezes e não termina.
    resultado = BuscaLargura().search(inicial, pruning="general")

    if resultado is None:
        print("Nao achou solucao")
        return

    plano = [acao for acao in resultado.show_path().split(" ; ") if acao]
    print(f"Achou em {len(plano)} acoes, custo {resultado.g}:")
    for i, acao in enumerate(plano, start=1):
        print(f"  {i}. {acao}")
    print()
    print(desenhar(resultado.state))


if __name__ == "__main__":
    main()

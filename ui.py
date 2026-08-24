#!/usr/bin/env python3
"""Visualizador passo a passo das buscas do aigyminsper.

    python3 ui.py                  # abre com AspiradorPo.py no editor
    python3 ui.py OitoNumeros.py   # ou qualquer outro problema

Abre o navegador em http://localhost:8000. O codigo fica num editor dentro
da propria pagina: cole, aperte Rodar (ou ctrl+enter) e veja a arvore de
busca sendo construida no lado direito. Nada e gravado em disco -- o
arquivo passado na linha de comando so serve para preencher o editor.

O codigo colado so precisa ter uma subclasse de State (ou HeuristicState).
Opcionalmente ele pode definir:

    def estado_inicial():        # se o construtor precisar de argumentos
        return MeuProblema('', ...)

    def desenhar(estado):        # desenho em texto, mostrado no inspetor
        return "A B\\nC D"

Qualquer print() -- inclusive dentro de successors() -- aparece no painel
"saida" embaixo do editor.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import json
import linecache
import secrets
import sys
import traceback
import types
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aigyminsper.search.graph import Node, State

AQUI = Path(__file__).resolve().parent
ARQUIVO_VIRTUAL = "<codigo colado>"
LIMITE_SAIDA = 20_000


# ---------------------------------------------------------------------------
# 1. Transformar o codigo colado num modulo Python de verdade
# ---------------------------------------------------------------------------

def modulo_do_codigo(fonte: str, nome: str = "problema_colado") -> types.ModuleType:
    """Executa o codigo do editor num modulo novo em folha."""
    modulo = types.ModuleType(nome)
    modulo.__file__ = ARQUIVO_VIRTUAL
    # registrar no linecache faz o traceback mostrar a linha de codigo errada,
    # e nao so o numero dela
    linecache.cache[ARQUIVO_VIRTUAL] = (len(fonte), None, fonte.splitlines(True),
                                        ARQUIVO_VIRTUAL)
    sys.modules[nome] = modulo
    exec(compile(fonte, ARQUIVO_VIRTUAL, "exec"), modulo.__dict__)  # noqa: S102
    return modulo


def achar_classe(modulo: types.ModuleType) -> type[State]:
    """Descobre qual classe do codigo colado e o problema de busca."""
    candidatas = [
        obj for _, obj in inspect.getmembers(modulo, inspect.isclass)
        if issubclass(obj, State) and obj.__module__ == modulo.__name__
        and not inspect.isabstract(obj)
    ]
    if not candidatas:
        raise TypeError(
            "nao achei nenhuma subclasse concreta de State no codigo. "
            "Faltou herdar de State/HeuristicState, ou faltou implementar "
            "algum metodo abstrato (successors, is_goal, description, cost, env)?"
        )
    return candidatas[-1]


def criar_estado(modulo, classe) -> State:
    """Monta o estado inicial: usa estado_inicial() se existir, senao Classe('')."""
    fabrica = getattr(modulo, "estado_inicial", None)
    if callable(fabrica):
        return fabrica()
    try:
        return classe("")
    except TypeError as erro:
        raise TypeError(
            f"{classe.__name__}('') nao funciona ({erro}). Defina no seu codigo:\n\n"
            f"    def estado_inicial():\n"
            f"        return {classe.__name__}('', ...)\n"
        ) from erro


# ---------------------------------------------------------------------------
# 2. A busca, instrumentada
#
# O esqueleto abaixo e o mesmo dos seis algoritmos do aigyminsper. A unica
# diferenca entre eles esta em duas linhas: quem sai da fronteira (tirar) e
# se ha limite de profundidade. A poda ("without" / "father-son" / "general")
# e o parametro `pruning` da biblioteca.
# ---------------------------------------------------------------------------

LIMITADOS = ("profundidade", "iterativa")
ORDENADOS = {"custo_uniforme": lambda n: n.g,
             "gananciosa": lambda n: n.h(),
             "aestrela": lambda n: n.f()}


def tirar(aberta: list[Node], alg: str) -> Node:
    """Retira um no da fronteira -- e so isso que muda de um algoritmo pro outro."""
    if alg == "largura":
        return aberta.pop(0)                       # fila: o mais antigo
    if alg in LIMITADOS:
        return aberta.pop()                        # pilha: o mais recente
    aberta.sort(key=ORDENADOS[alg], reverse=True)  # ordena e tira o menor
    return aberta.pop()


def buscar(inicial: State, alg: str, poda: str, m: int, max_nos: int,
           desenhar=None) -> dict:
    """Roda a busca guardando um evento por acao, para a interface reproduzir."""
    nos: list[dict] = []
    passos: list[dict] = []
    estouro = False

    def cadastrar(no: Node, pai: Node | None) -> None:
        atributos = {
            k: v if isinstance(v, (int, float, str, bool, type(None))) else str(v)
            for k, v in vars(no.state).items() if k != "operator"
        }
        no.vid = len(nos)
        nos.append({
            "id": no.vid, "pai": pai.vid if pai else None,
            "op": str(no.state.operator), "env": str(no.state.env()),
            "g": no.g, "h": no.h(), "f": no.f(), "prof": no.depth,
            "attrs": atributos,
            "desenho": str(desenhar(no.state)) if desenhar else None,
        })

    def evento(tipo: str, linha: int, no: Node | None = None, msg: str = "") -> None:
        passos.append({"t": tipo, "l": linha, "no": no.vid if no else None, "msg": msg})

    solucao = None
    erro = None
    try:
        # aprofundamento iterativo = a limitada rodada com m = 1, 2, 3, ...
        limites = range(1, m + 1) if alg == "iterativa" else [m]
        for limite in limites:
            if alg == "iterativa":
                evento("reinicia", 1, msg=f"nova rodada com limite m = {limite}")

            raiz = Node(inicial, None)
            cadastrar(raiz, None)
            aberta: list[Node] = [raiz]
            vistos: set[str] = set()
            evento("inicio", 1, raiz, "aberta = [Node(estado_inicial, None)]")

            while aberta:
                if len(nos) >= max_nos:
                    estouro = True
                    evento("teto", 3, msg=f"parei em {max_nos} nos gerados")
                    break

                n = tirar(aberta, alg)
                evento("tira", 4, n, f"n = {n.state.env()}")

                if n.state.is_goal():
                    evento("objetivo", 5, n, "is_goal() -> True: devolve o caminho")
                    caminho: list[int] = []
                    atual: Node | None = n
                    while atual is not None:
                        caminho.append(atual.vid)
                        atual = atual.father_node
                    solucao = list(reversed(caminho))
                    break
                evento("testa", 5, n, "is_goal() -> False")

                if alg in LIMITADOS and n.depth >= limite:
                    evento("limite", 6, n,
                           f"profundidade {n.depth} = limite {limite}: nao expande")
                    continue

                for filho in n.state.successors():
                    novo = Node(filho, n)
                    cadastrar(novo, n)
                    evento("gera", 7, novo, f"successors() gerou '{novo.state.operator}'")

                    env = novo.state.env()
                    if poda == "without":
                        aceita, motivo = True, ""
                    elif poda == "father-son":
                        aceita = env != n.state.env()
                        motivo = "env() igual ao do pai"
                    else:  # general
                        aceita = env not in vistos
                        motivo = "env() ja esta em vistos"

                    if aceita:
                        aberta.append(novo)
                        if poda == "general":
                            vistos.add(env)
                        evento("insere", 10, novo, f"aberta.append({env})")
                    else:
                        evento("poda", 9, novo, f"podado: {motivo}")

            if solucao or estouro:
                break
        if solucao is None and not estouro:
            evento("falha", 11, msg="aberta ficou vazia: devolve None")

    except Exception:  # noqa: BLE001 -- o erro e do codigo do aluno: queremos mostrar
        erro = detalhar_erro()
        evento("erro", 0, msg=erro["msg"])

    return {"nos": nos, "passos": passos, "solucao": solucao,
            "erro": erro, "estouro": estouro}


def detalhar_erro() -> dict:
    """Empacota a excecao atual, achando a linha do codigo colado que estourou."""
    tipo, valor, tb = sys.exc_info()
    linha = None
    for quadro in traceback.extract_tb(tb):
        if quadro.filename == ARQUIVO_VIRTUAL:
            linha = quadro.lineno          # a ultima linha do codigo colado
    if isinstance(valor, SyntaxError) and valor.filename == ARQUIVO_VIRTUAL:
        linha = valor.lineno
    return {
        "msg": traceback.format_exception_only(tipo, valor)[-1].strip(),
        "trace": "".join(traceback.format_exception(tipo, valor, tb)),
        "linha": linha,
    }


def rodar(fonte: str, alg: str, poda: str, m: int, max_nos: int) -> dict:
    """Executa o codigo colado e roda uma busca. Nunca levanta excecao."""
    vazio = {"info": None, "nos": [], "passos": [], "solucao": None, "estouro": False}
    saida = io.StringIO()

    try:
        with contextlib.redirect_stdout(saida):
            modulo = modulo_do_codigo(fonte)
            classe = achar_classe(modulo)
            inicial = criar_estado(modulo, classe)
            desenhar = getattr(modulo, "desenhar", None)
            desenhar = desenhar if callable(desenhar) else None
            info = {
                "classe": classe.__name__,
                "descricao": str(inicial.description()),
                "env_inicial": str(inicial.env()),
                "tem_h": callable(getattr(inicial, "h", None)),
                "desenho": desenhar is not None,
            }
    except Exception:  # noqa: BLE001
        return {**vazio, "erro": detalhar_erro(), "saida": saida.getvalue()[:LIMITE_SAIDA]}

    with contextlib.redirect_stdout(saida):
        resultado = buscar(inicial, alg, poda, m, max_nos, desenhar)
    resultado["info"] = info
    resultado["saida"] = saida.getvalue()[:LIMITE_SAIDA]
    return resultado


# ---------------------------------------------------------------------------
# 3. Servidor local
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    semente = ""          # codigo que preenche o editor ao abrir
    nome_arquivo = ""
    token = ""            # impede que outra pagina do navegador poste codigo aqui

    def responder(self, corpo: bytes, tipo: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def json(self, dados: dict, status: int = 200) -> None:
        self.responder(json.dumps(dados).encode(), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802 -- nome exigido pela stdlib
        if self.path in ("/", "/index.html"):
            pagina = (AQUI / "ui.html").read_text(encoding="utf-8")
            pagina = (pagina.replace("__TOKEN__", self.token)
                            .replace("__ARQUIVO__", self.nome_arquivo)
                            .replace("__SEMENTE__", json.dumps(self.semente)))
            self.responder(pagina.encode(), "text/html; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/busca":
            self.send_error(404)
            return
        if self.headers.get("X-Token") != self.token:
            self.json({"erro": {"msg": "token invalido", "trace": "", "linha": None}}, 403)
            return
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            pedido = json.loads(self.rfile.read(tamanho) or b"{}")
        except (ValueError, TypeError):
            self.json({"erro": {"msg": "pedido invalido", "trace": "", "linha": None}}, 400)
            return
        self.json(rodar(
            pedido.get("codigo", ""),
            pedido.get("alg", "largura"),
            pedido.get("poda", "general"),
            int(pedido.get("m", 10)),
            int(pedido.get("max", 600)),
        ))

    def log_message(self, *_args) -> None:
        """Silencia o log de cada requisicao."""


def main() -> None:
    ap = argparse.ArgumentParser(description="Visualizador de buscas do aigyminsper")
    ap.add_argument("problema", nargs="?", default="AspiradorPo.py",
                    help="arquivo .py que preenche o editor (padrao: AspiradorPo.py)")
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--nao-abrir", action="store_true", help="nao abrir o navegador")
    args = ap.parse_args()

    caminho = Path(args.problema)
    Handler.semente = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
    Handler.nome_arquivo = caminho.name if caminho.exists() else "(editor vazio)"
    Handler.token = secrets.token_urlsafe(16)

    for porta in range(args.porta, args.porta + 10):
        try:
            servidor = HTTPServer(("127.0.0.1", porta), Handler)
            break
        except OSError:
            continue
    else:
        sys.exit(f"nenhuma porta livre entre {args.porta} e {args.porta + 9}")

    endereco = f"http://localhost:{porta}"
    print(f"editor com {Handler.nome_arquivo}  ->  {endereco}   (ctrl+c para sair)")
    if not args.nao_abrir:
        webbrowser.open(endereco)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\ntchau")


if __name__ == "__main__":
    main()

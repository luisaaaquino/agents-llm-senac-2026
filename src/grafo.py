"""
Montagem do grafo do sistema.

O grafo é compilado uma vez, na importação, com o checkpointer em SQLite
(dados/checkpoints.db). É isso que permite continuar a conversa entre
turnos e retomar uma pausa humana mesmo depois de reiniciar o processo.
O conferir_grafo.py da raiz importa o `GRAFO` daqui.
"""
from __future__ import annotations

import sqlite3
import typing
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from . import config
from . import nos_anuncio as b
from . import nos_compra as a
from . import nos_comuns as c
from .estado import Estado


def _rota(fn):
    """Embrulha a função de roteamento sem anotação de tipo, para o LangGraph
    não tentar inferir o schema a partir dela."""
    def rotear(estado):
        return fn(estado)
    rotear.__name__ = fn.__name__
    return rotear


def construir(estado_tipo: type = Estado, checkpointer: Any = None):
    g = StateGraph(estado_tipo)

    # --- nós -----------------------------------------------------------------
    for nome, fn in [
        ("entrada", c.entrada), ("triagem", c.triagem), ("desambiguar", c.desambiguar),
        ("fora_escopo", c.fora_escopo), ("buscar_regras", c.buscar_regras),
        ("responder_regras", c.responder_regras), ("recusar_sem_base", c.recusar_sem_base),
        # Agente B
        ("iniciar_b", b.iniciar_b), ("agente_b", b.agente_b), ("perguntar_b", b.perguntar_b),
        ("ferramenta_preco", b.ferramenta_preco), ("ferramenta_regras", b.ferramenta_regras),
        ("portao_avaria", b.portao_avaria), ("avaliador", b.avaliador),
        ("recusar_item", b.recusar_item),
        ("preparar_aprovacao", b.preparar_aprovacao), ("aprovacao_vendedor", b.aprovacao_vendedor),
        ("publicar", b.publicar), ("registrar_indicio", b.registrar_indicio),
        ("preparar_moderacao", b.preparar_moderacao), ("moderacao", b.moderacao),
        ("aplicar_moderacao", b.aplicar_moderacao), ("finalizar_b", b.finalizar_b),
        # Agente A
        ("iniciar_a", a.iniciar_a), ("interpretar_compra", a.interpretar_compra),
        ("completar_pedido", a.completar_pedido), ("buscar_categoria", a.buscar_categoria),
        ("montar_sugestao", a.montar_sugestao), ("perguntar_a", a.perguntar_a),
    ]:
        # input_schema explícito para o LangGraph não ler o tipo da anotação do nó
        # (o que quebraria a versão do estado sem reducer).
        # `buscar_categoria` recebe o payload do Send, não o estado.
        g.add_node(nome, fn, input_schema=None if nome == "buscar_categoria" else estado_tipo)

    # --- entrada e triagem ----------------------------------------------------------
    g.add_edge(START, "entrada")
    g.add_conditional_edges("entrada", _rota(c.rotear_entrada),
                            ["triagem", "agente_b", "interpretar_compra"])
    g.add_conditional_edges("triagem", _rota(c.rotear_triagem),
                            ["iniciar_b", "iniciar_a", "buscar_regras", "desambiguar", "fora_escopo"])
    g.add_edge("desambiguar", END)
    g.add_edge("fora_escopo", END)

    # --- dúvida (busca no corpus em toda execução) ---------------------------------
    g.add_conditional_edges("buscar_regras", _rota(c.rotear_portao_rag),
                            ["responder_regras", "recusar_sem_base"])
    g.add_edge("responder_regras", END)
    g.add_edge("recusar_sem_base", END)

    # --- Agente B (laço) -----------------------------------------------------------
    g.add_edge("iniciar_b", "agente_b")
    g.add_conditional_edges("agente_b", _rota(b.rotear_b),
                            ["perguntar_b", "ferramenta_preco", "ferramenta_regras",
                             "portao_avaria", "registrar_indicio", "recusar_item", "finalizar_b"])
    g.add_edge("perguntar_b", END)
    g.add_conditional_edges("ferramenta_preco", _rota(b.rotear_preco), ["agente_b", "perguntar_b"])
    g.add_edge("ferramenta_regras", "agente_b")
    g.add_edge("registrar_indicio", "agente_b")
    g.add_conditional_edges("recusar_item", _rota(b.rotear_recusa), ["finalizar_b", "agente_b"])
    g.add_conditional_edges("portao_avaria", _rota(b.rotear_portao),
                            ["perguntar_b", "avaliador", "agente_b"])
    g.add_conditional_edges("avaliador", _rota(b.rotear_avaliador),
                            ["preparar_aprovacao", "preparar_moderacao", "agente_b", "finalizar_b"])
    g.add_edge("preparar_aprovacao", "aprovacao_vendedor")
    g.add_conditional_edges("aprovacao_vendedor", _rota(b.rotear_aprovacao), ["publicar", "finalizar_b"])
    g.add_edge("publicar", "finalizar_b")
    g.add_edge("preparar_moderacao", "moderacao")
    g.add_edge("moderacao", "aplicar_moderacao")
    g.add_edge("aplicar_moderacao", "finalizar_b")
    g.add_edge("finalizar_b", END)

    # --- Agente A (workflow com paralelização) -----------------------------------
    g.add_edge("iniciar_a", "interpretar_compra")
    g.add_edge("interpretar_compra", "completar_pedido")
    g.add_conditional_edges("completar_pedido", _rota(a.rotear_pedido), ["buscar_categoria", "perguntar_a"])
    g.add_edge("buscar_categoria", "montar_sugestao")
    g.add_edge("montar_sugestao", END)
    g.add_edge("perguntar_a", END)

    return g.compile(checkpointer=checkpointer)


def estado_sem_reducer_em(campo: str) -> type:
    """Cópia do Estado sem o reducer de `campo`. Usada só em
    scripts/demo_sem_reducer.py."""
    tipos = typing.get_type_hints(Estado, include_extras=True)
    tipos[campo] = typing.get_args(tipos[campo])[0]   # Annotated[X, reducer] -> X
    return TypedDict(f"EstadoSem_{campo}", tipos, total=False)


CHECKPOINTER = SqliteSaver(sqlite3.connect(config.CHECKPOINT_DB_PATH, check_same_thread=False))
GRAFO = construir(checkpointer=CHECKPOINTER)

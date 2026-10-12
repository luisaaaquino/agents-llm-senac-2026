"""
Agente A — consultor de compra (comprador), como nós do grafo.

Nível de autonomia: WORKFLOW, não agente (docs/arquitetura.md §3.3). Com a
entrada em texto, o que era "inferir intenção a partir de cliques" virou uma
extração (modelo) seguida de consultas determinísticas (código). O modelo
decide em dois pontos — quais categorias a intenção pede, e qual conjunto
de itens sugerir —, e entre eles não há laço: não houve, nos casos, decisão
que dependesse do resultado de uma busca para escolher a próxima busca.

Padrões: sequencial com portão (o pedido tem o que procurar?) e
paralelização por seções (uma busca por categoria, via Send — os ramos
escrevem no mesmo campo `candidatos`, e é por isso que ele tem reducer).
"""
from __future__ import annotations

import json
from typing import Any

from langgraph.types import Send

from . import config, db
from .contrato import Fonte
from .esquemas import PedidoCompra, Sugestao
from .estado import Estado
from .nos_comuns import chamar_modelo, conversa_texto, passo_codigo, saida


def iniciar_a(estado: Estado) -> dict[str, Any]:
    """[código] Começa uma busca nova — ou continua o refinamento de uma sugestão."""
    refinando = bool(estado.get("sugestao"))
    inicio = estado.get("msg_inicio", 0) if refinando else len(estado.get("mensagens", [])) - 1
    return {"msg_inicio": inicio, "pedido": None, "candidatos": [],
            "trajetoria": [passo_codigo("iniciar_a", refinando=refinando)]}


def interpretar_compra(estado: Estado) -> dict[str, Any]:
    """[MODELO] Texto livre -> parâmetros fechados de busca.
    Teto de passos do A é ESTRUTURAL: o workflow não tem laço, então um turno
    faz no máximo 2 chamadas de modelo (esta e montar_sugestao)."""
    pedido, inc = chamar_modelo("interpretar_compra", "compra-interpretar-v1.md",
                                conversa_texto(estado, desde=estado.get("msg_inicio", 0)),
                                PedidoCompra, max_tokens=300)
    return {**inc, "pedido": pedido.model_dump(), "candidatos": []}


def completar_pedido(estado: Estado) -> dict[str, Any]:
    """[código] Portão: sem categoria, tenta o sinal auxiliar (cliques); sem
    bairro, segue sem distância e DECLARA a escolha (§1.4, ambígua)."""
    pedido = dict(estado["pedido"])
    escolhas = [pedido["escolha"]] if pedido.get("escolha") else []
    if not pedido["categorias"]:
        cliques = db.historico_cliques(estado["usuario_id"])
        cats = list(dict.fromkeys(c["categoria"] for c in cliques if c["categoria"] in db.CATEGORIAS))
        if cats and "o_que_procura" in pedido.get("faltando", []):
            pedido["categorias"] = cats[:config.A_MAX_CATEGORIAS]
            pedido["faltando"] = []
            escolhas.append("você não disse o que procura; usei as categorias dos anúncios que "
                            f"você abriu recentemente: {', '.join(pedido['categorias'])}")
    if pedido["categorias"] and not pedido.get("bairro"):
        escolhas.append("você não disse o bairro; ordenei por preço, sem distância")
    return {"pedido": pedido, "escolha_declarada": "; ".join(escolhas) or None,
            "trajetoria": [passo_codigo("completar_pedido", pedido=pedido, escolhas=escolhas)]}


def rotear_pedido(estado: Estado) -> list[Send] | str:
    """[código] Sem categoria -> pergunta. Com categorias -> um ramo por categoria."""
    pedido = estado["pedido"]
    if not pedido["categorias"]:
        return "perguntar_a"
    teto = pedido.get("preco_max_item") or pedido.get("orcamento_total")
    return [Send("buscar_categoria", {"categoria": c, "preco_max": teto, "bairro": pedido.get("bairro"),
                                      "usuario_id": estado["usuario_id"]})
            for c in pedido["categorias"][:config.A_MAX_CATEGORIAS]]


def buscar_categoria(ramo: dict[str, Any]) -> dict[str, Any]:
    """[código] Um ramo paralelo: itens ATIVOS da categoria, de outros vendedores."""
    r = db.buscar_catalogo(ramo["categoria"], ramo["preco_max"], ramo["bairro"], ramo["usuario_id"])
    return {"candidatos": r["itens"] or [{"categoria": ramo["categoria"], "erro": r.get("erro")}],
            "trajetoria": [passo_codigo("buscar_categoria", argumentos=ramo,
                                        n=len(r["itens"]), erro=r.get("erro"))]}


def perguntar_a(estado: Estado) -> dict[str, Any]:
    """[código] Entrada incompleta: pergunta o que falta (§1.4)."""
    texto = ("Me conta o que você está procurando — um produto específico (ex.: uma geladeira) "
             "ou o que quer resolver (ex.: montar a cozinha)? Se puder, diga também o bairro e "
             "quanto quer gastar.")
    return {"mensagens": [{"quem": "agente", "texto": texto}], "conversa_aberta": "compra",
            "trajetoria": [passo_codigo("perguntar_a")],
            **saida(estado, agente="compra", tipo="pergunta", resultado=texto,
                    termino="aguardando_usuario", suficiente=False,
                    motivo="não dá para saber o que a pessoa procura",
                    faltando=["o que procura"])}


def conferir_sugestao(sug: Sugestao, candidatos: list[dict[str, Any]],
                      orcamento: float | None,
                      prioridade: list[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """[código] O schema garante uma lista de ints; não garante que sejam ids
    reais, nem que a soma caiba. Corrige e registra o que corrigiu."""
    por_id = {c["id"]: c for c in candidatos if "id" in c}
    correcoes, itens = [], []
    for i in sug.itens_ids:
        if i not in por_id:
            correcoes.append(f"id {i} não está entre os candidatos — removido")
        elif any(x["categoria"] == por_id[i]["categoria"] for x in itens):
            correcoes.append(f"id {i} repete a categoria {por_id[i]['categoria']} — removido")
        else:
            itens.append(por_id[i])
    # Estourou o orçamento: sai a categoria de MENOR prioridade do pedido (o
    # modelo ordenou da mais para a menos importante), não a mais cara — numa
    # cozinha, cortar a geladeira para caber a mesa inverte a intenção.
    ordem = {c: i for i, c in enumerate(prioridade or [])}
    while orcamento and itens and sum(x["preco"] for x in itens) > orcamento:
        menos = max(itens, key=lambda x: (ordem.get(x["categoria"], len(ordem)), x["preco"]))
        itens.remove(menos)
        correcoes.append(f"soma acima de R$ {orcamento:.0f} — removida a categoria de menor "
                         f"prioridade: {menos['categoria']} (id {menos['id']})")
    return itens, correcoes


def montar_sugestao(estado: Estado) -> dict[str, Any]:
    """[MODELO + código] Escolhe o conjunto; o código confere ids e orçamento."""
    pedido = estado["pedido"]
    validos = [c for c in estado.get("candidatos", []) if "id" in c]
    sem_itens = sorted({c["categoria"] for c in estado.get("candidatos", []) if "erro" in c})
    if not validos:
        texto = (f"Procurei {', '.join(pedido['categorias'])} ativos"
                 + (f" até R$ {pedido.get('preco_max_item') or pedido.get('orcamento_total'):.0f}"
                    if pedido.get("preco_max_item") or pedido.get("orcamento_total") else "")
                 + " e não há nenhum anúncio assim agora. Itens usados somem rápido: vale "
                   "aumentar o orçamento ou voltar em alguns dias.")
        return {"mensagens": [{"quem": "agente", "texto": texto}], "conversa_aberta": None,
                "trajetoria": [passo_codigo("montar_sugestao", sem_candidatos=sem_itens)],
                **saida(estado, agente="compra", tipo="recusa", resultado=texto, termino="recusou",
                        suficiente=False, motivo="nenhum item ativo nas categorias e faixa pedidas",
                        faltando=[f"itens ativos de {c}" for c in sem_itens],
                        dados={"pedido": pedido})}
    entrada_txt = json.dumps({"pedido": pedido, "candidatos": validos,
                              "categorias_sem_itens": sem_itens}, ensure_ascii=False, indent=1)
    sug, inc = chamar_modelo("montar_sugestao", "compra-sugestao-v1.md", entrada_txt, Sugestao,
                             max_tokens=300)
    itens, correcoes = conferir_sugestao(sug, validos, pedido.get("orcamento_total"),
                                         pedido.get("categorias"))
    justificativa = sug.justificativa
    cortadas = sorted({c["categoria"] for c in validos if c["id"] in sug.itens_ids}
                      - {i["categoria"] for i in itens})
    if correcoes:
        # O texto do modelo descreve a seleção DELE; se o código mudou a
        # seleção, o texto do modelo virou falso — quem corrigiu, escreve.
        soma = sum(i["preco"] for i in itens)
        justificativa = (f"Separei {len(itens)} itens ativos perto de você, somando R$ {soma:.0f}"
                         + (f" (dentro dos R$ {pedido['orcamento_total']:.0f})" if pedido.get("orcamento_total") else "")
                         + "." + (f" Ficou de fora: {', '.join(cortadas)}, porque não coube no orçamento."
                                  if cortadas else ""))
    texto = justificativa + "\n" + "\n".join(
        f"- {i['titulo']} — R$ {i['preco']:.0f}, {i['bairro']}"
        + (f" ({i['dist_km']} km)" if i.get("dist_km") is not None else "") for i in itens)
    fontes = [Fonte(tipo="banco", ref=f"anuncios[{i['id']}]",
                    trecho=f"{i['titulo']} · R$ {i['preco']:.0f} · {i['bairro']} · status ativo")
              for i in itens]
    return {**inc, "sugestao": {"itens": itens, "justificativa": justificativa,
                                "justificativa_do_modelo": sug.justificativa},
            "mensagens": [{"quem": "agente", "texto": texto}], "conversa_aberta": None,
            "trajetoria": inc["trajetoria"] + [passo_codigo("conferir_sugestao", correcoes=correcoes)],
            **saida(estado, agente="compra", tipo="sugestao", resultado=texto, termino="respondeu",
                    suficiente=True, motivo="itens ativos encontrados no catálogo", fontes=fontes,
                    faltando=[f"sem itens ativos: {c}" for c in sem_itens]
                    + [f"fora do orçamento: {c}" for c in cortadas],
                    dados={"pedido": pedido, "itens": itens, "correcoes": correcoes,
                           "soma": sum(i["preco"] for i in itens)})}

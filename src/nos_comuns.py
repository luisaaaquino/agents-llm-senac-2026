"""
Nós comuns: entrada, triagem (o roteador), e as rotas que não são de um
agente — dúvida sobre regras (RAG), entrada ambígua e fora do escopo.
Também os utilitários que todos os nós usam: chamar o modelo registrando a
trajetória, e montar a saída validada (o contrato do §1.2).

Convenção: todo nó devolve só o que mudou. Contadores (`passos`, `tokens`,
`custo_usd`) voltam como INCREMENTO — o reducer de soma faz a conta.
"""
from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel

from . import config, llm, rag
from .contrato import Fonte, SaidaSistema, Suficiencia
from .esquemas import RespostaRegras, Triagem
from .estado import Estado

# --- utilitários ----------------------------------------------------------------


def chamar_modelo(etapa: str, prompt: str, usuario: str, schema: type[BaseModel], *,
                  modelo: str | None = None, max_tokens: int = 800,
                  extra_sistema: str = "") -> tuple[Any, dict[str, Any]]:
    """Chama o modelo e devolve (objeto, incrementos de estado)."""
    sistema = llm.carregar_prompt(prompt) + (f"\n\n{extra_sistema}" if extra_sistema else "")
    objeto, uso = llm.chamada_estruturada(sistema, usuario, schema, modelo=modelo,
                                          max_tokens=max_tokens)
    passo = {"etapa": etapa, "decide": "modelo", "prompt": prompt, "modelo": uso.modelo,
             "tokens": uso.total, "segundos": round(uso.segundos, 2),
             "tentativas": uso.tentativas, "saida": objeto.model_dump()}
    return objeto, {"passos": 1, "tokens": uso.total, "custo_usd": uso.custo_usd,
                    "trajetoria": [passo]}


def passo_codigo(etapa: str, **dados: Any) -> dict[str, Any]:
    return {"etapa": etapa, "decide": "codigo", **dados}


def conversa_texto(estado: Estado, desde: int | None = None, ultimas: int = 12) -> str:
    msgs = estado.get("mensagens", [])[desde or 0:]
    return "\n".join(f"{m['quem']}: {m['texto']}" for m in msgs[-ultimas:])


def saida(estado: Estado, *, agente: str, tipo: str, resultado: str, termino: str,
          motivo: str, suficiente: bool, faltando: list[str] | None = None,
          dados: dict[str, Any] | None = None, fontes: list[Fonte] | None = None,
          escolha: str | None = None) -> dict[str, Any]:
    """Monta e VALIDA a saída (Pydantic). Devolve o update do estado."""
    objeto = SaidaSistema(
        thread_id=estado["thread_id"], agente=agente, tipo=tipo, resultado=resultado,
        dados=dados, fontes=fontes or [],
        suficiencia=Suficiencia(base_suficiente=suficiente, motivo=motivo, faltando=faltando or []),
        escolha_declarada=escolha or estado.get("escolha_declarada"),
        termino=termino, motivo_termino=motivo)
    return {"saida": objeto.model_dump(), "termino": termino, "motivo_termino": motivo}


def fontes_rag(trechos: list[dict[str, Any]], citados: list[str]) -> list[Fonte]:
    por_id = {t["id"]: t for t in trechos}
    return [Fonte(tipo="corpus", ref=c, trecho=por_id[c]["texto"]) for c in citados if c in por_id]


def turno_estourou(estado: Estado, max_segundos: float) -> bool:
    return time.time() - estado.get("inicio_turno", time.time()) > max_segundos


# --- entrada e triagem ------------------------------------------------------------


def entrada(estado: Estado) -> dict[str, Any]:
    """[código] Registra a fala e abre um turno novo (zera o que é por turno)."""
    texto = estado["texto_turno"].strip()
    return {"mensagens": [{"quem": "usuario", "texto": texto}],
            "termino": None, "motivo_termino": None, "saida": None,
            "decisao_humana": None, "pergunta_portao": None,
            "inicio_turno": time.time(),
            "trajetoria": [passo_codigo("entrada", texto=texto,
                                        conversa_aberta=estado.get("conversa_aberta"))]}


def rotear_entrada(estado: Estado) -> str:
    """[código] Conversa em andamento volta ao agente que perguntou; senão, triagem."""
    aberta = estado.get("conversa_aberta")
    if aberta == "anuncio":
        return "agente_b"
    if aberta == "compra":
        return "interpretar_compra"
    return "triagem"


def triagem(estado: Estado) -> dict[str, Any]:
    """[MODELO] Roteador: em qual rota a mensagem cabe (Literal com 5 rotas)."""
    resultado, inc = chamar_modelo("triagem", "triagem-v2.md",
                                   conversa_texto(estado, ultimas=6), Triagem, max_tokens=200)
    return {**inc, "rota": resultado.rota, "leituras": resultado.leituras,
            "categoria_mencionada": resultado.categoria, "escolha_declarada": None}


def rotear_triagem(estado: Estado) -> str:
    """[código] O modelo escolheu a rota; o mapa rota -> nó é fixo."""
    return {"vender": "iniciar_b", "comprar": "iniciar_a", "duvida": "buscar_regras",
            "ambigua": "desambiguar", "fora_escopo": "fora_escopo"}[estado["rota"]]


def desambiguar(estado: Estado) -> dict[str, Any]:
    """[código] Entrada ambígua: pergunta em vez de chutar (§1.4)."""
    nomes = {"vender": "anunciar o seu produto", "comprar": "procurar algo para comprar",
             "duvida": "tirar uma dúvida sobre as regras"}
    opcoes = [nomes[l] for l in (estado.get("leituras") or ["vender", "comprar"]) if l in nomes]
    texto = ("Entendi que você quer fazer mais de uma coisa. Para eu ajudar direito, "
             f"vamos por partes: você prefere começar por {' ou por '.join(opcoes)}?")
    return {"mensagens": [{"quem": "sistema", "texto": texto}], "conversa_aberta": None,
            "trajetoria": [passo_codigo("desambiguar", opcoes=opcoes)],
            **saida(estado, agente="nenhum", tipo="pergunta", resultado=texto,
                    termino="aguardando_usuario", suficiente=False,
                    motivo="a mensagem tem mais de uma leitura; o sistema pergunta em vez de escolher",
                    faltando=["qual das ações fazer primeiro"],
                    dados={"leituras": estado.get("leituras")})}


def fora_escopo(estado: Estado) -> dict[str, Any]:
    """[código] Recusa e diz o que o sistema faz (§1.4)."""
    texto = ("Isso foge do que eu faço aqui. Eu sou o assistente do Santo Desapego e posso: "
             "montar o anúncio de um produto seu, encontrar itens à venda perto de você, "
             "ou tirar dúvidas sobre as regras da plataforma (taxa, prazos, pagamento, entrega).")
    return {"mensagens": [{"quem": "sistema", "texto": texto}], "conversa_aberta": None,
            "trajetoria": [passo_codigo("fora_escopo")],
            **saida(estado, agente="nenhum", tipo="recusa", resultado=texto, termino="recusou",
                    suficiente=False, motivo="pedido fora do escopo do sistema",
                    faltando=["um pedido de compra, venda ou dúvida sobre a plataforma"])}


# --- rota de dúvida: RAG como etapa fixa --------------------------------------------


def buscar_regras(estado: Estado) -> dict[str, Any]:
    """[código] Busca vetorial no corpus de regras + portão de suficiência."""
    r = rag.buscar(estado["texto_turno"])
    portao = {"melhor": r["melhor_similaridade"], "limiar": r["limiar"], "suficiente": r["suficiente"]}
    return {"trechos_rag": r["trechos"], "rag_portao": portao, "consultas_rag": 1,
            "trajetoria": [passo_codigo("buscar_regras", consulta=r["pergunta"], k=r["k"],
                                        recuperados=[(t["id"], t["similaridade"]) for t in r["trechos"]],
                                        portao=portao)]}


def rotear_portao_rag(estado: Estado) -> str:
    """[código] Limiar numérico: abaixo dele não há base — nem chama o modelo."""
    return "responder_regras" if estado["rag_portao"]["suficiente"] else "recusar_sem_base"


def responder_regras(estado: Estado) -> dict[str, Any]:
    """[MODELO] Responde só com os trechos; a citação é conferida em código."""
    trechos = estado["trechos_rag"]
    contexto = json.dumps([{"id": t["id"], "secao": t["secao"], "texto": t["texto"]} for t in trechos],
                          ensure_ascii=False, indent=1)
    resp, inc = chamar_modelo("responder_regras", "resposta-regras-v1.md",
                              f"PERGUNTA: {estado['texto_turno']}\n\nTRECHOS:\n{contexto}",
                              RespostaRegras, max_tokens=400)
    cit = rag.verificar_citacoes(resp.citacoes, trechos)
    suficiente = resp.base_suficiente and bool(cit["validas"])
    conferencia = passo_codigo("conferir_citacoes", **cit, suficiente_final=suficiente)
    base = {"mensagens": [{"quem": "sistema", "texto": resp.resposta}], "conversa_aberta": None,
            **inc, "trajetoria": inc["trajetoria"] + [conferencia]}
    if suficiente:
        return {**base, **saida(estado, agente="duvida", tipo="resposta", resultado=resp.resposta,
                                termino="respondeu", suficiente=True,
                                motivo="resposta sustentada pelos trechos citados",
                                fontes=fontes_rag(trechos, cit["validas"]))}
    return {**base, **saida(estado, agente="duvida", tipo="recusa", resultado=resp.resposta,
                            termino="recusou", suficiente=False,
                            motivo="os trechos recuperados não respondem a pergunta",
                            faltando=["regra sobre este assunto no corpus"])}


def recusar_sem_base(estado: Estado) -> dict[str, Any]:
    """[código] Nada no corpus passou do limiar: recusa útil, sem chamar o modelo."""
    perto = [t["secao"] for t in (estado.get("trechos_rag") or [])[:2]]
    texto = ("Não encontrei nenhuma regra do Santo Desapego sobre isso, então prefiro não "
             "chutar. O mais perto que eu tenho é sobre: " + "; ".join(perto) + ". "
             "Para esse caso, a equipe responde pela Central de Ajuda.")
    return {"mensagens": [{"quem": "sistema", "texto": texto}], "conversa_aberta": None,
            "trajetoria": [passo_codigo("recusar_sem_base", portao=estado["rag_portao"])],
            **saida(estado, agente="duvida", tipo="recusa", resultado=texto, termino="recusou",
                    suficiente=False,
                    motivo=f"melhor similaridade {estado['rag_portao']['melhor']:.3f} abaixo do "
                           f"limiar {estado['rag_portao']['limiar']}",
                    faltando=["regra sobre este assunto no corpus"])}

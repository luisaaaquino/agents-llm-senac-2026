"""
Agente B — assistente de anúncio (vendedor), como nós do grafo.

O laço: `agente_b` (modelo escolhe UMA ação) -> ferramenta -> `agente_b`…
até ter um rascunho que passe pelo PORTÃO (código) e pelo AVALIADOR (modelo
+ código). Publicar não é ação do modelo: depois do avaliador, quem decide é
o vendedor (interrupt) — ou a moderação, se houve indício de avaria.

Pontos de parada (docs/humano.md):
  1. `aprovacao_vendedor` — ação que sai para o mundo (o anúncio fica visível
     para os vizinhos); perfil: o vendedor dono da conversa; prazo 24 h.
  2. `moderacao` — confiança baixa: o vendedor recusou declarar um defeito;
     perfil: moderador; prazo 48 h; silêncio = não publica.
Nada com efeito colateral roda dentro desses dois nós (o nó do interrupt
re-executa inteiro na retomada): as escritas ficam no nó anterior (abrir a
pendência) e no posterior (publicar / aplicar a decisão), ambas idempotentes.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Any

from langgraph.types import interrupt

from . import config, db, llm, memoria, rag
from .contrato import Fonte
from .esquemas import Avaliacao, DecisaoAnuncio, ResumoEpisodio
from .estado import Estado
from .nos_comuns import chamar_modelo, passo_codigo, saida, turno_estourou

# --- o que a conversa diz sobre avaria (DERIVADO, não guardado — §7.3) ---------
_NEGA = re.compile(r"\b(sem (nenhum )?(defeito|problema|avaria)s?|nenhum (defeito|problema)|"
                   r"n[ãa]o tem (nenhum )?(defeito|problema)|tudo funcionando|funciona (bem|perfeit\w*|100))",
                   re.I)
# Só termos inequívocos de defeito. Na 1ª versão havia "barulho", "solto" e
# "mancha": no caso 15 ("é só de apertar e fazer barulho", um brinquedo) o
# detector viu avaria onde não havia e o anúncio foi parar na moderação —
# o custo do degrau "regra em código" para julgar texto livre (docs/grafo.md §6.3).
_MENCIONA = re.compile(r"\b(defeito|avaria|quebrad\w*|rachad\w*|rachadura|trincad\w*|amassad\w*|"
                       r"riscad\w*|rasgad\w*|vaza\w*|n[ãa]o (gela|congela|funciona|liga|acende|esquenta)|"
                       r"demora\w* (pra|para) (gelar|congelar|esquentar|ligar)|barulho estranho|"
                       r"s[óo] n[ãa]o (gela|congela|funciona|liga|acende|esquenta))\b", re.I)
_PERGUNTA_AVARIA = re.compile(r"\b(defeito|avaria|problema|funciona|risco|amassad|quebr|rachad|estado)", re.I)


def avaria_da_conversa(estado: Estado) -> dict[str, Any]:
    msgs = estado.get("mensagens", [])[estado.get("msg_inicio", 0):]
    perguntada = any(m["quem"] == "agente" and _PERGUNTA_AVARIA.search(m["texto"]) for m in msgs)
    respondida_nao, falas = False, []
    for m in msgs:
        if m["quem"] != "usuario":
            continue
        if _MENCIONA.search(_NEGA.sub("", m["texto"])):
            falas.append(m["texto"])
        elif _NEGA.search(m["texto"]):
            respondida_nao = True
    return {"perguntada": perguntada, "negou_defeito": respondida_nao,
            "mencionada": bool(falas), "falas": falas,
            "tratada": perguntada or respondida_nao or bool(falas)}


def _preco_pedido(estado: Estado) -> float | None:
    for m in estado.get("mensagens", [])[estado.get("msg_inicio", 0):]:
        if m["quem"] == "usuario":
            achou = re.search(r"(?:R\$\s*)?(\d{2,5})(?:[.,]\d{2})?\s*(?:reais|conto|pila)?", m["texto"])
            if achou:
                return float(achou.group(1))
    return None


# --- início do agente: zera o estado do anúncio e lê a memória -------------------


def iniciar_b(estado: Estado) -> dict[str, Any]:
    """[código] Começa um anúncio novo: zera os campos do B e recupera a memória
    (semântica por chave, episódica por filtro+similaridade, procedural inteira)."""
    vendedor = estado["usuario_id"]
    categoria = estado.get("categoria_mencionada")
    fatos = memoria.ler_fatos(f"vendedor:{vendedor}")
    fatos_cat = memoria.ler_fatos(f"categoria:{categoria}") if categoria else []
    episodios = memoria.ler_episodios(categoria, estado["texto_turno"]) if categoria else []
    mem = {"vendedor": fatos, "categoria": fatos_cat,
           "episodios": [{k: e[k] for k in ("id", "data", "resumo", "desfecho", "avaria", "similaridade")}
                         for e in episodios],
           "procedural": memoria.ler_procedural()}
    return {"msg_inicio": len(estado.get("mensagens", [])) - 1,
            "passos_inicio": estado.get("passos", 0),
            "decisao_b": None, "faixa_preco": None, "regras_consultadas": None, "indicio": None,
            "rascunho": None, "avaliacao": None, "rodadas_avaliador": 0, "pendencia": None,
            "desfecho": None, "memoria": mem,
            "trajetoria": [passo_codigo("iniciar_b", memoria_recuperada={
                "fatos_vendedor": [f["chave"] for f in fatos],
                "fatos_categoria": [f["chave"] for f in fatos_cat],
                "episodios": [e["id"] for e in episodios]})]}


def _texto_memoria(mem: dict[str, Any] | None) -> str:
    if not mem:
        return ""
    partes = []
    for f in mem.get("vendedor", []):
        sufixo = " (antigo — confirme com o vendedor)" if f["a_confirmar"] else ""
        partes.append(f"- vendedor: {f['chave']} = {f['valor']}{sufixo}")
    for f in mem.get("categoria", []):
        partes.append(f"- categoria: {f['chave']} = {f['valor']}")
    for e in mem.get("episodios", []):
        partes.append(f"- anúncio parecido: {e['resumo']}")
    return ("MEMÓRIA (fatos de execuções anteriores; a conversa atual vence a memória):\n"
            + "\n".join(partes)) if partes else ""


# --- o laço ------------------------------------------------------------------------


def _assinatura(decisao: dict[str, Any]) -> str:
    chave = {k: decisao.get(k) for k in ("acao", "categoria", "bairro", "consulta", "indicio")}
    if decisao.get("acao") == "preencher_rascunho":
        chave["rascunho"] = decisao.get("rascunho")
    return hashlib.sha256(json.dumps(chave, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def detectar_laco(estado: Estado, assinatura: str) -> bool:
    """Reimplantado sobre o grafo (§6.5): `recursion_limit` limita o dano, não
    detecta. Laço = a MESMA ação com os MESMOS argumentos N vezes seguidas."""
    anteriores = [p["assinatura"] for p in estado.get("trajetoria", [])
                  if p.get("etapa") == "agente_b" and "assinatura" in p]
    ultimas = anteriores[-(config.LACO_REPETICOES - 1):]
    return len(ultimas) == config.LACO_REPETICOES - 1 and all(a == assinatura for a in ultimas)


def checar_orcamento(estado: Estado) -> str | None:
    """Os quatro tetos da Aula 05 — o framework só cobre o de passos (e mal)."""
    if estado.get("passos", 0) - estado.get("passos_inicio", 0) >= config.B_MAX_PASSOS:
        return f"passos: {config.B_MAX_PASSOS} decisões do modelo neste anúncio"
    if estado.get("tokens", 0) >= config.B_MAX_TOKENS:
        return f"tokens: {config.B_MAX_TOKENS}"
    if estado.get("custo_usd", 0.0) >= config.B_MAX_CUSTO_USD:
        return f"custo: US$ {config.B_MAX_CUSTO_USD}"
    if turno_estourou(estado, config.B_MAX_SEGUNDOS_TURNO):
        return f"tempo: {config.B_MAX_SEGUNDOS_TURNO:.0f}s no turno"
    return None


def agente_b(estado: Estado) -> dict[str, Any]:
    """[MODELO] Escolhe a próxima ação (ReAct, uma ação por volta)."""
    estouro = checar_orcamento(estado)
    if estouro:
        return {"desfecho": "orcamento", "motivo_termino": estouro,
                "trajetoria": [passo_codigo("agente_b", orcamento_estourado=estouro)]}

    avaria = avaria_da_conversa(estado)
    msgs = estado.get("mensagens", [])[estado.get("msg_inicio", 0):]
    # Ordem de descarte (docs/memoria.md §1.2): as 10 últimas falas ficam; das
    # antigas, só sobrevivem as que falam de avaria — nunca são descartadas.
    recentes = msgs[-10:]
    antigas_avaria = [m for m in msgs[:-10] if m["texto"] in avaria["falas"]]
    contexto = {
        "conversa": antigas_avaria + recentes,
        "observacoes": {
            "faixa_de_preco": estado.get("faixa_preco"),
            "regras_consultadas": estado.get("regras_consultadas"),
            "ultima_avaliacao": estado.get("avaliacao"),
            # Na 1ª rodada do teste de remoção o modelo repetiu registrar_indicio
            # 3x (o detector de laço parou). A observação agora diz o que já foi
            # feito e o que falta — dado, não instrução nova no prompt.
            "indicio_registrado": ({**estado["indicio"],
                                    "situacao": "JÁ REGISTRADO para a moderação — não registre de novo; "
                                                "monte o rascunho sem esse defeito"}
                                   if estado.get("indicio") else None),
        },
        "rascunho_atual": estado.get("rascunho"),
        "sobre_avaria": {k: avaria[k] for k in ("perguntada", "negou_defeito", "mencionada")},
    }
    extra = "\n\n".join(t for t in (estado["memoria"].get("procedural", "") if estado.get("memoria") else "",
                                     _texto_memoria(estado.get("memoria"))) if t)
    decisao, inc = chamar_modelo("agente_b", "agente-anuncio-v8.md",
                                 json.dumps(contexto, ensure_ascii=False, indent=1),
                                 DecisaoAnuncio, extra_sistema=extra)
    d = decisao.model_dump()
    assinatura = _assinatura(d)
    inc["trajetoria"][0]["assinatura"] = assinatura
    if detectar_laco(estado, assinatura):
        return {**inc, "decisao_b": d, "desfecho": "laco",
                "motivo_termino": f"a ação '{d['acao']}' com os mesmos argumentos "
                                  f"{config.LACO_REPETICOES}x seguidas"}
    return {**inc, "decisao_b": d}


def rotear_b(estado: Estado) -> str:
    """[código] A ação já foi escolhida pelo modelo; o mapa ação -> nó é fixo."""
    if estado.get("desfecho") in ("orcamento", "laco"):
        return "finalizar_b"
    return {"perguntar": "perguntar_b", "consultar_preco": "ferramenta_preco",
            "consultar_regras": "ferramenta_regras", "preencher_rascunho": "portao_avaria",
            "registrar_indicio": "registrar_indicio",
            "recusar_item": "recusar_item"}[estado["decisao_b"]["acao"]]


def perguntar_b(estado: Estado) -> dict[str, Any]:
    """[código] Encerra o turno com uma pergunta ao vendedor."""
    pergunta = estado.get("pergunta_portao") or (estado.get("decisao_b") or {}).get("pergunta") \
        or "Pode me contar um pouco mais sobre o produto?"
    return {"mensagens": [{"quem": "agente", "texto": pergunta}], "conversa_aberta": "anuncio",
            "pergunta_portao": None,
            "trajetoria": [passo_codigo("perguntar_b", pergunta=pergunta,
                                        origem="portao" if estado.get("pergunta_portao") else "modelo")],
            **saida(estado, agente="anuncio", tipo="pergunta", resultado=pergunta,
                    termino="aguardando_usuario", suficiente=False,
                    motivo="falta informação essencial para o anúncio",
                    dados={"rascunho": estado.get("rascunho")})}


def ferramenta_preco(estado: Estado) -> dict[str, Any]:
    """[código] Consulta estruturada no SQLite. Erro volta como dado."""
    d = estado["decisao_b"]
    r = db.consultar_preco_comparaveis(d.get("categoria") or "outro",
                                       d.get("bairro") or "")
    return {"faixa_preco": r, "trajetoria": [passo_codigo(
        "ferramenta_preco", argumentos={"categoria": d.get("categoria"), "bairro": d.get("bairro")},
        resultado=r)]}


def ferramenta_regras(estado: Estado) -> dict[str, Any]:
    """[código] RAG como FERRAMENTA do agente: só roda quando o modelo pede."""
    consulta = estado["decisao_b"].get("consulta") or estado["texto_turno"]
    r = rag.buscar(consulta)
    regras = ([{"id": t["id"], "texto": t["texto"]} for t in r["trechos"]] if r["suficiente"]
              else [{"id": None, "texto": "nenhuma regra do corpus responde esta dúvida"}])
    return {"regras_consultadas": regras, "trechos_rag": r["trechos"] if r["suficiente"] else [],
            "consultas_rag": 1,
            "trajetoria": [passo_codigo("ferramenta_regras", consulta=consulta,
                                        recuperados=[(t["id"], t["similaridade"]) for t in r["trechos"]],
                                        suficiente=r["suficiente"])]}


def recusar_item(estado: Estado) -> dict[str, Any]:
    """[código] O modelo quer recusar o produto: só vale citando uma regra que
    foi DE FATO consultada nesta conversa (citação verificada em código)."""
    citada = estado["decisao_b"].get("regra_citada")
    consultadas = {t["id"] for t in estado.get("regras_consultadas") or [] if t.get("id")}
    if citada in consultadas:
        return {"desfecho": "item_proibido",
                "motivo_termino": f"produto proibido pela regra {citada}",
                "trajetoria": [passo_codigo("recusar_item", regra=citada, valida=True)]}
    aviso = {"id": None, "texto": f"recusar_item recusado pelo código: a regra '{citada}' não foi "
                                  "consultada nesta conversa — use consultar_regras antes de recusar"}
    return {"regras_consultadas": (estado.get("regras_consultadas") or []) + [aviso],
            "trajetoria": [passo_codigo("recusar_item", regra=citada, valida=False)]}


def rotear_recusa(estado: Estado) -> str:
    return "finalizar_b" if estado.get("desfecho") == "item_proibido" else "agente_b"


def portao_avaria(estado: Estado) -> dict[str, Any]:
    """[código] Sequencial com portão: rascunho só passa se a conversa já tratou
    de avaria. O prompt pedia isso desde a v4 e o modelo pulava (Parte 1, e o
    gemini-3.5-flash-lite no primeiro teste) — virou regra verificável."""
    if not estado["decisao_b"].get("rascunho"):
        # erro de contrato vira dado: o laço continua, com a observação
        return {"avaliacao": {"aprovado": False,
                              "faltando": ["rascunho: a ação preencher_rascunho veio sem o rascunho"]},
                "trajetoria": [passo_codigo("portao_avaria", passou=False, erro="rascunho_ausente")]}
    avaria = avaria_da_conversa(estado)
    if avaria["tratada"]:
        return {"rascunho": estado["decisao_b"]["rascunho"],
                "trajetoria": [passo_codigo("portao_avaria", passou=True, avaria=avaria)]}
    tipicas = next((f["valor"] for f in (estado.get("memoria") or {}).get("categoria", [])
                    if f["chave"] == "avarias_tipicas"), None)
    if tipicas:
        pergunta = (f"Antes de montar o anúncio: em {estado['decisao_b']['rascunho']['categoria']} "
                    f"usada é comum aparecer {', '.join(tipicas)}. Alguma dessas coisas acontece "
                    "com o seu, ou tem outro defeito que o comprador vai notar?")
    else:
        pergunta = ("Antes de montar o anúncio: o produto tem algum defeito, risco ou algo que não "
                    "funciona 100%? Declarar evita problema na hora da entrega.")
    return {"pergunta_portao": pergunta,
            "trajetoria": [passo_codigo("portao_avaria", passou=False, avaria=avaria,
                                        usou_memoria=bool(tipicas))]}


def rotear_portao(estado: Estado) -> str:
    if estado.get("pergunta_portao"):
        return "perguntar_b"
    if not estado["decisao_b"].get("rascunho"):
        return "agente_b"
    return "avaliador"


# --- avaliador ------------------------------------------------------------------------


def checar_preco(rascunho: dict[str, Any], faixa: dict[str, Any] | None,
                 conversa: list[dict[str, str]]) -> str | None:
    """[código] Três caminhos para o preço passar (era critério do modelo na v2)."""
    if not faixa or "erro" in faixa:
        return None   # sem comparáveis: não há faixa contra a qual comparar
    preco = float(rascunho["preco"])
    if faixa["faixa_min"] * 0.7 <= preco <= faixa["faixa_max"] * 1.15:
        return None
    avisou = any(m["quem"] == "agente" and str(int(faixa["faixa_max"])) in m["texto"] for m in conversa)
    if avisou:
        return None   # o vendedor foi avisado da faixa e manteve: a alçada é dele
    return (f"preco: R$ {preco:.0f} está fora da faixa R$ {faixa['faixa_min']:.0f}–"
            f"{faixa['faixa_max']:.0f}; avise o vendedor da faixa antes de seguir")


def avaliador(estado: Estado) -> dict[str, Any]:
    """[MODELO + código] Avaliador-otimizador. O modelo julga texto; o código
    confere preço, avaria mencionada e recalcula `aprovado`."""
    rascunho = estado["rascunho"]
    conversa = estado.get("mensagens", [])[estado.get("msg_inicio", 0):]
    entrada_txt = json.dumps({"rascunho": rascunho,
                              "conversa": [f"{m['quem']}: {m['texto']}" for m in conversa],
                              "indicio_registrado": (estado.get("indicio") or {}).get("texto")},
                             ensure_ascii=False, indent=1)
    aval, inc = chamar_modelo("avaliador", "avaliador-anuncio-v4.md", entrada_txt, Avaliacao,
                              modelo=config.MODELO_AVALIADOR, max_tokens=400)
    faltando = list(aval.faltando)
    criterios_modelo = all([aval.tem_titulo, aval.tem_categoria, aval.tem_descricao,
                            aval.estado_coerente, aval.sem_invencao])
    erro_preco = checar_preco(rascunho, estado.get("faixa_preco"), conversa)
    if erro_preco:
        faltando.append(erro_preco)
    avaria = avaria_da_conversa(estado)
    if avaria["mencionada"] and not rascunho.get("avarias_declaradas") and not estado.get("indicio"):
        faltando.append("avaria: o vendedor mencionou um defeito que não está no rascunho — "
                        "declare-o, ou registre o indício se ele recusou")
    aprovado = criterios_modelo and not erro_preco and not (
        avaria["mencionada"] and not rascunho.get("avarias_declaradas") and not estado.get("indicio"))
    resultado = {**aval.model_dump(), "aprovado": aprovado, "faltando": faltando,
                 "aprovado_pelo_modelo": aval.aprovado}
    rodadas = estado.get("rodadas_avaliador", 0) + 1
    conferencia = passo_codigo("avaliador_conferencia", aprovado_final=aprovado,
                               checagens_codigo={"preco": erro_preco, "avaria": avaria})
    upd = {**inc, "trajetoria": inc["trajetoria"] + [conferencia],
           "avaliacao": resultado, "rodadas_avaliador": rodadas}
    if not aprovado and rodadas >= config.B_MAX_RODADAS_AVALIADOR:
        upd |= {"desfecho": "avaliador_reprovou",
                "motivo_termino": f"avaliador reprovou {rodadas}x: {faltando}"}
    return upd


def rotear_avaliador(estado: Estado) -> str:
    if estado["avaliacao"]["aprovado"]:
        return "preparar_moderacao" if estado.get("indicio") else "preparar_aprovacao"
    if estado.get("desfecho") == "avaliador_reprovou":
        return "finalizar_b"
    return "agente_b"


# --- ponto de parada 1: o vendedor aprova a publicação --------------------------------

CAMPOS_EDITAVEIS = {"titulo", "descricao", "preco", "estado_conservacao"}


def _expira(horas: int) -> str:
    return (datetime.now() + timedelta(hours=horas)).isoformat(timespec="seconds")


def preparar_aprovacao(estado: Estado) -> dict[str, Any]:
    """[código] Monta O QUE a pessoa vai ver (a ação exata e a consequência) e
    abre a pendência com prazo. Fica fora do nó do interrupt de propósito."""
    r = estado["rascunho"]
    expira = _expira(config.PRAZO_APROVACAO_VENDEDOR_H)
    pendencia = {
        "tipo": "aprovacao_vendedor", "perfil": "vendedor", "responsavel": estado["usuario_id"],
        "acao": "publicar_anuncio",
        "argumentos": r,
        "consequencia": (f"O anúncio \"{r['titulo']}\" por R$ {float(r['preco']):.2f} fica visível "
                         f"para os compradores dos 18 bairros, com retirada em {r['bairro']}. "
                         "Você pode pausar ou editar depois."),
        "opcoes": {"aprovar": {}, "editar": {"campos": sorted(CAMPOS_EDITAVEIS)},
                   "rejeitar": {"motivo": "texto livre"}},
        "expira_em": expira,
        "se_ninguem_responder": "o anúncio NÃO é publicado; o rascunho fica salvo nesta conversa",
    }
    db.abrir_pendencia(estado["thread_id"], "aprovacao_vendedor", "vendedor",
                       estado["usuario_id"], expira)
    return {"pendencia": pendencia,
            "trajetoria": [passo_codigo("preparar_aprovacao", expira_em=expira)]}


def aprovacao_vendedor(estado: Estado) -> dict[str, Any]:
    """[HUMANO] O grafo para aqui. Só o interrupt — nenhum efeito colateral."""
    resposta = interrupt(estado["pendencia"])
    return {"decisao_humana": resposta,
            "trajetoria": [passo_codigo("aprovacao_vendedor", decide="humano", resposta=resposta)]}


def rotear_aprovacao(estado: Estado) -> str:
    acao = (estado.get("decisao_humana") or {}).get("acao")
    return "publicar" if acao in ("aprovar", "editar") else "finalizar_b"


def publicar(estado: Estado) -> dict[str, Any]:
    """[código] ESCRITA. Aplica as edições (aprovar editando) e publica.
    Idempotente pelo conteúdo: a segunda aprovação não cria um segundo anúncio."""
    decisao = estado["decisao_humana"]
    rascunho = dict(estado["rascunho"])
    ignoradas = {}
    for campo, valor in (decisao.get("campos") or {}).items():
        if campo in CAMPOS_EDITAVEIS and valor not in (None, ""):
            rascunho[campo] = float(valor) if campo == "preco" else valor
        else:
            ignoradas[campo] = valor
    rascunho["estado_declarado"] = True
    r = db.publicar_anuncio(estado["usuario_id"], rascunho, estado["thread_id"])
    db.fechar_pendencia(estado["thread_id"])
    return {"rascunho": rascunho, "desfecho": "publicado",
            "escritas": {"anuncio_id": r["anuncio_id"], "anuncio_ja_existia": r["ja_existia"]},
            "trajetoria": [passo_codigo("publicar", argumentos=rascunho, edicoes_ignoradas=ignoradas,
                                        resultado=r)]}


# --- ponto de parada 2: a moderação decide sobre a avaria -------------------------------


def registrar_indicio(estado: Estado) -> dict[str, Any]:
    """[código] ESCRITA idempotente. O vendedor recusou declarar o defeito:
    registra o indício e volta ao laço para terminar o rascunho sem ele."""
    texto = estado["decisao_b"].get("indicio") or "possível avaria não declarada"
    falas = avaria_da_conversa(estado)["falas"]
    r = db.registrar_indicio(estado["usuario_id"], estado["thread_id"], texto,
                             falas[-1] if falas else None, anuncio_id=None)
    return {"indicio": {"id": r["indicio_id"], "texto": texto, "fala_literal": falas[-1] if falas else None},
            "escritas": {"indicio_id": r["indicio_id"], "indicio_ja_existia": r["ja_existia"]},
            "trajetoria": [passo_codigo("registrar_indicio", argumentos={"indicio": texto}, resultado=r)]}


def preparar_moderacao(estado: Estado) -> dict[str, Any]:
    """[código] Grava o anúncio como `aguardando_moderacao` (não aparece nas
    buscas), liga o indício a ele e abre a pendência de 48 h."""
    r = db.publicar_anuncio(estado["usuario_id"], estado["rascunho"], estado["thread_id"],
                            status="aguardando_moderacao")
    db.vincular_indicio(estado["indicio"]["id"], r["anuncio_id"])
    expira = _expira(config.PRAZO_MODERACAO_H)
    pendencia = {
        "tipo": "moderacao", "perfil": "moderador", "responsavel": None,
        "acao": "decidir_indicio_de_avaria",
        "argumentos": {"anuncio_id": r["anuncio_id"], "indicio_id": estado["indicio"]["id"],
                       "indicio": estado["indicio"]["texto"],
                       "fala_literal_do_vendedor": estado["indicio"]["fala_literal"],
                       "rascunho": estado["rascunho"]},
        "consequencia": ("publicar: o anúncio entra nas buscas como está; publicar_com_aviso: entra "
                         "com o aviso de avaria (texto editável); rejeitar: não é publicado."),
        "opcoes": {"publicar": {}, "publicar_com_aviso": {"aviso": "texto do aviso (editável)"},
                   "rejeitar": {"motivo": "texto livre"}},
        "expira_em": expira,
        "se_ninguem_responder": "o anúncio NÃO é publicado e o vendedor é avisado de que pode "
                                "refazê-lo declarando o estado do produto",
    }
    db.abrir_pendencia(estado["thread_id"], "moderacao", "moderador", None, expira)
    return {"pendencia": pendencia,
            "escritas": {"anuncio_id": r["anuncio_id"], "anuncio_ja_existia": r["ja_existia"]},
            "trajetoria": [passo_codigo("preparar_moderacao", anuncio=r, expira_em=expira)]}


def moderacao(estado: Estado) -> dict[str, Any]:
    """[HUMANO] O grafo para aqui até um moderador decidir. Só o interrupt."""
    resposta = interrupt(estado["pendencia"])
    return {"decisao_humana": resposta,
            "trajetoria": [passo_codigo("moderacao", decide="humano", resposta=resposta)]}


def aplicar_moderacao(estado: Estado) -> dict[str, Any]:
    """[código] ESCRITA. Aplica a decisão — idempotente nas duas tabelas."""
    d = estado["decisao_humana"]
    acao = d.get("acao")
    anuncio_id, indicio_id = estado["escritas"]["anuncio_id"], estado["indicio"]["id"]
    quem = d.get("quem", "desconhecido")
    if acao == "publicar":
        resultados = [db.atualizar_status_anuncio(anuncio_id, "ativo"),
                      db.decidir_indicio(indicio_id, "descartado", quem)]
        desfecho = "moderacao_publicou"
    elif acao == "publicar_com_aviso":
        aviso = d.get("aviso") or estado["indicio"]["texto"]
        resultados = [db.acrescentar_aviso(anuncio_id, aviso),
                      db.atualizar_status_anuncio(anuncio_id, "ativo"),
                      db.decidir_indicio(indicio_id, "confirmado", quem)]
        desfecho = "moderacao_publicou_com_aviso"
    elif acao == "expirou":
        resultados = [db.atualizar_status_anuncio(anuncio_id, "rejeitado"),
                      db.decidir_indicio(indicio_id, "expirado", quem)]
        desfecho = "expirou"
    else:
        resultados = [db.atualizar_status_anuncio(anuncio_id, "rejeitado"),
                      db.decidir_indicio(indicio_id, "confirmado", quem)]
        desfecho = "moderacao_rejeitou"
    db.fechar_pendencia(estado["thread_id"], "expirada" if acao == "expirou" else "resolvida")
    return {"desfecho": desfecho,
            "trajetoria": [passo_codigo("aplicar_moderacao", acao=acao, resultados=resultados)]}


# --- fim: memória de longo prazo + saída ----------------------------------------------

_TEXTOS = {
    "publicado": ("anuncio_publicado", "respondeu", True),
    "moderacao_publicou": ("anuncio_publicado", "respondeu", True),
    "moderacao_publicou_com_aviso": ("anuncio_publicado", "respondeu", True),
    "moderacao_rejeitou": ("anuncio_nao_publicado", "rejeitado", True),
    "rejeitado": ("anuncio_nao_publicado", "rejeitado", True),
    "expirou": ("anuncio_nao_publicado", "expirou", False),
    "orcamento": ("anuncio_nao_publicado", "orcamento", False),
    "avaliador_reprovou": ("anuncio_nao_publicado", "orcamento", False),
    "laco": ("anuncio_nao_publicado", "laco", False),
    "item_proibido": ("recusa", "recusou", True),
}


def _mensagem_final(estado: Estado, desfecho: str) -> str:
    r = estado.get("rascunho") or {}
    titulo, preco = r.get("titulo", "seu anúncio"), float(r.get("preco") or 0)
    return {
        "publicado": f"Pronto! \"{titulo}\" está no ar por R$ {preco:.2f}.",
        "moderacao_publicou": f"A moderação revisou e publicou \"{titulo}\" por R$ {preco:.2f}.",
        "moderacao_publicou_com_aviso": f"A moderação publicou \"{titulo}\" com um aviso sobre o estado do produto.",
        "moderacao_rejeitou": f"A moderação não aprovou \"{titulo}\". Você pode refazer o anúncio declarando o estado do produto.",
        "rejeitado": "Tudo bem, não publiquei. O rascunho fica salvo nesta conversa.",
        "expirou": ("O prazo para a decisão venceu e o anúncio não foi publicado. "
                    "Você pode refazê-lo quando quiser."),
        "orcamento": "Não consegui fechar o anúncio dentro do limite desta conversa. O rascunho ficou salvo; você pode completar pelo formulário.",
        "avaliador_reprovou": "O rascunho não passou na checagem depois de 3 tentativas. Ele ficou salvo; você pode completar pelo formulário.",
        "laco": "Fiquei repetindo o mesmo passo sem avançar, então parei. O rascunho ficou salvo; você pode completar pelo formulário.",
        "item_proibido": (estado.get("decisao_b") or {}).get("pergunta")
        or "Esse produto não pode ser anunciado no Santo Desapego.",
    }[desfecho]


def _escrever_memoria(estado: Estado, desfecho: str) -> list[dict[str, Any]]:
    """Política de escrita (docs/memoria.md §1.4): código por regra + 1 extração."""
    vendedor, r = estado["usuario_id"], estado.get("rascunho") or {}
    faixa, escritas = estado.get("faixa_preco") or {}, []
    if desfecho in ("publicado", "moderacao_publicou", "moderacao_publicou_com_aviso") and r:
        escritas.append(memoria.gravar_fato(f"vendedor:{vendedor}", "bairro_retirada", r["bairro"],
                                            fonte=f"anuncio:{estado['escritas']['anuncio_id']}"))
        pedido = _preco_pedido(estado)
        if "faixa_max" in faixa and pedido and pedido > faixa["faixa_max"]:
            escritas.append(memoria.gravar_fato(f"vendedor:{vendedor}", "aceita_sugestao_preco",
                                                float(r["preco"]) <= faixa["faixa_max"],
                                                fonte=f"anuncio:{estado['escritas']['anuncio_id']}"))
    if desfecho in ("moderacao_publicou_com_aviso", "moderacao_rejeitou") and r and estado.get("indicio"):
        atuais = next((f["valor"] for f in memoria.ler_fatos(f"categoria:{r['categoria']}")
                       if f["chave"] == "avarias_tipicas"), [])
        nova = estado["indicio"]["texto"]
        if nova not in atuais:
            escritas.append(memoria.gravar_fato(f"categoria:{r['categoria']}", "avarias_tipicas",
                                                atuais + [nova],
                                                fonte=f"moderacao:indicio:{estado['indicio']['id']}"))
    if r.get("categoria"):
        avaria = ("negada" if estado.get("indicio") else
                  "declarada" if r.get("avarias_declaradas") else "nenhuma")
        campos = {"data": datetime.now().date().isoformat(), "categoria": r.get("categoria"),
                  "bairro": r.get("bairro"), "preco_pedido": _preco_pedido(estado),
                  "faixa": [faixa.get("faixa_min"), faixa.get("faixa_max")] if "faixa_max" in faixa
                  else "sem comparáveis" if faixa else None,
                  "preco_final": r.get("preco"), "avaria": avaria, "desfecho": desfecho}
        resumo, uso = llm.chamada_estruturada(llm.carregar_prompt("extracao-memoria-v1.md"),
                                              json.dumps(campos, ensure_ascii=False), ResumoEpisodio,
                                              max_tokens=150)
        escritas.append({**memoria.gravar_episodio(vendedor, r["categoria"], r.get("bairro"),
                                                   desfecho, avaria, resumo.resumo),
                         "tokens_extracao": uso.total})
    if desfecho in ("laco", "orcamento", "avaliador_reprovou"):
        escritas.append(memoria.propor_regra(
            f"Quando o anúncio termina em '{desfecho}' na categoria {r.get('categoria')}, "
            f"revisar: {estado.get('motivo_termino')}", motivo=desfecho,
            origem_thread=estado["thread_id"]))
    return escritas


def finalizar_b(estado: Estado) -> dict[str, Any]:
    """[código] Fecha o anúncio: escreve memória, monta a saída, libera a conversa."""
    desfecho = estado.get("desfecho")
    if desfecho is None:   # veio da aprovação com rejeitar/expirou
        acao = (estado.get("decisao_humana") or {}).get("acao")
        desfecho = "expirou" if acao == "expirou" else "rejeitado"
        db.fechar_pendencia(estado["thread_id"], "expirada" if acao == "expirou" else "resolvida")
    tipo, termino, suficiente = _TEXTOS[desfecho]
    escritas_mem = _escrever_memoria(estado, desfecho)
    fontes = []
    faixa = estado.get("faixa_preco")
    if faixa:
        fontes.append(Fonte(tipo="banco" if "erro" not in faixa else "ferramenta",
                            ref=faixa.get("ref", "precos_comparaveis"),
                            trecho=json.dumps(faixa, ensure_ascii=False)))
    for t in estado.get("regras_consultadas") or []:
        if t.get("id"):
            fontes.append(Fonte(tipo="corpus", ref=t["id"], trecho=t["texto"]))
    if estado.get("escritas", {}).get("anuncio_id"):
        fontes.append(Fonte(tipo="banco", ref=f"anuncios[{estado['escritas']['anuncio_id']}]"))
    if estado.get("decisao_humana"):
        fontes.append(Fonte(tipo="humano", ref=str(estado["decisao_humana"].get("quem")),
                            trecho=json.dumps(estado["decisao_humana"], ensure_ascii=False)))
    texto = _mensagem_final(estado, desfecho)
    motivo = estado.get("motivo_termino") or desfecho
    return {"mensagens": [{"quem": "agente", "texto": texto}], "conversa_aberta": None,
            "desfecho": desfecho,
            "trajetoria": [passo_codigo("finalizar_b", desfecho=desfecho, memoria_escrita=escritas_mem)],
            **saida(estado, agente="anuncio", tipo=tipo, resultado=texto, termino=termino,
                    suficiente=suficiente, motivo=motivo, fontes=fontes,
                    faltando=[] if suficiente else ["anúncio concluído"],
                    dados={"anuncio": estado.get("rascunho"), "anuncio_id":
                           estado.get("escritas", {}).get("anuncio_id"),
                           "indicio": estado.get("indicio"), "desfecho": desfecho})}

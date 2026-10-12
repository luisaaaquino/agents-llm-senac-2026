"""
A porta do sistema: texto entra, SaidaSistema sai.

  conversar(Entrada)                      -> um turno de conversa
  responder_pendencia(thread, resposta)   -> a pessoa responde a um ponto de parada
  rotina_prazos(agora)                    -> o que acontece quando ninguém responde

thread_id = "<usuario_id>:<sessao_id>" (docs/memoria.md §5.5): o checkpoint
do LangGraph é endereçado por ele. Mesma chave, mesma conversa.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

from langgraph.types import Command

from . import config, db, llm, memoria
from .contrato import Entrada, Fonte, SaidaSistema, Suficiencia
from .grafo import GRAFO

__all__ = ["GRAFO", "conversar", "responder_pendencia", "rotina_prazos", "carimbo"]


def _cfg(thread_id: str) -> dict[str, Any]:
    # recursion_limit declarado (§6.6): o padrão do LangGraph 1.2 é 10007.
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": config.RECURSION_LIMIT}


def carimbo() -> dict[str, Any]:
    """Combinação em uso, registrada no início de cada execução (§2.2)."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, cwd=config.ROOT).stdout.strip()
        sujo = bool(subprocess.run(["git", "status", "--porcelain", "src", "conferir_grafo.py"],
                                   capture_output=True, text=True, cwd=config.ROOT).stdout.strip())
    except OSError:
        commit, sujo = "desconhecido", True
    return {"data": datetime.now().isoformat(timespec="seconds"), "commit": commit,
            "codigo_com_alteracao_nao_commitada": sujo,
            "modelo": config.MODELO, "modelo_avaliador": config.MODELO_AVALIADOR,
            "modelo_embedding": config.MODELO_EMBEDDING, "temperatura": config.TEMPERATURA,
            "prompts": llm.prompts_em_uso(), "memoria": memoria.snapshot(),
            "parametros": {"recursion_limit": config.RECURSION_LIMIT, "rag_k": config.RAG_K,
                           "rag_limiar": config.RAG_LIMIAR, "b_max_passos": config.B_MAX_PASSOS,
                           "laco_repeticoes": config.LACO_REPETICOES}}


def _pendencia_aberta(thread_id: str) -> dict[str, Any] | None:
    estado = GRAFO.get_state(_cfg(thread_id))
    for tarefa in estado.tasks:
        if tarefa.interrupts:
            return tarefa.interrupts[0].value
    return None


def _saida_pendencia(thread_id: str, pendencia: dict[str, Any]) -> SaidaSistema:
    moderacao = pendencia["tipo"] == "moderacao"
    texto = ("Seu anúncio foi para a revisão da moderação, porque conversamos sobre um possível "
             "defeito que não vai na descrição. A decisão sai em até 48 horas."
             if moderacao else
             f"Confere antes de publicar? {pendencia['consequencia']} Você pode aprovar, editar "
             "algum campo ou desistir.")
    return SaidaSistema(
        thread_id=thread_id, agente="anuncio",
        tipo="aguardando_moderacao" if moderacao else "aguardando_aprovacao",
        resultado=texto, dados={"pendencia": pendencia},
        fontes=[Fonte(tipo="ferramenta", ref=pendencia["acao"])],
        suficiencia=Suficiencia(base_suficiente=True,
                                motivo="o sistema tem o que precisa; a decisão é de uma pessoa",
                                faltando=[f"decisão do {pendencia['perfil']}"]),
        termino="aguardando_humano", motivo_termino=f"interrupt: {pendencia['tipo']}")


def _erro(thread_id: str, mensagem: str) -> SaidaSistema:
    return SaidaSistema(
        thread_id=thread_id, agente="nenhum", tipo="erro",
        resultado="Tive um problema técnico e não consegui continuar agora. Tente de novo em instantes.",
        suficiencia=Suficiencia(base_suficiente=False, motivo=mensagem), termino="erro_fatal",
        motivo_termino=mensagem)


def _executar(thread_id: str, entrada_grafo: Any) -> SaidaSistema:
    try:
        resultado = GRAFO.invoke(entrada_grafo, _cfg(thread_id))
    except (llm.ErroLLMFatal, llm.ErroLLMRecuperavelEsgotado) as erro:
        return _erro(thread_id, f"{type(erro).__name__}: {erro}")
    if resultado.get("__interrupt__"):
        return _saida_pendencia(thread_id, resultado["__interrupt__"][0].value)
    return SaidaSistema(**resultado["saida"])


def conversar(entrada: Entrada) -> SaidaSistema:
    """Um turno: a pessoa digitou `entrada.texto`."""
    pendencia = _pendencia_aberta(entrada.thread_id)
    if pendencia:
        # Com o grafo parado, uma fala nova não passa por cima da decisão pendente.
        return _saida_pendencia(entrada.thread_id, pendencia)
    return _executar(entrada.thread_id, {
        "texto_turno": entrada.texto, "thread_id": entrada.thread_id,
        "usuario_id": entrada.usuario_id, "sessao_id": entrada.sessao_id})


def responder_pendencia(thread_id: str, resposta: dict[str, Any], quem: str) -> SaidaSistema:
    """A pessoa responde ao ponto de parada: {"acao": "aprovar" | "editar" | "rejeitar"
    | "publicar" | "publicar_com_aviso" | "expirou", ...}.

    Idempotência por ESTADO: se não há mais pendência (a decisão já foi
    tomada), a segunda resposta não retoma nada. A idempotência por CONTEÚDO
    (chave nas escritas) cobre o caso em que o nó de escrita re-executa."""
    pendencia = _pendencia_aberta(thread_id)
    if pendencia is None:
        return SaidaSistema(
            thread_id=thread_id, agente="anuncio", tipo="erro",
            resultado="Essa decisão já foi registrada; nada foi feito de novo.",
            suficiencia=Suficiencia(base_suficiente=True, motivo="não há pendência aberta nesta conversa"),
            termino="respondeu", motivo_termino="resposta repetida: sem pendência aberta")
    perfil = pendencia["perfil"]
    if quem != "sistema:prazo":
        if perfil == "vendedor" and quem != pendencia["responsavel"]:
            return _erro(thread_id, f"{quem} não pode aprovar o anúncio de {pendencia['responsavel']}")
        if perfil == "moderador" and not quem.startswith("M-"):
            return _erro(thread_id, f"{quem} não tem perfil de moderador")
    if quem != "sistema:prazo" and datetime.now() > datetime.fromisoformat(pendencia["expira_em"]):
        # Resposta depois do prazo não vale: o caminho do silêncio já era o
        # declarado, e a rotina pode simplesmente não ter passado ainda.
        resposta = {"acao": "expirou", "resposta_tardia": resposta, "quem_respondeu_tarde": quem}
        quem = "sistema:prazo"
    validas = set(pendencia["opcoes"]) | {"expirou"}
    if resposta.get("acao") not in validas:
        return _erro(thread_id, f"resposta inválida: {resposta.get('acao')} (válidas: {sorted(validas)})")
    return _executar(thread_id, Command(resume={**resposta, "quem": quem}))


def rotina_prazos(agora: datetime | None = None) -> list[dict[str, Any]]:
    """O silêncio tem caminho declarado (§8.4): pendência vencida é retomada
    com {"acao": "expirou"} — o anúncio não é publicado, e a pessoa é avisada."""
    agora = agora or datetime.now()
    vencidas = [p for p in db.pendencias("aberta") if datetime.fromisoformat(p["expira_em"]) <= agora]
    saidas = []
    for p in vencidas:
        s = responder_pendencia(p["thread_id"], {"acao": "expirou"}, quem="sistema:prazo")
        saidas.append({"thread_id": p["thread_id"], "tipo": p["tipo"], "saida": s.model_dump()})
    return saidas

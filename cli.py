"""
Linha de comando do sistema.

    python cli.py preparar                 # banco do zero + índice do RAG (1x)
    python cli.py chat V-017               # conversa interativa como o usuário V-017
    python cli.py caso 01_simples          # roda um caso e grava logs/01_simples.json
    python cli.py casos                    # roda todos os casos, na ordem
    python cli.py pendencias               # o que está esperando uma pessoa
    python cli.py responder <thread> <json> <quem>   # ex.: '{"acao": "aprovar"}' V-017
    python cli.py prazos [+horas]          # roda a rotina de prazos (simula o relógio)
    python cli.py repetir 02_divergencia_preco 3   # estabilidade: N execuções do mesmo caso
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timedelta

from src import config, db, memoria, rag
from src.casos import CASOS, FALA_ESGOTADA, Caso
from src.contrato import Entrada
from src.grafo import GRAFO
from src.sistema import carimbo, conversar, responder_pendencia, rotina_prazos


def preparar(reindexar: bool = True) -> None:
    db.inicializar()
    memoria.zerar()
    GRAFO.checkpointer.setup()
    if config.CHECKPOINT_DB_PATH.exists():
        GRAFO.checkpointer.conn.execute("DELETE FROM checkpoints")
        GRAFO.checkpointer.conn.execute("DELETE FROM writes")
        GRAFO.checkpointer.conn.commit()
    if reindexar or not config.INDICE_DB_PATH.exists():
        print("índice do RAG:", rag.indexar())
    print("banco, memória e checkpoints zerados.")


def _trajetoria(thread_id: str) -> list:
    return GRAFO.get_state({"configurable": {"thread_id": thread_id}}).values.get("trajetoria", [])


def _contadores(thread_id: str) -> dict:
    v = GRAFO.get_state({"configurable": {"thread_id": thread_id}}).values
    return {k: v.get(k, 0) for k in ("passos", "tokens", "custo_usd", "consultas_rag")}


def rodar_caso(caso: Caso, destino=None) -> dict:
    thread = f"{caso.usuario_id}:{caso.nome}"
    GRAFO.checkpointer.delete_thread(thread)   # cada execução do caso começa do zero
    entrada = Entrada(texto=caso.primeira_fala, usuario_id=caso.usuario_id, sessao_id=caso.nome)
    log = {"caso": caso.nome, "prova": caso.prova, "esperado": caso.esperado,
           "carimbo": carimbo(), "thread_id": thread, "turnos": []}
    respostas, decisoes = list(caso.respostas), list(caso.decisoes)
    inicio = time.monotonic()

    def registrar(tipo: str, enviado: object, saida_obj) -> None:
        antes = registrar.n
        traj = _trajetoria(thread)
        registrar.n = len(traj)
        log["turnos"].append({"tipo": tipo, "enviado": enviado, "saida": saida_obj.model_dump(),
                              "trajetoria": traj[antes:]})
        print(f"  [{tipo}] {str(enviado)[:90]}")
        print(f"     -> {saida_obj.tipo} / {saida_obj.termino}: {saida_obj.resultado[:150]}")
    registrar.n = 0

    s = conversar(entrada)
    registrar("fala", entrada.texto, s)
    for _ in range(12):
        if s.termino == "aguardando_usuario" and s.agente in ("anuncio", "compra"):
            fala = respostas.pop(0) if respostas else FALA_ESGOTADA
            s = conversar(Entrada(texto=fala, usuario_id=caso.usuario_id, sessao_id=caso.nome))
            registrar("fala", fala, s)
        elif s.termino == "aguardando_humano":
            if caso.vencer_prazo:
                depois = datetime.now() + timedelta(hours=config.PRAZO_MODERACAO_H + 1)
                r = rotina_prazos(depois)
                from src.contrato import SaidaSistema
                s = SaidaSistema(**r[0]["saida"]) if r else s
                registrar("prazo_vencido", {"relogio_simulado": depois.isoformat(timespec="seconds")}, s)
                break
            if not decisoes:
                break
            quem, resposta = decisoes.pop(0)
            s = responder_pendencia(thread, resposta, quem)
            registrar("decisao_humana", {"quem": quem, **resposta}, s)
            if caso.repetir_decisao:
                antes = db.conectar().execute("SELECT COUNT(*) FROM anuncios").fetchone()[0]
                s2 = responder_pendencia(thread, resposta, quem)
                depois = db.conectar().execute("SELECT COUNT(*) FROM anuncios").fetchone()[0]
                registrar("decisao_humana_repetida", {"quem": quem, **resposta}, s2)
                # 2ª prova: re-executa o nó `publicar` a partir do checkpoint
                # anterior a ele (o que aconteceria se o processo morresse entre
                # a escrita no banco e a gravação do checkpoint).
                cfg = {"configurable": {"thread_id": thread}}
                anterior = next(h for h in GRAFO.get_state_history(cfg) if h.next == ("publicar",))
                GRAFO.invoke(None, anterior.config)
                original = [p for t in log["turnos"] for p in t["trajetoria"] if p["etapa"] == "publicar"]
                refeito = original + [p for p in GRAFO.get_state(cfg).values["trajetoria"]
                                      if p["etapa"] == "publicar"]
                depois_replay = db.conectar().execute("SELECT COUNT(*) FROM anuncios").fetchone()[0]
                log["prova_idempotencia"] = {
                    "anuncios_antes_da_2a_aprovacao": antes,
                    "anuncios_depois_da_2a_aprovacao": depois,
                    "anuncios_depois_de_reexecutar_publicar": depois_replay,
                    "publicar_executou_vezes": len(refeito),
                    "nota": "a 1ª é a execução original; a 2ª é a re-execução a partir do checkpoint anterior a publicar",
                    "resultado_de_cada_execucao": [p["resultado"] for p in refeito],
                    "criou_algo": len({antes, depois, depois_replay}) != 1}
                print(f"  idempotência: {log['prova_idempotencia']['anuncios_antes_da_2a_aprovacao']} -> "
                      f"{depois} -> {depois_replay} anúncios; publicar rodou {len(refeito)}x; "
                      f"ja_existia={[p['resultado']['ja_existia'] for p in refeito]}")
        else:
            break
    log["final"] = {"tipo": s.tipo, "termino": s.termino, "motivo": s.motivo_termino,
                    "segundos": round(time.monotonic() - inicio, 1), **_contadores(thread)}
    destino = destino or config.LOGS_DIR / f"{caso.nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  == {s.tipo} / {s.termino} · {log['final']} · log: {destino.relative_to(config.ROOT)}")
    return log


def chat(usuario_id: str) -> None:
    sessao = uuid.uuid4().hex[:6]
    print(f"conversa {usuario_id}:{sessao} — digite 'sair' para encerrar")
    while (texto := input("> ").strip()) and texto != "sair":
        s = conversar(Entrada(texto=texto, usuario_id=usuario_id, sessao_id=sessao))
        print(f"[{s.tipo} / {s.termino}] {s.resultado}")
        if s.termino == "aguardando_humano":
            print("  pendência:", json.dumps(s.dados["pendencia"]["argumentos"], ensure_ascii=False)[:300])
            print(f"  responda com: python cli.py responder {usuario_id}:{sessao} '<json>' <quem>")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "preparar":
        preparar()
    elif cmd == "chat":
        chat(args[1] if len(args) > 1 else "V-001")
    elif cmd == "caso":
        rodar_caso(CASOS[args[1]])
    elif cmd == "casos":
        for caso in CASOS.values():
            print(f"\n=== {caso.nome} ===")
            rodar_caso(caso)
    elif cmd == "repetir":
        caso, n = CASOS[args[1]], int(args[2]) if len(args) > 2 else 3
        pasta = config.LOGS_DIR / "medicoes" / "estabilidade"
        resumo = []
        for i in range(1, n + 1):
            print(f"\n=== {caso.nome} — execução {i}/{n} ===")
            log = rodar_caso(caso, pasta / f"{caso.nome}_r{i}.json")
            acoes = [p["saida"].get("acao") for t in log["turnos"] for p in t["trajetoria"]
                     if p["etapa"] == "agente_b" and "saida" in p]
            resumo.append({"execucao": i, **log["final"], "acoes_do_agente_b": acoes})
        (pasta / f"{caso.nome}_resumo.json").write_text(json.dumps(
            {"caso": caso.nome, "esperado": caso.esperado, "carimbo": carimbo(), "execucoes": resumo},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(resumo, ensure_ascii=False, indent=1))
    elif cmd == "pendencias":
        print(json.dumps(db.pendencias(), ensure_ascii=False, indent=2))
    elif cmd == "responder":
        print(responder_pendencia(args[1], json.loads(args[2]), args[3]).model_dump_json(indent=2))
    elif cmd == "prazos":
        horas = float(args[1].lstrip("+")) if len(args) > 1 else 0
        print(json.dumps(rotina_prazos(datetime.now() + timedelta(hours=horas)),
                         ensure_ascii=False, indent=2)[:3000])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

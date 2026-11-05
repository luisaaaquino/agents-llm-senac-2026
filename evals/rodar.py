"""
Roda o golden dataset contra o sistema entregue e grava o resultado da rodada.

    python -m evals.rodar --versao 2.1.0
    python -m evals.rodar --versao 2.1.0 --casos 01_simples,05_fora_do_corpus
    python -m evals.rodar --versao 2.1.0 --sem-juiz

Cada caso passa pelo mesmo caminho do `python cli.py caso ...`: as funções
conversar() e responder_pendencia() de src/sistema.py. A rodada começa com o
banco, a memória e os checkpoints zerados (os casos rodam em ordem, porque o
caso 13 depende da memória gravada pelo caso 04).

Saída em evals/resultados/v<versao>_<data>/:
  resultado.json   o número por classe, cada caso com as checagens e as métricas
  logs/<caso>.json o log completo de cada conversa
  traces.jsonl     os traces OpenTelemetry da rodada
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import cli
from src import config
from src import observabilidade as obs
from src.casos import Caso
from src.sistema import _git

from . import checagens, juiz

RAIZ = Path(__file__).resolve().parent
DATASET = RAIZ / "dataset.json"
RESULTADOS = RAIZ / "resultados"


def carregar_dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _caso(c: dict) -> Caso:
    return Caso(nome=c["id"], usuario_id=c["usuario_id"], primeira_fala=c["primeira_fala"],
                respostas=list(c.get("respostas", [])),
                decisoes=[tuple(d) for d in c.get("decisoes", [])],
                prova=c["por_que_existe"], esperado=json.dumps(c["esperado"], ensure_ascii=False),
                repetir_decisao=c.get("repetir_decisao", False), vencer_prazo=c.get("vencer_prazo", False))


def _falha_do_provedor(motivo: str) -> bool:
    return any(m in motivo for m in ("503", "UNAVAILABLE", "RateLimitError", "429", "RESOURCE_EXHAUSTED"))


def _ler_spans(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def _juiz(c: dict, log: dict, depois: dict, usar: bool) -> list[dict]:
    if not usar or not c["esperado"].get("juiz"):
        return []
    publicados = [a for a in depois["anuncios"] if a["status"] == "ativo"]
    if not publicados:
        return []
    falas = [t["enviado"] for t in log["turnos"] if t["tipo"] == "fala"]
    v = juiz.julgar(falas, publicados[-1])
    return [{"nivel": "juiz", "nome": "sem_invencao", "ok": v.sem_invencao,
             "detalhe": {"justificativa": v.justificativa, "afirmacao": v.afirmacao_inventada},
             "conta_na_nota": juiz.adotado()}]


def rodar(versao: str, ids: list[str] | None, usar_juiz: bool) -> Path:
    if versao != config.VERSAO_SISTEMA:
        sys.exit(f"--versao {versao} não bate com config.VERSAO_SISTEMA = {config.VERSAO_SISTEMA}")
    ds = carregar_dataset()
    casos = [c for c in ds["casos"] if not ids or c["id"] in ids]
    pasta = RESULTADOS / f"v{versao}_{datetime.now():%Y%m%d-%H%M}"
    (pasta / "logs").mkdir(parents=True, exist_ok=True)
    obs.usar_arquivo(pasta / "traces.jsonl")
    cli.preparar(reindexar=not config.INDICE_DB_PATH.exists())

    linhas = []
    for c in casos:
        print(f"\n=== {c['id']} ({c['classe']}) ===")
        antes = checagens.mundo(c["usuario_id"])
        inicio = time.monotonic()
        repeticoes_infra = 0
        while True:
            spans_inicio = len(_ler_spans(pasta / "traces.jsonl"))
            try:
                log = cli.rodar_caso(_caso(c), pasta / "logs" / f"{c['id']}.json")
                erro = None
            except Exception as e:  # noqa: BLE001 — a rodada continua; o caso conta como falha
                log, erro = {"turnos": [], "final": {}}, f"{type(e).__name__}: {e}"
                traceback.print_exc()
            # Falha do provedor (sobrecarga, limite de cota) não é falha do sistema:
            # o caso roda mais uma vez, e a repetição fica registrada.
            motivo = (log.get("final") or {}).get("motivo") or ""
            if repeticoes_infra < 1 and _falha_do_provedor(motivo):
                repeticoes_infra += 1
                print(f"  falha do provedor, repetindo o caso: {motivo[:120]}")
                time.sleep(30)
                continue
            break
        depois = checagens.mundo(c["usuario_id"])
        linhas.append({"caso": c, "log": log, "antes": antes, "depois": depois, "erro": erro,
                       "repeticoes_infra": repeticoes_infra,
                       "spans": (spans_inicio, len(_ler_spans(pasta / "traces.jsonl"))),
                       "segundos": round(time.monotonic() - inicio, 1)})

    spans = _ler_spans(pasta / "traces.jsonl")
    detalhes = []
    for l in linhas:
        c, log = l["caso"], l["log"]
        esp = c["esperado"]
        thread = f"{c['usuario_id']}:{c['id']}"
        if l["erro"]:
            checks = [{"nivel": "deterministico", "nome": "execucao_sem_excecao", "ok": False, "detalhe": l["erro"]}]
        else:
            ferramentas = checagens.ferramentas_do_trace(spans[l["spans"][0]:l["spans"][1]], thread)
            checks = (checagens.deterministicas(esp, log) + checagens.de_trajetoria(esp, ferramentas)
                      + checagens.de_resultado(esp, l["antes"], l["depois"], log) + checagens.de_compra(esp, log)
                      + _juiz(c, log, l["depois"], usar_juiz))
        contam = [k for k in checks if k.get("conta_na_nota", True)]
        final = log.get("final") or {}
        detalhes.append({
            "id": c["id"], "classe": c["classe"], "origem": c["origem"],
            "passou": all(k["ok"] for k in contam), "checagens": checks,
            "termino": final.get("termino", "erro_execucao"), "tipo": final.get("tipo"),
            "segundos": final.get("segundos", l["segundos"]), "tokens": final.get("tokens", 0),
            "custo_usd": final.get("custo_usd", 0.0), "passos": final.get("passos", 0),
            "repeticoes_por_falha_do_provedor": l["repeticoes_infra"],
        })

    por_classe: dict[str, list[bool]] = {}
    for d in detalhes:
        por_classe.setdefault(d["classe"], []).append(d["passou"])
    commit, sujo = _git()
    resultado = {
        "versao_sistema": config.VERSAO_SISTEMA, "commit": commit,
        "codigo_com_alteracao_nao_commitada": sujo,
        "data": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"versao": ds["versao"], "n": len(casos),
                    "por_origem": {o: sum(1 for c in casos if c["origem"] == o)
                                   for o in ("producao", "desenvolvimento", "sintetico")}},
        "juiz": {"rubrica": juiz.versao_rubrica(), "usado": usar_juiz, "adotado": juiz.adotado(),
                 "validacao": json.loads(juiz.RESULTADO.read_text(encoding="utf-8"))
                 if juiz.RESULTADO.exists() else None},
        "modelo": config.MODELO,
        "por_classe": {k: round(100 * sum(v) / len(v), 1) for k, v in sorted(por_classe.items())},
        "media": round(100 * sum(d["passou"] for d in detalhes) / len(detalhes), 1) if detalhes else 0.0,
        "casos": detalhes,
    }
    (pasta / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRODADA {pasta.name}: média {resultado['media']}% · {resultado['por_classe']}")
    for d in detalhes:
        if not d["passou"]:
            falhas = [k["nome"] for k in d["checagens"] if not k["ok"] and k.get("conta_na_nota", True)]
            print(f"  FALHOU {d['id']}: {falhas}")
    print(f"gravado em {pasta.relative_to(config.ROOT)}")
    return pasta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--versao", required=True)
    p.add_argument("--casos", default="")
    p.add_argument("--sem-juiz", action="store_true")
    a = p.parse_args()
    rodar(a.versao, [x for x in a.casos.split(",") if x] or None, not a.sem_juiz)


if __name__ == "__main__":
    main()

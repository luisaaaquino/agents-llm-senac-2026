"""
Métricas de operação lidas dos traces, com corte por versão do sistema.

    python -m evals.metricas evals/resultados/<rodada-A> evals/resultados/<rodada-B>
    python -m evals.metricas evals/resultados/*            # todas as rodadas

Unidades:
  execução  = um span raiz `invoke_agent` (um turno da conversa, ou uma
              retomada depois de uma decisão humana)
  conversa  = todas as execuções com o mesmo gen_ai.conversation.id (um caso
              do dataset)

Saída: latência p50 e p95, custo por execução e por conversa, distribuição
dos motivos de término, taxa de erro por ferramenta e o SLO de qualidade
(docs/observabilidade.md §4).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

TERMINOS_RUINS = {"orcamento", "laco", "erro_fatal"}
SLO_ALVO = 0.95


def _pct(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    v = sorted(valores)
    k = (len(v) - 1) * p
    i, f = int(k), k - int(k)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * f


def _spans(pastas: list[str]) -> list[dict]:
    out = []
    for pasta in pastas:
        arq = Path(pasta) / "traces.jsonl"
        if arq.exists():
            out += [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    return out


def calcular(spans: list[dict]) -> dict[str, dict]:
    por_versao: dict[str, list[dict]] = defaultdict(list)
    for s in spans:
        por_versao[s["versao_sistema"]].append(s)
    resultado = {}
    for versao, ss in sorted(por_versao.items()):
        # a reexecução de `publicar` do caso 06 (prova de idempotência) roda fora
        # de conversar(), sem raiz; ela não conta como execução
        raizes = [s for s in ss if s["parent_id"] is None and s["nome"].startswith("invoke_agent")]
        custo_trace: dict[str, float] = defaultdict(float)
        for s in ss:
            if s["atributos"].get("gen_ai.operation.name") == "chat":
                custo_trace[s["trace_id"]] += s["atributos"].get("santo.custo_usd", 0.0)
        lat = [r["duracao_ms"] / 1000 for r in raizes]
        custos = [custo_trace[r["trace_id"]] for r in raizes]
        conversas: dict[str, list[dict]] = defaultdict(list)
        for r in raizes:
            conversas[r["atributos"].get("gen_ai.conversation.id")].append(r)
        lat_conv = [sum(r["duracao_ms"] for r in rs) / 1000 for rs in conversas.values()]
        custo_conv = [sum(custo_trace[r["trace_id"]] for r in rs) for rs in conversas.values()]
        terminos = Counter(r["atributos"].get("santo.termino", "sem_termino") for r in raizes)
        finais = Counter(max(rs, key=lambda r: r["inicio"])["atributos"].get("santo.termino", "sem_termino")
                         for rs in conversas.values())
        ferr: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for s in ss:
            if s["atributos"].get("gen_ai.operation.name") == "execute_tool":
                nome = s["atributos"]["gen_ai.tool.name"]
                ferr[nome][0] += 1
                ferr[nome][1] += s["status"] == "ERROR"
        chats = [s for s in ss if s["atributos"].get("gen_ai.operation.name") == "chat"]
        ruins = sum(n for t, n in terminos.items() if t in TERMINOS_RUINS)
        validas = len(raizes)
        sli = (validas - ruins) / validas if validas else 0.0
        orcamento_erro = validas * (1 - SLO_ALVO)
        resultado[versao] = {
            "execucoes": len(raizes), "conversas": len(conversas),
            "latencia_execucao_s": {"p50": round(_pct(lat, .5), 1), "p95": round(_pct(lat, .95), 1)},
            "latencia_conversa_s": {"p50": round(_pct(lat_conv, .5), 1), "p95": round(_pct(lat_conv, .95), 1)},
            "custo_usd": {"por_execucao_media": round(sum(custos) / len(custos), 5) if custos else 0,
                          "por_execucao_p95": round(_pct(custos, .95), 5),
                          "por_conversa_media": round(sum(custo_conv) / len(custo_conv), 5) if custo_conv else 0,
                          "total": round(sum(custos), 4)},
            "chamadas_modelo": len(chats),
            "chamadas_modelo_com_erro": sum(s["status"] == "ERROR" for s in chats),
            "chamadas_modelo_com_nova_tentativa": sum(s["atributos"].get("santo.tentativas", 1) > 1 for s in chats),
            "terminos_por_execucao": dict(terminos.most_common()),
            "terminos_finais_por_conversa": dict(finais.most_common()),
            "erro_por_ferramenta": {n: {"chamadas": c, "erros": e, "taxa": round(e / c, 3)}
                                    for n, (c, e) in sorted(ferr.items())},
            "slo_qualidade": {"sli": round(sli, 3), "alvo": SLO_ALVO, "boas": validas - ruins,
                              "validas": validas, "ruins": ruins,
                              "orcamento_de_erro_execucoes": round(orcamento_erro, 1),
                              "orcamento_consumido": round(ruins / orcamento_erro, 2) if orcamento_erro else None,
                              "cumprido": sli >= SLO_ALVO},
        }
    return resultado


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(json.dumps(calcular(_spans(sys.argv[1:])), ensure_ascii=False, indent=2))

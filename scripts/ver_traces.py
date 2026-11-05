"""
Mostra os traces gravados em JSONL como árvore de spans.

    python scripts/ver_traces.py                                  # últimos 5 traces de logs/traces/traces.jsonl
    python scripts/ver_traces.py evals/resultados/<rodada>/traces.jsonl
    python scripts/ver_traces.py <arquivo> --conversa V-017:01_simples   # só uma conversa
    python scripts/ver_traces.py <arquivo> --trace <trace_id> --atributos  # um trace, com todos os atributos
    python scripts/ver_traces.py <arquivo> --n 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402

RAIZ_ATTRS = ("santo.versao_sistema", "santo.termino", "santo.motivo_termino", "santo.agente",
              "santo.entrada.texto", "santo.humano.quem", "santo.humano.resposta")


def _linha(s: dict, nivel: int, atributos: bool) -> list[str]:
    a = s["atributos"]
    resumo = []
    if a.get("gen_ai.operation.name") == "chat":
        resumo = [a.get("santo.etapa", ""), f"tokens {a.get('gen_ai.usage.input_tokens', 0)}+"
                  f"{a.get('gen_ai.usage.output_tokens', 0)}"]
    elif a.get("gen_ai.operation.name") == "execute_tool":
        resumo = [str(a.get("gen_ai.tool.call.arguments", ""))[:90]]
    status = " ERRO " + str(a.get("error.type", "")) if s["status"] == "ERROR" else ""
    out = [f"{'  ' * nivel}{s['nome']}  {s['duracao_ms']:.0f} ms{status}  " + "  ".join(r for r in resumo if r)]
    if nivel == 0:
        out += [f"    {k} = {str(a[k])[:140]}" for k in RAIZ_ATTRS if k in a]
    if atributos:
        out += [f"{'  ' * nivel}    · {k} = {str(v)[:300]}" for k, v in a.items()]
    return out


def mostrar(spans: list[dict], atributos: bool) -> None:
    filhos: dict[str | None, list[dict]] = {}
    for s in spans:
        filhos.setdefault(s["parent_id"], []).append(s)

    def andar(s: dict, nivel: int) -> None:
        print("\n".join(_linha(s, nivel, atributos)))
        for f in sorted(filhos.get(s["span_id"], []), key=lambda x: x["inicio"]):
            andar(f, nivel + 1)

    for raiz in sorted(filhos.get(None, []), key=lambda x: x["inicio"]):
        print(f"\ntrace {raiz['trace_id']}  conversa {raiz['atributos'].get('gen_ai.conversation.id')}")
        andar(raiz, 0)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", nargs="?", default=str(config.TRACES_PATH))
    p.add_argument("--conversa")
    p.add_argument("--trace")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--atributos", action="store_true")
    a = p.parse_args()
    spans = [json.loads(l) for l in Path(a.arquivo).read_text(encoding="utf-8").splitlines() if l.strip()]
    raizes = [s for s in spans if s["parent_id"] is None]
    if a.conversa:
        raizes = [s for s in raizes if s["atributos"].get("gen_ai.conversation.id") == a.conversa]
    if a.trace:
        raizes = [s for s in raizes if s["trace_id"] == a.trace]
    ids = {s["trace_id"] for s in (raizes if (a.conversa or a.trace) else raizes[-a.n:])}
    mostrar([s for s in spans if s["trace_id"] in ids], a.atributos)


if __name__ == "__main__":
    main()

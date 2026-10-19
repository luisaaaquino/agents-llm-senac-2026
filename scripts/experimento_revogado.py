"""
Testa o documento revogado. O FAQ antigo (dados/corpus/faq-site-2025.md,
`vigente: false`) responde duas perguntas do conjunto de um jeito que não
vale mais (60 dias; "aceito trocas"). Roda a resposta completa (busca +
modelo) sem curadoria (o revogado entra na busca) e com curadoria.

    python scripts/experimento_revogado.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, llm, rag  # noqa: E402
from src.esquemas import RespostaRegras  # noqa: E402

PERGUNTAS = ["por quanto tempo meu anuncio fica no ar?", "posso aceitar troca em vez de dinheiro?"]


def responder(pergunta: str, incluir_revogados: bool, k: int | None = None) -> dict:
    b = rag.buscar(pergunta, k=k, incluir_revogados=incluir_revogados)
    ctx = json.dumps([{"id": t["id"], "secao": t["secao"], "texto": t["texto"]} for t in b["trechos"]],
                     ensure_ascii=False)
    r, _ = llm.chamada_estruturada(llm.carregar_prompt("resposta-regras-v1.md"),
                                   f"PERGUNTA: {pergunta}\n\nTRECHOS:\n{ctx}", RespostaRegras, max_tokens=400)
    return {"recuperados": [(t["id"], t["similaridade"], "revogado" if not t["vigente"] else "vigente")
                            for t in b["trechos"]],
            "resposta": r.resposta, "citacoes": r.citacoes,
            "citou_revogado": any(c.startswith("faq-site-2025") for c in r.citacoes)}


def main() -> None:
    # k=1 sem curadoria: só o primeiro trecho entra no contexto, e nas duas
    # perguntas o primeiro é o documento revogado.
    linhas = [{"pergunta": p, "sem_curadoria": responder(p, True), "com_curadoria": responder(p, False),
               "sem_curadoria_k1": responder(p, True, k=1)} for p in PERGUNTAS]
    destino = config.LOGS_DIR / "medicoes" / "rag_revogado.json"
    destino.write_text(json.dumps({"data": datetime.now().isoformat(timespec="seconds"),
                                   "modelo": config.MODELO, "casos": linhas},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    for l in linhas:
        print(f"\n? {l['pergunta']}")
        for k in ("sem_curadoria", "com_curadoria", "sem_curadoria_k1"):
            print(f"  [{k}] citou_revogado={l[k]['citou_revogado']} · {l[k]['resposta']}")
    print(f"\nlog: {destino.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

"""
Mede a busca contra o conjunto de perguntas com resposta conhecida
(dados/perguntas_rag.json). Os valores de k e do limiar vêm daqui.

    python scripts/medir_rag.py            # mede só com documentos vigentes
    python scripts/medir_rag.py --revogado # mede também com o revogado no índice
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, rag  # noqa: E402


def medir(incluir_revogados: bool) -> list[dict]:
    perguntas = json.loads((config.DADOS_DIR / "perguntas_rag.json").read_text(encoding="utf-8"))
    linhas = []
    for p in perguntas:
        r = rag.buscar(p["pergunta"], k=5, incluir_revogados=incluir_revogados)
        ids = [t["id"] for t in r["trechos"]]
        esperado = set(p["esperado"])
        linha = {
            "id": p["id"], "forma": p["forma"], "excecao": p["excecao"],
            "top": [(t["id"], t["similaridade"]) for t in r["trechos"][:3]],
            "melhor_sim": r["melhor_similaridade"],
            "acerto@1": bool(esperado) and ids[0] in esperado,
            "acerto@3": bool(esperado) and bool(esperado & set(ids[:3])),
            "posicao_esperado": next((i + 1 for i, x in enumerate(ids) if x in esperado), None),
        }
        if incluir_revogados and p.get("revogado_concorrente"):
            linha["posicao_revogado"] = next(
                (i + 1 for i, x in enumerate(ids) if x == p["revogado_concorrente"]), None)
        linhas.append(linha)
    return linhas


def main() -> None:
    if not config.INDICE_DB_PATH.exists():
        print("indexando:", rag.indexar())
    saida = {"data": datetime.now().isoformat(timespec="seconds"),
             "modelo_embedding": config.MODELO_EMBEDDING, "dimensoes": config.EMBEDDING_DIMENSOES,
             "curado": medir(incluir_revogados=False)}
    if "--revogado" in sys.argv:
        saida["com_revogado"] = medir(incluir_revogados=True)
    destino = config.LOGS_DIR / "medicoes" / "rag_buscador.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    for chave in [c for c in ("curado", "com_revogado") if c in saida]:
        print(f"\n== {chave} ==")
        for l in saida[chave]:
            extra = f" revogado@{l.get('posicao_revogado')}" if "posicao_revogado" in l else ""
            print(f"{l['id']} {l['forma']:<14} sim={l['melhor_sim']:.3f} "
                  f"@1={'S' if l['acerto@1'] else '-'} @3={'S' if l['acerto@3'] else '-'} "
                  f"pos={l['posicao_esperado']}{extra}  top1={l['top'][0][0]}")
    print(f"\nlog: {destino.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

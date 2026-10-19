"""
Mostra o que acontece sem reducer. Monta o grafo com o mesmo construtor
do sistema (src/grafo.construir), trocando só o tipo do estado, e roda a
mesma entrada do caso 07 (Agente A).

  1. `candidatos` sem reducer: os 4 ramos paralelos (Send) escrevem no
     campo ao mesmo tempo.
  2. `passos` sem a soma: cada nó que chama o modelo devolve 1. Sem a
     soma, fica só o valor do último nó, e o limite de passos nunca é
     atingido.

    python scripts/demo_sem_reducer.py
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from src import config, db  # noqa: E402
from src.casos import CASOS  # noqa: E402
from src.estado import Estado  # noqa: E402
from src.grafo import construir, estado_sem_reducer_em  # noqa: E402

CASO = CASOS["07_compra_cozinha"]


def rodar(estado_tipo: type, rotulo: str) -> dict:
    grafo = construir(estado_tipo, checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": f"demo:{rotulo}"}, "recursion_limit": config.RECURSION_LIMIT}
    entrada = {"texto_turno": CASO.primeira_fala, "thread_id": f"demo:{rotulo}",
               "usuario_id": CASO.usuario_id, "sessao_id": rotulo}
    try:
        final = grafo.invoke(entrada, cfg)
        ramos = [p for p in final["trajetoria"] if p["etapa"] == "buscar_categoria"]
        chamadas = [p for p in final["trajetoria"] if p.get("decide") == "modelo"]
        return {"rotulo": rotulo, "erro": None,
                "ramos_paralelos": len(ramos),
                "categorias_nos_candidatos": sorted({c["categoria"] for c in final.get("candidatos", [])}),
                "candidatos": len(final.get("candidatos", [])),
                "chamadas_de_modelo_na_trajetoria": len(chamadas),
                "campo_passos": final.get("passos"),
                "itens_sugeridos": [i["titulo"] for i in (final.get("sugestao") or {}).get("itens", [])]}
    except Exception as erro:  # noqa: BLE001 (o erro é o que queremos mostrar)
        return {"rotulo": rotulo, "erro": f"{type(erro).__name__}: {erro}".split("\n")[0][:300],
                "onde": traceback.extract_tb(erro.__traceback__)[-1].name}


def main() -> None:
    db.inicializar()
    resultados = [rodar(Estado, "com_reducers"),
                  rodar(estado_sem_reducer_em("candidatos"), "candidatos_sem_reducer"),
                  rodar(estado_sem_reducer_em("passos"), "passos_sem_reducer")]
    destino = config.LOGS_DIR / "medicoes" / "demo_sem_reducer.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"data": datetime.now().isoformat(timespec="seconds"),
                                   "entrada": CASO.primeira_fala, "resultados": resultados},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    for r in resultados:
        print(json.dumps(r, ensure_ascii=False))
    print(f"log: {destino.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

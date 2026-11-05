"""
O juiz: um modelo que julga UMA propriedade sem gabarito, com rubrica escrita
(evals/juiz/rubrica.md) e saída binária.

Propriedade: o anúncio publicado não afirma nada sobre o produto que o
vendedor não disse na conversa (sem_invencao).

    python -m evals.juiz preparar    # junta 20 anúncios publicados das rodadas e julga cada um
                                     # -> evals/juiz/validacao.csv (com colunas para o rótulo humano)
    python -m evals.juiz validar     # lê os rótulos humanos e calcula a matriz de concordância
                                     # -> evals/juiz/validacao_resultado.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from src import config, llm

PASTA = Path(__file__).resolve().parent / "juiz"
RUBRICA = PASTA / "rubrica.md"
CSV = PASTA / "validacao.csv"
RESULTADO = PASTA / "validacao_resultado.json"
RESULTADOS_DIR = Path(__file__).resolve().parent / "resultados"
LIMIAR_ADOCAO = 0.85   # declarado antes de medir (docs/evals.md)


class Veredito(BaseModel):
    sem_invencao: bool = Field(description="true se tudo o que o anúncio afirma sobre o produto foi dito pelo vendedor")
    afirmacao_inventada: str | None = Field(default=None, description="a afirmação sem base, se houver")
    justificativa: str


def versao_rubrica() -> str:
    achou = re.search(r"v(\d+\.\d+\.\d+)", RUBRICA.read_text(encoding="utf-8").splitlines()[0])
    return achou.group(1) if achou else "?"


def julgar(falas_vendedor: list[str], anuncio: dict) -> Veredito:
    rubrica = RUBRICA.read_text(encoding="utf-8")
    entrada = json.dumps({"falas_do_vendedor": falas_vendedor,
                          "anuncio_publicado": {k: anuncio.get(k) for k in
                                                ("titulo", "descricao", "estado_conservacao", "preco")}},
                         ensure_ascii=False, indent=1)
    veredito, _ = llm.chamada_estruturada(rubrica, entrada, Veredito, modelo=config.MODELO_AVALIADOR,
                                          max_tokens=300, etapa="juiz_sem_invencao", prompt="evals/juiz/rubrica.md")
    return veredito


def adotado() -> bool:
    if not RESULTADO.exists():
        return False
    return json.loads(RESULTADO.read_text(encoding="utf-8")).get("adotado", False)


def _amostras() -> list[dict]:
    """Os anúncios publicados nos logs das rodadas, com as falas do vendedor."""
    vistos, out = set(), []
    for log_path in sorted(RESULTADOS_DIR.glob("*/logs/*.json")):
        log = json.loads(log_path.read_text(encoding="utf-8"))
        final = log["turnos"][-1]["saida"] if log["turnos"] else {}
        anuncio = (final.get("dados") or {}).get("anuncio")
        if final.get("tipo") != "anuncio_publicado" or not anuncio:
            continue
        falas = [t["enviado"] for t in log["turnos"] if t["tipo"] == "fala"]
        chave = (anuncio.get("titulo"), anuncio.get("descricao"))
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append({"origem": f"{log_path.parent.parent.name}/{log_path.stem}", "falas": falas, "anuncio": anuncio})
    return out


def preparar(n: int = 20) -> None:
    amostras = _amostras()[:n]
    PASTA.mkdir(exist_ok=True)
    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "origem", "falas_do_vendedor", "titulo", "descricao", "estado_conservacao",
                    "juiz_sem_invencao", "juiz_justificativa",
                    "humano_sem_invencao", "humano_nota", "rotulado_por"])
        for i, a in enumerate(amostras, 1):
            v = julgar(a["falas"], a["anuncio"])
            w.writerow([i, a["origem"], " | ".join(a["falas"]), a["anuncio"].get("titulo"),
                        a["anuncio"].get("descricao"), a["anuncio"].get("estado_conservacao"),
                        v.sem_invencao, v.justificativa, "", "", ""])
            print(i, a["origem"], v.sem_invencao, v.justificativa[:100])
    print(f"{len(amostras)} saídas em {CSV.relative_to(config.ROOT)}; preencha humano_sem_invencao, humano_nota e rotulado_por")


def validar() -> None:
    linhas = list(csv.DictReader(CSV.open(encoding="utf-8")))
    rotuladas = [l for l in linhas if l["humano_sem_invencao"].strip().lower() in ("true", "false")]
    m = {"juiz_true_humano_true": 0, "juiz_true_humano_false": 0,
         "juiz_false_humano_true": 0, "juiz_false_humano_false": 0}
    desacordos = []
    for l in rotuladas:
        j, h = l["juiz_sem_invencao"].lower() == "true", l["humano_sem_invencao"].lower() == "true"
        m[f"juiz_{str(j).lower()}_humano_{str(h).lower()}"] += 1
        if j != h:
            desacordos.append({"id": l["id"], "origem": l["origem"], "juiz": j, "humano": h,
                               "nota_humana": l["humano_nota"], "justificativa_juiz": l["juiz_justificativa"]})
    n = len(rotuladas)
    concordancia = (m["juiz_true_humano_true"] + m["juiz_false_humano_false"]) / n if n else 0.0
    rotuladores = sorted({l["rotulado_por"] for l in rotuladas})
    resultado = {"rubrica": versao_rubrica(), "n_rotuladas": n, "limiar": LIMIAR_ADOCAO,
                 "concordancia": round(concordancia, 3), "matriz": m,
                 "adotado": n >= 20 and concordancia >= LIMIAR_ADOCAO,
                 "rotulado_por": rotuladores, "desacordos": desacordos}
    RESULTADO.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    {"preparar": preparar, "validar": validar}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()

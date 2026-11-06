"""
Compara duas rodadas da avaliação, classe por classe.

    python -m evals.comparar evals/resultados/<rodada-A> evals/resultados/<rodada-B>

Também lista os casos que mudaram de resultado entre as duas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _ler(pasta: str) -> dict:
    return json.loads((Path(pasta) / "resultado.json").read_text(encoding="utf-8"))


def comparar(a: dict, b: dict) -> str:
    ds = b["dataset"]
    o = ds["por_origem"]
    linhas = [f"DATASET v{ds['versao']}   {ds['n']} casos   "
              f"(producao {o['producao']} · desenvolvimento {o['desenvolvimento']} · sintetico {o['sintetico']})"]
    # a validação do juiz pode ser posterior à rodada: vale a mais recente
    atual = Path(__file__).resolve().parent / "juiz" / "validacao_resultado.json"
    v = json.loads(atual.read_text(encoding="utf-8")) if atual.exists() else b["juiz"].get("validacao")
    if v:
        situacao = "adotado" if v["adotado"] else (
            "NÃO adotado: rótulos ainda só sugeridos" if v.get("rotulos_so_sugeridos") else "NÃO adotado")
        linhas.append(f"JUIZ rubrica v{v['rubrica']}   concordância {100 * v['concordancia']:.0f}%   "
                      f"limiar {100 * v['limiar']:.0f}%   {situacao}")
    else:
        linhas.append(f"JUIZ rubrica v{b['juiz']['rubrica']}   sem validação: não conta na nota")
    linhas.append("")
    va, vb = f"v{a['versao_sistema']}", f"v{b['versao_sistema']}"
    linhas.append(f"{'classe':<18}{va:>10}{vb:>10}{'delta':>9}")
    for classe in sorted(set(a["por_classe"]) | set(b["por_classe"])):
        x, y = a["por_classe"].get(classe), b["por_classe"].get(classe)
        delta = f"{y - x:+.0f}" if x is not None and y is not None else "-"
        linhas.append(f"{classe:<18}{x if x is not None else '-':>9}%{y if y is not None else '-':>9}%{delta:>9}")
    linhas.append(f"{'MÉDIA':<18}{a['media']:>9}%{b['media']:>9}%{b['media'] - a['media']:>+9.0f}")
    linhas.append("")
    pa = {c["id"]: c["passou"] for c in a["casos"]}
    for c in b["casos"]:
        if c["id"] in pa and pa[c["id"]] != c["passou"]:
            linhas.append(f"  {c['id']:<36} {'passou' if pa[c['id']] else 'falhou'} -> "
                          f"{'passou' if c['passou'] else 'falhou'}")
    linhas.append(f"\nA: {a['versao_sistema']} commit {a['commit']} ({a['data']})"
                  f"\nB: {b['versao_sistema']} commit {b['commit']} ({b['data']})")
    return "\n".join(linhas)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(comparar(_ler(sys.argv[1]), _ler(sys.argv[2])))

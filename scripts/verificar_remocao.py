"""
Varredura INDEPENDENTE da remoção (docs/memoria.md §2.3, passo 3).

Não importa src/remocao.py nem src/memoria.py: abre cada arquivo do sistema
e procura o identificador por dois critérios — nas colunas de texto de TODAS
as tabelas de TODOS os bancos SQLite (inclusive os blobs dos checkpoints,
como bytes), e no texto dos logs e dos prompts.

    python scripts/verificar_remocao.py V-TESTE
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def varrer_sqlite(caminho: Path, alvo: str) -> list[str]:
    achados = []
    with sqlite3.connect(caminho) as con:
        tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tabelas:
            colunas = [r[1] for r in con.execute(f"PRAGMA table_info('{t}')")]
            for linha in con.execute(f"SELECT * FROM '{t}'"):
                for col, valor in zip(colunas, linha):
                    texto = valor.decode("utf-8", "ignore") if isinstance(valor, bytes) else str(valor)
                    if alvo in texto:
                        achados.append(f"{caminho.name}:{t}.{col}")
    return sorted(set(achados))


def main() -> None:
    alvo = sys.argv[1] if len(sys.argv) > 1 else "V-TESTE"
    achados: list[str] = []
    for banco in sorted((RAIZ / "dados").glob("*.db")):
        achados += varrer_sqlite(banco, alvo)
    for pasta, padrao in (("logs", "**/*.json"), ("src/prompts", "*.md")):
        for arq in sorted((RAIZ / pasta).glob(padrao)):
            if alvo in arq.read_text(encoding="utf-8", errors="ignore"):
                achados.append(str(arq.relative_to(RAIZ)))
    estruturas = [p.name for p in sorted((RAIZ / "dados").glob("*.db"))] + ["logs/", "src/prompts/"]
    if achados:
        print(f"FALHOU — vestígios de {alvo}:")
        for a in achados:
            print("  ", a)
        sys.exit(1)
    print(f"OK — nenhum vestígio de {alvo} em {len(estruturas)} lugares: {', '.join(estruturas)}")


if __name__ == "__main__":
    main()

"""
Busca nas regras do Santo Desapego (RAG).

- Busca vetorial sobre os documentos de dados/corpus/*.md. Perguntas sobre
  registros (preço de mercado, catálogo, bairros) não passam por aqui: são
  consultas SQL em src/db.py.
- Corte por seção: cada "##" vira um trecho, assim a regra e a exceção
  dela ficam no mesmo trecho.
- Devolve os k trechos mais próximos (config.RAG_K). Se a maior similaridade
  ficar abaixo de config.RAG_LIMIAR, considera que não há base.
- Documento com `vigente: false` continua no índice, mas fica fora da busca.
  `incluir_revogados=True` só é usado no experimento do documento revogado.

O índice é SQLite + numpy (similaridade de cosseno). Com poucas dezenas de
trechos, a busca leva menos de 1 ms.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import config, llm


@dataclass
class Trecho:
    id: str            # formato "<doc_id>#<n>", que é o id citado na resposta
    doc_id: str
    titulo_doc: str
    secao: str
    texto: str
    vigente: bool
    versao: str


def _ler_cabecalho(texto: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    if not m:
        return {}, texto
    meta = {}
    for linha in m.group(1).splitlines():
        if ":" in linha:
            chave, valor = linha.split(":", 1)
            meta[chave.strip()] = valor.strip().strip('"')
    return meta, m.group(2)


def cortar_documento(caminho: Path) -> list[Trecho]:
    meta, corpo = _ler_cabecalho(caminho.read_text(encoding="utf-8"))
    doc_id = meta.get("id", caminho.stem)
    vigente = meta.get("vigente", "true").lower() == "true"
    trechos = []
    for n, bloco in enumerate(re.split(r"\n## ", "\n" + corpo)[1:], start=1):
        secao, _, texto = bloco.partition("\n")
        texto = " ".join(texto.split())
        if texto:
            trechos.append(Trecho(id=f"{doc_id}#{n}", doc_id=doc_id,
                                  titulo_doc=meta.get("titulo", doc_id), secao=secao.strip(),
                                  texto=texto, vigente=vigente, versao=meta.get("versao", "")))
    return trechos


def _conectar() -> sqlite3.Connection:
    con = sqlite3.connect(config.INDICE_DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def indexar(diretorio: Path | None = None) -> dict[str, Any]:
    """Reconstrói o índice inteiro (o corpus muda pouco)."""
    diretorio = diretorio or config.CORPUS_DIR
    trechos = [t for arq in sorted(diretorio.glob("*.md")) for t in cortar_documento(arq)]
    vetores = llm.embeddings([f"{t.titulo_doc} — {t.secao}\n{t.texto}" for t in trechos])
    if config.INDICE_DB_PATH.exists():
        config.INDICE_DB_PATH.unlink()
    with closing(_conectar()) as con:
        con.execute("CREATE TABLE trechos (id TEXT PRIMARY KEY, doc_id TEXT, titulo_doc TEXT, "
                    "secao TEXT, texto TEXT, vigente INTEGER, versao TEXT, vetor BLOB)")
        con.executemany("INSERT INTO trechos VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            (t.id, t.doc_id, t.titulo_doc, t.secao, t.texto, int(t.vigente), t.versao,
             np.asarray(v, dtype=np.float32).tobytes()) for t, v in zip(trechos, vetores)])
        con.commit()
    return {"trechos": len(trechos), "documentos": len({t.doc_id for t in trechos}),
            "revogados": sum(not t.vigente for t in trechos)}


def _carregar(incluir_revogados: bool) -> tuple[list[dict[str, Any]], np.ndarray]:
    if not config.INDICE_DB_PATH.exists():
        raise FileNotFoundError("índice do RAG não existe: rode `python cli.py indexar`")
    with closing(_conectar()) as con:
        linhas = [dict(r) for r in con.execute(
            "SELECT * FROM trechos" + ("" if incluir_revogados else " WHERE vigente = 1"))]
    matriz = np.stack([np.frombuffer(r.pop("vetor"), dtype=np.float32) for r in linhas])
    return linhas, matriz / np.linalg.norm(matriz, axis=1, keepdims=True)


def buscar(pergunta: str, k: int | None = None, incluir_revogados: bool = False) -> dict[str, Any]:
    """Recupera os k trechos mais próximos e aplica o portão de suficiência."""
    k = k or config.RAG_K
    linhas, matriz = _carregar(incluir_revogados)
    q = np.asarray(llm.embeddings([pergunta])[0], dtype=np.float32)
    sims = matriz @ (q / np.linalg.norm(q))
    ordem = np.argsort(-sims)[:k]
    recuperados = [{"id": linhas[i]["id"], "secao": linhas[i]["secao"],
                    "doc": linhas[i]["titulo_doc"], "vigente": bool(linhas[i]["vigente"]),
                    "texto": linhas[i]["texto"], "similaridade": round(float(sims[i]), 4)}
                   for i in ordem]
    melhor = recuperados[0]["similaridade"] if recuperados else 0.0
    return {"pergunta": pergunta, "trechos": recuperados, "melhor_similaridade": melhor,
            "suficiente": melhor >= config.RAG_LIMIAR, "limiar": config.RAG_LIMIAR, "k": k}


def verificar_citacoes(citadas: list[str], recuperados: list[dict[str, Any]]) -> dict[str, Any]:
    """Confere a citação: só vale um id que foi de fato recuperado."""
    ids = {t["id"] for t in recuperados}
    validas = [c for c in citadas if c in ids]
    return {"validas": validas, "invalidas": [c for c in citadas if c not in ids]}


if __name__ == "__main__":  # inspeção rápida do corte, sem chamar o modelo
    for arq in sorted(config.CORPUS_DIR.glob("*.md")):
        for t in cortar_documento(arq):
            print(json.dumps({"id": t.id, "secao": t.secao, "vigente": t.vigente,
                              "palavras": len(t.texto.split())}, ensure_ascii=False))

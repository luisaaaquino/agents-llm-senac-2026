"""
Memória de longo prazo do Agente B.

  episódica  -> índice por similaridade (SQLite + numpy), com data,
                categoria, bairro, vendedor_id, desfecho e avaria
  semântica  -> chave-valor (entidade, chave, condição) -> valor; o valor
                antigo fica guardado em `substituiu`
  procedural -> texto em src/prompts/procedural.md, anexado ao system
                prompt; regras novas só entram depois de um humano aprovar

Quem escreve: o código grava a semântica por regra, gera a episódica com
uma chamada de modelo a partir de campos estruturados, e a procedural
depende de aprovação humana. O agente nunca escreve memória diretamente.
Toda escrita tem chave derivada do conteúdo e devolve `ja_existia`.

O Agente A não usa memória de longo prazo.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from . import config, llm

DECAIMENTO_REBAIXA_DIAS = 180   # idade em dias a partir da qual o dado é rebaixado
DECAIMENTO_REMOVE_DIAS = 365
FATOR_REBAIXADO = 0.5           # multiplica a similaridade de episódio rebaixado
PROCEDURAL_PATH = config.PROMPTS_DIR / "procedural.md"

# Remove dados pessoais antes de qualquer gravação.
_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[cep]"),
    (re.compile(r"(\(?\d{2}\)?\s?)?9?\d{4}[-\s]?\d{4}\b"), "[telefone]"),
]


def filtrar_pii(texto: str) -> str:
    for padrao, marca in _PII:
        texto = padrao.sub(marca, texto)
    return texto


def _conectar() -> sqlite3.Connection:
    con = sqlite3.connect(config.MEMORIA_DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS memoria_semantica (
            entidade TEXT NOT NULL, chave TEXT NOT NULL, condicao TEXT NOT NULL DEFAULT '',
            valor TEXT NOT NULL, data TEXT NOT NULL, fonte TEXT NOT NULL,
            substituiu TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (entidade, chave, condicao));
        CREATE TABLE IF NOT EXISTS memoria_episodica (
            id TEXT PRIMARY KEY, vendedor_id TEXT NOT NULL, categoria TEXT NOT NULL,
            bairro TEXT, desfecho TEXT NOT NULL, avaria TEXT NOT NULL, data TEXT NOT NULL,
            resumo TEXT NOT NULL, vetor BLOB NOT NULL, rebaixado INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS regras_candidatas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE NOT NULL, regra TEXT NOT NULL,
            motivo TEXT NOT NULL, origem_thread TEXT, status TEXT NOT NULL DEFAULT 'pendente',
            criada_em TEXT NOT NULL);
    """)
    return con


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash(*partes: Any) -> str:
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:24]


# --- Semântica (chave-valor) -------------------------------------------------
def gravar_fato(entidade: str, chave: str, valor: Any, fonte: str,
                condicao: str = "", data: str | None = None) -> dict[str, Any]:
    """Grava ou atualiza um fato. Se o valor mudou, o novo substitui o antigo,
    que fica guardado em `substituiu`."""
    data = data or _agora()
    valor_json = json.dumps(valor, ensure_ascii=False)
    with closing(_conectar()) as con:
        atual = con.execute("SELECT * FROM memoria_semantica WHERE entidade=? AND chave=? AND condicao=?",
                            (entidade, chave, condicao)).fetchone()
        if atual and atual["valor"] == valor_json:
            return {"ok": True, "ja_existia": True, "entidade": entidade, "chave": chave}
        historico = json.loads(atual["substituiu"]) if atual else []
        if atual:
            historico.append({"valor": json.loads(atual["valor"]), "data": atual["data"],
                              "fonte": atual["fonte"]})
        con.execute("INSERT OR REPLACE INTO memoria_semantica VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (entidade, chave, condicao, valor_json, data, fonte,
                     json.dumps(historico, ensure_ascii=False)))
        con.commit()
    return {"ok": True, "ja_existia": False, "entidade": entidade, "chave": chave,
            "substituiu": historico[-1] if historico else None}


def ler_fatos(entidade: str) -> list[dict[str, Any]]:
    """Lê os fatos pela chave, sem chamar o modelo. Fato de vendedor sem
    confirmação há mais de 180 dias volta marcado como `a_confirmar`."""
    limite = datetime.now() - timedelta(days=DECAIMENTO_REBAIXA_DIAS)
    with closing(_conectar()) as con:
        linhas = con.execute("SELECT * FROM memoria_semantica WHERE entidade=?", (entidade,)).fetchall()
    fatos = []
    for r in linhas:
        fatos.append({"entidade": r["entidade"], "chave": r["chave"], "condicao": r["condicao"],
                      "valor": json.loads(r["valor"]), "data": r["data"], "fonte": r["fonte"],
                      "a_confirmar": entidade.startswith("vendedor:")
                      and datetime.fromisoformat(r["data"]) < limite})
    return fatos


# --- Episódica (índice por similaridade) -------------------------------------
def chave_episodio(vendedor_id: str, origem: str, desfecho: str) -> str:
    """Chave do episódio feita de campos estruturados (vendedor, anúncio ou
    conversa, desfecho), e não do resumo: o resumo gerado pelo modelo muda
    entre execuções e faria o mesmo episódio ser gravado várias vezes."""
    return _hash("episodio", vendedor_id, origem, desfecho)


def episodio_existe(chave: str) -> bool:
    with closing(_conectar()) as con:
        return con.execute("SELECT 1 FROM memoria_episodica WHERE id=?", (chave,)).fetchone() is not None


def gravar_episodio(vendedor_id: str, categoria: str, bairro: str | None, desfecho: str,
                    avaria: str, resumo: str, data: str | None = None,
                    origem: str | None = None) -> dict[str, Any]:
    # A data é sempre gravada pelo código.
    data = data or _agora()
    resumo = filtrar_pii(resumo)
    chave = (chave_episodio(vendedor_id, origem, desfecho) if origem
             else _hash(vendedor_id, categoria, bairro, desfecho, avaria, resumo))
    if episodio_existe(chave):
        return {"ok": True, "ja_existia": True, "episodio_id": chave}
    vetor = np.asarray(llm.embeddings([resumo])[0], dtype=np.float32)
    with closing(_conectar()) as con:
        con.execute("INSERT INTO memoria_episodica VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (chave, vendedor_id, categoria, bairro, desfecho, avaria, data, resumo,
                     vetor.tobytes()))
        con.commit()
    return {"ok": True, "ja_existia": False, "episodio_id": chave, "tokens_resumo": len(resumo) // 4}


def ler_episodios(categoria: str, texto: str, k: int | None = None) -> list[dict[str, Any]]:
    """Filtra pela categoria e depois ordena por similaridade. Episódio
    rebaixado vale metade; em empate, ganha o mais recente."""
    k = k or config.MEMORIA_EPISODICA_K
    with closing(_conectar()) as con:
        linhas = [dict(r) for r in con.execute(
            "SELECT * FROM memoria_episodica WHERE categoria=?", (categoria,))]
    if not linhas:
        return []
    q = np.asarray(llm.embeddings([texto])[0], dtype=np.float32)
    q /= np.linalg.norm(q)
    for r in linhas:
        v = np.frombuffer(r.pop("vetor"), dtype=np.float32)
        r["similaridade"] = round(float(v @ q / np.linalg.norm(v))
                                  * (FATOR_REBAIXADO if r["rebaixado"] else 1.0), 4)
    linhas.sort(key=lambda r: (r["similaridade"], r["data"]), reverse=True)
    return linhas[:k]


# --- Procedural (texto no system prompt; fila com aprovação humana) ----------
def ler_procedural() -> str:
    return llm.carregar_prompt("procedural.md") if PROCEDURAL_PATH.exists() else ""


def propor_regra(regra: str, motivo: str, origem_thread: str | None) -> dict[str, Any]:
    """O código propõe a regra; ela só entra no system prompt depois que um
    humano aprova. A regra é montada a partir de campos estruturados, nunca
    com texto escrito pelo vendedor."""
    chave = _hash(regra)
    with closing(_conectar()) as con:
        if con.execute("SELECT 1 FROM regras_candidatas WHERE chave=?", (chave,)).fetchone():
            return {"ok": True, "ja_existia": True}
        con.execute("INSERT INTO regras_candidatas (chave, regra, motivo, origem_thread, criada_em) "
                    "VALUES (?, ?, ?, ?, ?)", (chave, regra, motivo, origem_thread, _agora()))
        con.commit()
    return {"ok": True, "ja_existia": False}


def regras_candidatas(status: str = "pendente") -> list[dict[str, Any]]:
    with closing(_conectar()) as con:
        return [dict(r) for r in con.execute("SELECT * FROM regras_candidatas WHERE status=?", (status,))]


# --- Rotina de decaimento ----------------------------------------------------
def rotina_decaimento(hoje: datetime | None = None) -> dict[str, int]:
    hoje = hoje or datetime.now()
    rebaixa = (hoje - timedelta(days=DECAIMENTO_REBAIXA_DIAS)).isoformat()
    remove = (hoje - timedelta(days=DECAIMENTO_REMOVE_DIAS)).isoformat()
    with closing(_conectar()) as con:
        removidos = con.execute("DELETE FROM memoria_episodica WHERE data < ?", (remove,)).rowcount
        rebaixados = con.execute("UPDATE memoria_episodica SET rebaixado=1 WHERE data < ? AND rebaixado=0",
                                 (rebaixa,)).rowcount
        con.commit()
    return {"removidos": removidos, "rebaixados": rebaixados}


# --- Resumo da memória para o registro da execução -----------------------------
def snapshot() -> dict[str, Any]:
    with closing(_conectar()) as con:
        n_sem = con.execute("SELECT COUNT(*) FROM memoria_semantica").fetchone()[0]
        ids_ep = [r[0] for r in con.execute("SELECT id FROM memoria_episodica ORDER BY id")]
    proc = PROCEDURAL_PATH.read_text(encoding="utf-8") if PROCEDURAL_PATH.exists() else ""
    return {"semantica_fatos": n_sem, "episodios": len(ids_ep),
            "episodios_hash": _hash(ids_ep)[:12],
            "procedural_hash": hashlib.sha256(proc.encode("utf-8")).hexdigest()[:12]}


def zerar() -> None:
    if config.MEMORIA_DB_PATH.exists():
        config.MEMORIA_DB_PATH.unlink()

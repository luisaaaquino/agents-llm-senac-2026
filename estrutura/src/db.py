"""
Camada de acesso a dados do Agente B (Assistente de anúncio).

Esta é a "integração com software tradicional" exigida pela §4.2 da entrega:
o agente NÃO fala com um dicionário Python no meio do arquivo — ele atravessa
a fronteira do processo e conversa com um SQLite via esta camada separada.
Aqui moram os erros que a §4.2 quer que o agente aprenda a lidar: registro
ausente, dado faltando, formato inesperado.

O banco é criado a partir de `dados/seed.sql`. Tudo é mock e simulado
(nenhum dado real de pessoa entra no repositório — ver §2.9 do case).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "dados" / "santo_desapego.db"
SEED_PATH = ROOT / "dados" / "seed.sql"


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def inicializar() -> None:
    """Cria o banco a partir do seed. Idempotente: recria do zero."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = conectar()
    con.executescript(SEED_PATH.read_text(encoding="utf-8"))
    con.commit()
    con.close()


def consultar_preco_comparaveis(categoria: str, bairro: str) -> dict[str, Any]:
    """
    LEITURA. Faixa de preço de itens semelhantes ativos/vendidos no bairro.
    Retorna erro-como-dado quando não há comparáveis (caso do 'registro
    inexistente' da §4.5): o agente precisa contornar, não quebrar.
    """
    con = conectar()
    linhas = con.execute(
        """
        SELECT preco FROM precos_comparaveis
        WHERE categoria = ? AND bairro = ?
        """,
        (categoria, bairro),
    ).fetchall()
    con.close()

    if not linhas:
        return {
            "erro": "sem_comparaveis",
            "categoria": categoria,
            "bairro": bairro,
            "dica": "não há base de preço para essa categoria/bairro",
        }

    precos = sorted(l["preco"] for l in linhas)
    return {
        "categoria": categoria,
        "bairro": bairro,
        "n": len(precos),
        "faixa_min": precos[0],
        "faixa_max": precos[-1],
    }


def publicar_anuncio(rascunho: dict[str, Any]) -> dict[str, Any]:
    """
    ESCRITA reversível (o vendedor edita/pausa depois — RF12).
    Idempotente: a mesma publicação não gera dois anúncios.
    """
    campos_obrigatorios = ("titulo", "categoria", "descricao", "preco", "bairro")
    faltando = [c for c in campos_obrigatorios if not rascunho.get(c)]
    if faltando:
        return {"erro": "rascunho_incompleto", "faltando": faltando}

    con = conectar()
    existente = con.execute(
        "SELECT id FROM anuncios WHERE titulo = ? AND bairro = ? AND preco = ?",
        (rascunho["titulo"], rascunho["bairro"], rascunho["preco"]),
    ).fetchone()
    if existente:
        con.close()
        return {"ok": True, "ja_existia": True, "anuncio_id": existente["id"],
                "estado": "ativo"}

    cur = con.execute(
        """
        INSERT INTO anuncios (titulo, categoria, descricao, preco, bairro,
                              estado_declarado, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'ativo')
        """,
        (
            rascunho["titulo"], rascunho["categoria"], rascunho["descricao"],
            rascunho["preco"], rascunho["bairro"],
            1 if rascunho.get("estado_declarado") else 0,
        ),
    )
    con.commit()
    anuncio_id = cur.lastrowid
    con.close()
    return {"ok": True, "ja_existia": False, "anuncio_id": anuncio_id,
            "estado": "ativo"}


def registrar_indicio_avaria(anuncio_ref: str, indicio: str) -> dict[str, Any]:
    """
    ESCRITA reversível. Sinaliza à moderação humana (RF20) quando o vendedor
    recusa declarar a avaria. É um REGISTRO — a decisão é humana; o agente
    apenas aconselha e encaminha, não veta a publicação.
    """
    con = conectar()
    cur = con.execute(
        "INSERT INTO indicios_moderacao (anuncio_ref, indicio, status) "
        "VALUES (?, ?, 'pendente')",
        (anuncio_ref, indicio),
    )
    con.commit()
    indicio_id = cur.lastrowid
    con.close()
    return {"ok": True, "indicio_id": indicio_id, "status": "pendente",
            "decisao": "humana"}

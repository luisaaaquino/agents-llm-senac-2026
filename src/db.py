"""
Camada de negócio (SQLite) — as ferramentas que os agentes chamam.

Herdada da Parte 1 (legado/parte1/db.py) e estendida: catálogo para o
Agente A, `vendedor_id` nos anúncios (sem ele a remoção por titular era
impossível — docs/memoria.md §2.3, item 6) e idempotência nas DUAS escritas.

Regra das escritas (§5.3 e §8.5): chave de idempotência DERIVADA DO
CONTEÚDO, com `ja_existia` no retorno. O mesmo conteúdo produz a mesma
chave, e a segunda chamada não cria nada.

Erro de ferramenta é DADO, não exceção: quem chama recebe {"erro": ...} e
decide o que fazer (o modelo contorna; o código registra).
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from typing import Any

from . import config

# Vocabulário fechado de categorias. Na Parte 1 a categoria era a palavra do
# vendedor, e o acento quebrava a busca exata ("sofa" × "sofá"). Agora o
# modelo escolhe de uma lista (Literal no schema) e o código não depende de grafia.
CATEGORIAS = ["geladeira", "fogão", "micro-ondas", "mesa", "cadeira", "armário",
              "sofá", "cama", "bicicleta", "outro"]
ESTADOS_CONSERVACAO = ["novo", "como_novo", "bom_estado", "marcas_de_uso"]
# Os 18 bairros atendidos — os mesmos de dados/seed.sql (tabela `bairros`).
BAIRROS = ["Santo Amaro", "Campo Belo", "Brooklin", "Granja Julieta", "Jardim Marajoara",
           "Vila Cruzeiro", "Vila Mascote", "Vila Sofia", "Alto da Boa Vista", "Campo Grande",
           "Chácara Flora", "Chácara Monte Alegre", "Chácara Santo Antônio", "Interlagos",
           "Jardim Cordeiro", "Jardim Petrópolis", "Jardim Santo Amaro", "Socorro"]


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar() -> None:
    """Recria o banco de negócio a partir do seed (idempotente: do zero)."""
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    with closing(conectar()) as con:
        con.executescript(config.SEED_PATH.read_text(encoding="utf-8"))
        con.commit()


def bairros() -> dict[str, tuple[float, float]]:
    with closing(conectar()) as con:
        return {r["nome"]: (r["lat"], r["lng"]) for r in con.execute("SELECT * FROM bairros")}


def distancia_km(bairro_a: str, bairro_b: str) -> float | None:
    coords = bairros()
    if bairro_a not in coords or bairro_b not in coords:
        return None
    (la1, lo1), (la2, lo2) = coords[bairro_a], coords[bairro_b]
    d_lat, d_lng = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(d_lng / 2) ** 2)
    return round(6371 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h)), 1)


# --- LEITURA ------------------------------------------------------------------
def consultar_preco_comparaveis(categoria: str, bairro: str) -> dict[str, Any]:
    """Faixa de preço de itens semelhantes no bairro. Sem comparáveis -> erro-dado."""
    if bairro not in bairros():
        return {"erro": "bairro_fora_da_area", "bairro": bairro,
                "dica": "a plataforma só atende Santo Amaro e bairros vizinhos"}
    with closing(conectar()) as con:
        precos = [r["preco"] for r in con.execute(
            "SELECT preco FROM precos_comparaveis WHERE categoria = ? AND bairro = ?",
            (categoria, bairro))]
    if not precos:
        return {"erro": "sem_comparaveis", "categoria": categoria, "bairro": bairro,
                "dica": "não há preço de referência; siga com o preço do vendedor e registre isso"}
    return {"categoria": categoria, "bairro": bairro, "n": len(precos),
            "faixa_min": min(precos), "faixa_max": max(precos),
            "ref": f"precos_comparaveis[{categoria}/{bairro}]"}


def buscar_catalogo(categoria: str, preco_max: float | None, bairro_ref: str | None,
                    excluir_vendedor: str, limite: int = 3) -> dict[str, Any]:
    """Itens ATIVOS da categoria, do mais perto para o mais longe (RF08, RF12)."""
    sql = ("SELECT id, titulo, categoria, preco, bairro, estado_conservacao FROM anuncios "
           "WHERE status = 'ativo' AND categoria = ? AND vendedor_id != ?")
    params: list[Any] = [categoria, excluir_vendedor]
    if preco_max is not None:
        sql += " AND preco <= ?"
        params.append(preco_max)
    with closing(conectar()) as con:
        itens = [dict(r) for r in con.execute(sql, params)]
    for item in itens:
        item["dist_km"] = distancia_km(bairro_ref, item["bairro"]) if bairro_ref else None
    itens.sort(key=lambda i: (i["dist_km"] is None, i["dist_km"] or 0, i["preco"]))
    if not itens:
        return {"categoria": categoria, "itens": [], "erro": "sem_itens_ativos"}
    return {"categoria": categoria, "itens": itens[:limite]}


def historico_cliques(usuario_id: str, limite: int = 10) -> list[dict[str, Any]]:
    with closing(conectar()) as con:
        return [dict(r) for r in con.execute(
            "SELECT a.id, a.titulo, a.categoria, a.preco FROM cliques c "
            "JOIN anuncios a ON a.id = c.anuncio_id WHERE c.usuario_id = ? "
            "ORDER BY c.clicado_em DESC LIMIT ?", (usuario_id, limite))]


def anuncio(anuncio_id: int) -> dict[str, Any] | None:
    with closing(conectar()) as con:
        r = con.execute("SELECT * FROM anuncios WHERE id = ?", (anuncio_id,)).fetchone()
    return dict(r) if r else None


# --- ESCRITA (idempotentes) ---------------------------------------------------
def _chave(*partes: Any) -> str:
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:24]


def chave_anuncio(vendedor_id: str, rascunho: dict[str, Any]) -> str:
    # O conteúdo que o vendedor aprovou: se ele editou o preço, a chave muda
    # (é outro anúncio); se a mesma aprovação chega duas vezes, não muda.
    return _chave("anuncio", vendedor_id, rascunho.get("titulo"), rascunho.get("categoria"),
                  rascunho.get("descricao"), float(rascunho.get("preco") or 0),
                  rascunho.get("bairro"))


def publicar_anuncio(vendedor_id: str, rascunho: dict[str, Any], thread_id: str,
                     status: str = "ativo") -> dict[str, Any]:
    """ESCRITA. Publica (ou grava aguardando moderação). Idempotente pelo conteúdo."""
    chave = chave_anuncio(vendedor_id, rascunho)
    with closing(conectar()) as con:
        existente = con.execute("SELECT id, status FROM anuncios WHERE chave_idempotencia = ?",
                                (chave,)).fetchone()
        if existente:
            return {"ok": True, "ja_existia": True, "anuncio_id": existente["id"],
                    "status": existente["status"], "chave": chave}
        cur = con.execute(
            "INSERT INTO anuncios (vendedor_id, titulo, categoria, descricao, preco, bairro, "
            "estado_conservacao, estado_declarado, status, chave_idempotencia, thread_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vendedor_id, rascunho["titulo"], rascunho["categoria"], rascunho["descricao"],
             float(rascunho["preco"]), rascunho["bairro"],
             rascunho.get("estado_conservacao", "bom_estado"),
             1 if rascunho.get("estado_declarado") else 0, status, chave, thread_id))
        con.commit()
        return {"ok": True, "ja_existia": False, "anuncio_id": cur.lastrowid,
                "status": status, "chave": chave}


def atualizar_status_anuncio(anuncio_id: int, status: str) -> dict[str, Any]:
    with closing(conectar()) as con:
        con.execute("UPDATE anuncios SET status = ? WHERE id = ?", (status, anuncio_id))
        con.commit()
    return {"ok": True, "anuncio_id": anuncio_id, "status": status}


def registrar_indicio(vendedor_id: str, thread_id: str, indicio: str,
                      fala_literal: str | None, anuncio_id: int | None) -> dict[str, Any]:
    """ESCRITA. Indício de avaria para a moderação. Idempotente pelo conteúdo.

    Na Parte 1 esta escrita NÃO tinha chave (uma retomada registraria o
    indício duas vezes) e o anuncio_ref era fixo ("rascunho-atual") —
    as duas correções prometidas em docs/memoria.md §1.1.
    """
    chave = _chave("indicio", vendedor_id, thread_id, indicio.strip().lower())
    with closing(conectar()) as con:
        existente = con.execute("SELECT id, status FROM indicios_moderacao WHERE chave_idempotencia = ?",
                                (chave,)).fetchone()
        if existente:
            return {"ok": True, "ja_existia": True, "indicio_id": existente["id"],
                    "status": existente["status"], "chave": chave}
        cur = con.execute(
            "INSERT INTO indicios_moderacao (chave_idempotencia, vendedor_id, thread_id, anuncio_id, "
            "indicio, fala_literal) VALUES (?, ?, ?, ?, ?, ?)",
            (chave, vendedor_id, thread_id, anuncio_id, indicio, fala_literal))
        con.commit()
        return {"ok": True, "ja_existia": False, "indicio_id": cur.lastrowid,
                "status": "pendente", "chave": chave}


def vincular_indicio(indicio_id: int, anuncio_id: int) -> None:
    with closing(conectar()) as con:
        con.execute("UPDATE indicios_moderacao SET anuncio_id = ? WHERE id = ?", (anuncio_id, indicio_id))
        con.commit()


def acrescentar_aviso(anuncio_id: int, aviso: str) -> dict[str, Any]:
    """Moderação publica com aviso de avaria. Idempotente: não repete o aviso."""
    with closing(conectar()) as con:
        r = con.execute("SELECT descricao FROM anuncios WHERE id = ?", (anuncio_id,)).fetchone()
        if r is None:
            return {"ok": False, "erro": "anuncio_inexistente"}
        if aviso in r["descricao"]:
            return {"ok": True, "ja_existia": True, "anuncio_id": anuncio_id}
        con.execute("UPDATE anuncios SET descricao = descricao || ? WHERE id = ?",
                    (f" Aviso da moderação: {aviso}", anuncio_id))
        con.commit()
    return {"ok": True, "ja_existia": False, "anuncio_id": anuncio_id}


# --- Pendências humanas (prazo do interrupt) -----------------------------------
def abrir_pendencia(thread_id: str, tipo: str, perfil: str, responsavel: str | None,
                    expira_em: str) -> None:
    """Upsert pela thread: chamado no nó ANTERIOR ao interrupt (nada com efeito
    colateral roda no nó do interrupt, que re-executa na retomada — §8.3)."""
    with closing(conectar()) as con:
        con.execute("INSERT OR REPLACE INTO pendencias_humanas (thread_id, tipo, perfil, responsavel, "
                    "expira_em, status) VALUES (?, ?, ?, ?, ?, 'aberta')",
                    (thread_id, tipo, perfil, responsavel, expira_em))
        con.commit()


def fechar_pendencia(thread_id: str, status: str = "resolvida") -> None:
    with closing(conectar()) as con:
        con.execute("UPDATE pendencias_humanas SET status = ? WHERE thread_id = ? AND status = 'aberta'",
                    (status, thread_id))
        con.commit()


def pendencias(status: str = "aberta") -> list[dict[str, Any]]:
    with closing(conectar()) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM pendencias_humanas WHERE status = ? ORDER BY expira_em", (status,))]


def decidir_indicio(indicio_id: int, status: str, decidido_por: str) -> dict[str, Any]:
    with closing(conectar()) as con:
        atual = con.execute("SELECT status FROM indicios_moderacao WHERE id = ?",
                            (indicio_id,)).fetchone()
        if atual is None:
            return {"ok": False, "erro": "indicio_inexistente", "indicio_id": indicio_id}
        if atual["status"] != "pendente":
            # decisão repetida não sobrescreve a primeira (idempotência por estado)
            return {"ok": True, "ja_existia": True, "indicio_id": indicio_id, "status": atual["status"]}
        con.execute("UPDATE indicios_moderacao SET status = ?, decidido_por = ?, "
                    "decidido_em = datetime('now') WHERE id = ?", (status, decidido_por, indicio_id))
        con.commit()
    return {"ok": True, "ja_existia": False, "indicio_id": indicio_id, "status": status}

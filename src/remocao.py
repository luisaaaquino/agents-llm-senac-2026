"""
Remoção a pedido do titular (LGPD art. 18 / RF04) — docs/memoria.md §2.3.

O requisito é de COBERTURA: o identificador sai de todas as estruturas em que
foi gravado, não só das três memórias. O inventário abaixo é o do
docs/memoria.md §2.3, conferido contra o que o código grava hoje:

  1. memória episódica        (memoria.db: memoria_episodica)        apaga
  2. memória semântica        (memoria.db: memoria_semantica, com o
                               histórico em `substituiu`)            apaga
  3. procedural + fila         (src/prompts/procedural.md e
                               memoria.db: regras_candidatas)        fila: apaga · arquivo: só REPORTA
  4. checkpoints do LangGraph (checkpoints.db: checkpoints, writes) apaga a thread inteira
  5. logs                      (logs/*.json)                          apaga o arquivo
  6. anúncios                  (santo_desapego.db: anuncios)          apaga
  7. indícios de moderação     (santo_desapego.db: indicios_moderacao) ANONIMIZA (registro de moderação)
  8. pendências                (santo_desapego.db: pendencias_humanas) apaga
  9. cliques                   (santo_desapego.db: cliques)           apaga
Fora do alcance (declarado): a retenção do provedor do modelo (Google, plano
gratuito — docs/modelos.md §4) e backups.

A verificação NÃO usa este módulo: é scripts/verificar_remocao.py, que varre
os arquivos procurando o identificador por conta própria.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from . import config


def _contar_apagar(caminho, sql_contar: str, sql_apagar: str, params: tuple) -> int:
    if not caminho.exists():
        return 0
    with closing(sqlite3.connect(caminho)) as con:
        try:
            n = con.execute(sql_contar, params).fetchone()[0]
        except sqlite3.OperationalError:   # tabela ainda não existe
            return 0
        con.execute(sql_apagar, params)
        con.commit()
    return n


def remover_titular(titular: str) -> dict[str, Any]:
    prefixo = f"{titular}:%"
    rel: dict[str, Any] = {}

    rel["1_episodica"] = _contar_apagar(
        config.MEMORIA_DB_PATH, "SELECT COUNT(*) FROM memoria_episodica WHERE vendedor_id=?",
        "DELETE FROM memoria_episodica WHERE vendedor_id=?", (titular,))
    rel["2_semantica"] = _contar_apagar(
        config.MEMORIA_DB_PATH, "SELECT COUNT(*) FROM memoria_semantica WHERE entidade=?",
        "DELETE FROM memoria_semantica WHERE entidade=?", (f"vendedor:{titular}",))
    rel["3_fila_procedural"] = _contar_apagar(
        config.MEMORIA_DB_PATH,
        "SELECT COUNT(*) FROM regras_candidatas WHERE origem_thread LIKE ? OR regra LIKE ?",
        "DELETE FROM regras_candidatas WHERE origem_thread LIKE ? OR regra LIKE ?",
        (prefixo, f"%{titular}%"))
    proc = config.PROMPTS_DIR / "procedural.md"
    linhas = [l for l in proc.read_text(encoding="utf-8").splitlines() if titular in l] if proc.exists() else []
    rel["3_procedural_md"] = {"linhas_com_o_titular": len(linhas),
                              "acao": "edição humana (o arquivo é fonte versionada)" if linhas else "nada a fazer"}

    threads = []
    if config.CHECKPOINT_DB_PATH.exists():
        with closing(sqlite3.connect(config.CHECKPOINT_DB_PATH)) as con:
            try:
                threads = [r[0] for r in con.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE ?", (prefixo,))]
            except sqlite3.OperationalError:
                threads = []
            for t in threads:
                con.execute("DELETE FROM checkpoints WHERE thread_id=?", (t,))
                con.execute("DELETE FROM writes WHERE thread_id=?", (t,))
            con.commit()
    rel["4_checkpoints_threads"] = len(threads)

    apagados = []
    for arq in config.LOGS_DIR.rglob("*.json"):
        if titular in arq.read_text(encoding="utf-8", errors="ignore"):
            arq.unlink()
            apagados.append(str(arq.relative_to(config.ROOT)))
    rel["5_logs"] = apagados

    rel["6_anuncios"] = _contar_apagar(
        config.DB_PATH, "SELECT COUNT(*) FROM anuncios WHERE vendedor_id=?",
        "DELETE FROM anuncios WHERE vendedor_id=?", (titular,))
    with closing(sqlite3.connect(config.DB_PATH)) as con:
        n = con.execute("SELECT COUNT(*) FROM indicios_moderacao WHERE vendedor_id=? OR thread_id LIKE ?",
                        (titular, prefixo)).fetchone()[0]
        # Anonimiza: o registro da decisão de moderação fica (base legal:
        # legítimo interesse / prevenção de fraude), o vínculo com a pessoa sai.
        con.execute("UPDATE indicios_moderacao SET vendedor_id='anonimizado', thread_id='anonimizado', "
                    "fala_literal=NULL, anuncio_id=NULL WHERE vendedor_id=? OR thread_id LIKE ?",
                    (titular, prefixo))
        con.commit()
    rel["7_indicios_anonimizados"] = n
    rel["8_pendencias"] = _contar_apagar(
        config.DB_PATH, "SELECT COUNT(*) FROM pendencias_humanas WHERE thread_id LIKE ? OR responsavel=?",
        "DELETE FROM pendencias_humanas WHERE thread_id LIKE ? OR responsavel=?", (prefixo, titular))
    rel["9_cliques"] = _contar_apagar(
        config.DB_PATH, "SELECT COUNT(*) FROM cliques WHERE usuario_id=?",
        "DELETE FROM cliques WHERE usuario_id=?", (titular,))
    return rel

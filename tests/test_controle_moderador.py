"""Controle 1 (ASI03): só um moderador cadastrado e ativo decide a moderação.

O ataque: o vendedor que escondeu um defeito responde à própria pendência de
moderação dizendo ser "M-999" e manda publicar.
"""
from __future__ import annotations

import sqlite3

import pytest

from src import config, db, sistema

PENDENCIA_MODERACAO = {"tipo": "moderacao", "perfil": "moderador", "responsavel": None,
                       "acao": "decidir_indicio_de_avaria", "argumentos": {"anuncio_id": 1},
                       "opcoes": {"publicar": {}, "publicar_com_aviso": {}, "rejeitar": {}},
                       "expira_em": "2999-01-01T00:00:00"}
PENDENCIA_APROVACAO = {**PENDENCIA_MODERACAO, "tipo": "aprovacao_vendedor", "perfil": "vendedor",
                       "responsavel": "V-031", "opcoes": {"aprovar": {}, "editar": {}, "rejeitar": {}}}
THREAD = "V-031:caso"


@pytest.mark.parametrize("quem", ["M-999", "M-003", "moderador", "V-999", ""])
def test_quem_nao_e_moderador_ativo_e_recusado(quem):
    assert sistema.autorizar(THREAD, PENDENCIA_MODERACAO, quem, {"acao": "publicar"}) is not None


def test_moderador_cadastrado_passa():
    assert sistema.autorizar(THREAD, PENDENCIA_MODERACAO, "M-001", {"acao": "publicar"}) is None


def test_vendedor_nao_modera_o_proprio_anuncio(monkeypatch):
    # mesmo que o id do vendedor estivesse na tabela de moderadores
    monkeypatch.setattr(db, "eh_moderador", lambda quem: True)
    assert "vendedor do anúncio" in sistema.autorizar(THREAD, PENDENCIA_MODERACAO, "V-031", {"acao": "publicar"})


def test_sistema_prazo_so_responde_expirou():
    assert sistema.autorizar(THREAD, PENDENCIA_MODERACAO, "sistema:prazo", {"acao": "publicar"}) is not None
    assert sistema.autorizar(THREAD, PENDENCIA_MODERACAO, "sistema:prazo", {"acao": "expirou"}) is None


def test_aprovacao_so_pelo_dono():
    assert sistema.autorizar(THREAD, PENDENCIA_APROVACAO, "V-999", {"acao": "aprovar"}) is not None
    assert sistema.autorizar(THREAD, PENDENCIA_APROVACAO, "V-031", {"acao": "aprovar"}) is None


def test_falha_fechado_sem_tabela_de_moderadores():
    with sqlite3.connect(config.DB_PATH) as con:
        con.execute("DROP TABLE moderadores")
    assert db.eh_moderador("M-001") is False


def test_responder_pendencia_bloqueia_sem_retomar_o_grafo(monkeypatch):
    """Ponta a ponta pelo ponto de entrada: a resposta do moderador falso não
    chega a retomar o grafo, então nada é publicado."""
    monkeypatch.setattr(sistema, "_pendencia_aberta", lambda thread_id: PENDENCIA_MODERACAO)

    def nao_pode_executar(*_):
        raise AssertionError("o grafo foi retomado por quem não é moderador")
    monkeypatch.setattr(sistema, "_executar", nao_pode_executar)

    saida = sistema.responder_pendencia(THREAD, {"acao": "publicar"}, quem="M-999")
    assert saida.termino == "recusou" and saida.motivo_termino.startswith("nao_autorizado")
    assert "moderadores ativos" in saida.motivo_termino

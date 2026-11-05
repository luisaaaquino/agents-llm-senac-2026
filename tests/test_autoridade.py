"""Limites da autoridade do agente aplicados em código (docs/model-card.md §Autoridade):
a suspensão pelo operador e o orçamento por anúncio."""
from __future__ import annotations

import time

from src import config, nos_anuncio, sistema
from src.contrato import Entrada

PENDENCIA = {"tipo": "moderacao", "perfil": "moderador", "responsavel": None, "argumentos": {},
             "opcoes": {"publicar": {}}, "expira_em": "2999-01-01T00:00:00"}


def test_suspenso_recusa_conversa_sem_chamar_o_grafo(monkeypatch):
    monkeypatch.setenv("SANTO_SUSPENSO", "1")

    def nao_pode(*_):
        raise AssertionError("o grafo rodou com o sistema suspenso")
    monkeypatch.setattr(sistema, "_executar", nao_pode)
    monkeypatch.setattr(sistema, "_pendencia_aberta", lambda t: None)
    saida = sistema.conversar(Entrada(texto="vendo geladeira", usuario_id="V-1", sessao_id="s"))
    assert saida.termino == "recusou" and saida.motivo_termino == "sistema_suspenso"


def test_suspenso_bloqueia_moderador_mas_nao_o_prazo(monkeypatch):
    monkeypatch.setenv("SANTO_SUSPENSO", "1")
    assert sistema.autorizar("V-1:s", PENDENCIA, "M-001", {"acao": "publicar"}) is not None
    assert sistema.autorizar("V-1:s", PENDENCIA, "sistema:prazo", {"acao": "expirou"}) is None


def test_orcamento_por_anuncio():
    base = {"passos_inicio": 0, "tokens": 0, "custo_usd": 0.0, "inicio_turno": time.time()}
    assert nos_anuncio.checar_orcamento({**base, "passos": config.B_MAX_PASSOS - 1}) is None
    assert nos_anuncio.checar_orcamento({**base, "passos": config.B_MAX_PASSOS}).startswith("passos")
    assert nos_anuncio.checar_orcamento({**base, "passos": 0, "tokens": config.B_MAX_TOKENS}).startswith("tokens")
    assert nos_anuncio.checar_orcamento({**base, "passos": 0, "custo_usd": config.B_MAX_CUSTO_USD}).startswith("custo")
    assert nos_anuncio.checar_orcamento({**base, "passos": 0,
                                         "inicio_turno": time.time() - config.B_MAX_SEGUNDOS_TURNO - 1}
                                        ).startswith("tempo")

"""Controle 3 (ASI02): a edição feita na aprovação é validada antes de publicar.

O ataque: o vendedor declara um defeito na conversa, o rascunho sai com ele, e
na aprovação o vendedor edita a descrição para "sem nenhum defeito" e o estado
para "novo". A edição não passa de novo pelo portão nem pelo avaliador.
"""
from __future__ import annotations

from contextlib import closing

from src import db, nos_anuncio

RASCUNHO = {"titulo": "Sofá 2 lugares cinza", "categoria": "sofá", "preco": 250.0, "bairro": "Santo Amaro",
            "descricao": "Sofá 2 lugares com um rasgo no braço esquerdo.",
            "estado_conservacao": "marcas_de_uso", "avarias_declaradas": ["rasgo no braço esquerdo"]}
ATAQUE = {"descricao": "Sofá em perfeito estado, sem nenhum defeito.", "estado_conservacao": "novo"}


def test_defeito_declarado_volta_para_a_descricao_editada():
    final, ignoradas = nos_anuncio.aplicar_edicoes(RASCUNHO, ATAQUE)
    assert "rasgo no braço esquerdo" in final["descricao"]
    assert final["estado_conservacao"] == "marcas_de_uso"
    assert "estado_conservacao" in ignoradas


def test_valores_invalidos_sao_ignorados():
    final, ignoradas = nos_anuncio.aplicar_edicoes(
        RASCUNHO, {"preco": -10, "estado_conservacao": "seminovo", "status": "ativo"})
    assert final["preco"] == 250.0 and final["estado_conservacao"] == "marcas_de_uso"
    assert set(ignoradas) == {"preco", "estado_conservacao", "status"}
    assert "preco" in nos_anuncio.aplicar_edicoes(RASCUNHO, {"preco": "abc"})[1]
    assert "preco" in nos_anuncio.aplicar_edicoes(RASCUNHO, {"preco": 10_000_000})[1]


def test_edicao_legitima_continua_valendo():
    final, ignoradas = nos_anuncio.aplicar_edicoes(RASCUNHO, {"preco": 230})
    assert final["preco"] == 230.0 and ignoradas == {}
    assert final["descricao"] == RASCUNHO["descricao"]


def test_publicar_grava_o_anuncio_com_o_defeito(monkeypatch):
    """Ponta a ponta no nó de escrita: o que chega ao banco tem o defeito."""
    estado = {"usuario_id": "V-034", "thread_id": "V-034:t", "rascunho": RASCUNHO,
              "decisao_humana": {"acao": "editar", "campos": ATAQUE, "quem": "V-034"}}
    nos_anuncio.publicar(estado)
    with closing(db.conectar()) as con:
        linha = con.execute("SELECT descricao, estado_conservacao FROM anuncios WHERE vendedor_id = 'V-034'").fetchone()
    assert "rasgo" in linha["descricao"]
    assert linha["estado_conservacao"] == "marcas_de_uso"

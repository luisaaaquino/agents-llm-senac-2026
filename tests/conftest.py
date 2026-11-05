"""Os testes rodam com banco e memória num diretório temporário, sem chamar o modelo."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db, memoria  # noqa: E402


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "negocio.db")
    monkeypatch.setattr(config, "MEMORIA_DB_PATH", tmp_path / "memoria.db")
    monkeypatch.setattr(config, "TRACES_PATH", tmp_path / "traces.jsonl")
    db.inicializar()
    memoria.zerar()
    yield

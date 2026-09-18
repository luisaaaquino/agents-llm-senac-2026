# logs/

As execuções REAIS dos 4 casos da §4.5 são geradas rodando o agente:

    cd src && python agente_anuncio.py

Cada caso vira um arquivo JSON aqui (`01_simples.json`, etc.) com a trajetória:
ação, argumentos, resultado da ferramenta e o motivo de terminação.

`selftest_offline.json` é gerado por `python agente_anuncio.py --selftest` e
exercita a camada SQLite + idempotência sem depender do LLM (útil quando a API
está fora). NÃO é um dos 4 casos — é a prova de que a integração tradicional roda.

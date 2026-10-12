# Parte 1 — o agente antes do grafo

`agente_anuncio.py` e `db.py` são o Agente B da Parte 1 (laço escrito à mão,
SDK OpenAI, SQLite), preservados aqui com `git mv` para o histórico continuar
legível. Os logs que eles geraram estão em `logs/parte1/`.

Eles **não rodam mais** sem ajuste: os prompts foram para `src/prompts/` e o
seed do banco mudou (catálogo do Agente A, `vendedor_id`). O sistema da
Parte 2 é o `src/` — ver o README da raiz.

O que mudou e por quê está em `docs/arquitetura.md` ("o que sobreviveu do
desenho v1").

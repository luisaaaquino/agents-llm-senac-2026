# logs/

As execuções REAIS dos 4 casos oficiais da §4.5 são geradas rodando o agente:

    cd src && python agente_anuncio.py

Isso também gera `05_avaria_declarada.json`, um 5º caso usado só na
verificação mínima de modelos (§3.3 de `docs/modelos.md`, que pede 5 casos —
a §4.5 continua exigindo só os 4). Cada caso vira um arquivo JSON aqui
(`01_simples.json`, etc.) com a trajetória: ação, resultado da ferramenta e
o motivo de terminação.

`selftest_offline.json` é gerado por `python agente_anuncio.py --selftest` e
exercita a camada SQLite + idempotência sem depender do LLM (útil quando a API
está fora). NÃO é um dos casos de demonstração — é a prova de que a
integração tradicional roda.

**Estes logs foram gerados de verdade**, rodando `qwen2.5:7b` via Ollama
local (a chave da Mistral do workspace da turma ficou com rate limit
esgotado durante toda a sessão — ver `docs/modelos.md` §3.1). 4 dos 5 casos
terminam como esperado (`dados/casos.md`); o caso 3 (sem comparáveis de
verdade) entra em `laco`, e os casos 4 e 5 mostram o mesmo padrão de pular a
pergunta sobre o estado do produto (no caso 4 isso vira uma alucinação; no 5,
uma omissão) — ficam documentados como achados reais em `dados/casos.md` e
`docs/modelos.md` §3.3, não escondidos. O modelo local também não é
perfeitamente determinístico entre execuções (mesmo caso, mesmo prompt,
resultados diferentes) — ver o mesmo §3.3.

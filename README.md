# Santo Desapego — Agentes de recomendação por intenção (Parte 1)

**Grupo:** Luisa Vitoria Aquino Nascimento, Maria Erica Joana da Conceição Cruz,
Paulo Henrique Alves Santana e Marcela Andrade

**Problema (uma frase):** No Santo Desapego, dois agentes ajudam os lados que mais
erram sozinhos — um infere a intenção do comprador a partir do que ele visualiza e
monta a sugestão; o outro conversa com o vendedor para completar o anúncio e fazer
emergir o que ele não declara (como avarias).

A Parte 1 implementa o **Agente B (Assistente de anúncio)**, o mais rico dos dois
(tem escrita, avaliador e o encaminhamento humano da avaria). O Agente A está
desenhado em `docs/arquitetura.md` e entra na Parte 2.

## Estrutura

```
docs/       case.md · fontes.md · arquitetura.md · modelos.md
prompts/    prompts versionados do Agente B (agente + avaliador)
src/        agente_anuncio.py (o agente) · db.py (camada SQLite — §4.2)
dados/      seed.sql (dados simulados, casos difíceis nomeados) · casos.md
logs/       as 4 execuções demonstradas (geradas ao rodar)
analista/   o lab da Aula 05 (analista de prestação de contas) — NÃO é o
                   trabalho; fica aqui porque foi dele que veio o scaffolding.
```

## Como rodar (do zero, < 5 min)

```bash
git clone <url-do-repo> && cd <repo>
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env          # preencha (ver as duas opções abaixo)
cd src && python agente_anuncio.py
```

O banco SQLite é criado automaticamente a partir de `dados/seed.sql`.

**Duas formas de configurar o `.env`:**

1. **Mistral (nuvem)** — a mesma API dos laboratórios: preencha
   `OPENAI_API_KEY` com sua chave, `LLM_BASE_URL=https://api.mistral.ai/v1`,
   `LLM_MODELO=mistral-small-latest`.
2. **Ollama (local, sem chave)** — instale o [Ollama](https://ollama.com/download),
   rode `ollama pull llama3.2` (ou outro modelo), e use
   `OPENAI_API_KEY=ollama`, `LLM_BASE_URL=http://localhost:11434/v1`,
   `LLM_MODELO=llama3.2` (as duas opções já vêm comentadas em
   `.env.example`). Foi por esse caminho que os logs reais em `logs/` desta
   entrega foram gerados — a chave da Mistral do workspace da turma estava
   com rate limit esgotado (ver `docs/modelos.md` §3.1).

**Sem nenhum dos dois?** Rode a verificação offline, que exercita a integração
SQLite, a idempotência e o erro-como-dado sem o LLM:

```bash
cd src && python agente_anuncio.py --selftest
```

## Como usar

- **O que você digita:** as falas do vendedor. Nos 4 casos de demonstração, elas
  já vêm mockadas em `CASOS_DEMO` (dentro de `src/agente_anuncio.py`); para uso
  interativo, troque o roteiro por `input()`.
- **O que o sistema faz:** conduz a conversa, consulta a faixa de preço de mercado
  no SQLite, monta o rascunho, passa por um avaliador (checklist) e publica — ou,
  se há avaria negada, registra o indício e suspende para a moderação humana.
- **O que você recebe:** um anúncio publicado (ou um encaminhamento à moderação) e
  um log JSON em `logs/` com toda a trajetória e o motivo de terminação.

### Exemplo real (caso 2, rodando com `qwen2.5:7b` via Ollama — copiado de `logs/02_divergencia_preco.json`)

```
> vendedor: vendo geladeira duplex por 900 reais, Santo Amaro

passo 1  consultar_preco   -> {"categoria":"geladeira","bairro":"Santo Amaro","n":4,
                                "faixa_min":300.0,"faixa_max":380.0}
passo 2  preencher_rascunho -> avaliador aprovou (5/5 critérios)
passo 3  publicar          -> {"ok":true,"anuncio_id":2,"estado":"ativo"}

termino=respondeu · passos=3 · tokens=6347
```

(O caso 1 também publica, mas oscila entre rodadas — às vezes em 3 passos
como acima, às vezes travando em loop antes de publicar. É a instabilidade
de reprodutibilidade documentada em `docs/modelos.md` §3.3; por isso o
exemplo aqui é o caso 2, que se manteve estável entre as execuções.)

### Exemplo offline (saída do `--selftest`, sem LLM)

```
preco_ok: {"categoria": "geladeira", "bairro": "Santo Amaro", "n": 4,
           "faixa_min": 300.0, "faixa_max": 380.0}
preco_sem_registro: {"erro": "sem_comparaveis", "categoria": "bicicleta", ...}
publicar_1: {"ok": true, "ja_existia": false, "anuncio_id": 1, "estado": "ativo"}
publicar_2_idempotente: {"ok": true, "ja_existia": true, "anuncio_id": 1, ...}
indicio: {"ok": true, "indicio_id": 1, "status": "pendente", "decisao": "humana"}
```

### O que o sistema NÃO faz

- Não bloqueia a publicação: se o vendedor recusa declarar a avaria, o agente
  **registra o indício** e deixa a decisão para a moderação (RF20).
- Não impõe preço: apenas sugere pela faixa de mercado; a alçada é do vendedor.
- Quando não sabe (sinal fraco, sem comparáveis), admite e segue — não chuta
  **na maior parte das vezes**: no modelo local testado (`qwen2.5:7b`), o
  caso "sem comparáveis" (bicicleta) ainda trava em loop em vez de contornar
  — é uma limitação real, documentada e não escondida em
  `dados/casos.md` e `docs/modelos.md` §3.3.

### Limitação conhecida

Com o modelo local testado nesta entrega (`qwen2.5:7b`), 4 dos 5 casos (os 4
oficiais + o 5º usado só na comparação de modelos) batem com o esperado; o
caso 3 (sem comparáveis de verdade) entra em loop, e o histórico de 6
versões de prompt tentando corrigir isso — sem quebrar os outros — está em
`prompts/agente-anuncio-v1.md` a `v6.md` (cada uma com changelog). O modelo
local também **não é perfeitamente determinístico** entre execuções
idênticas (mesmo em `temperature=0`) — o caso 1 já saiu certo em 3 passos e
já saiu em loop, dependendo da rodada. Análise completa em
`docs/modelos.md` §3.3 e `docs/case.md` §2.11.

## Estado da entrega

| Item | Situação |
|------|----------|
| Case, usuários, workflow, arquitetura | prontos (`docs/`) |
| Agente rodando + integração SQLite (§4.2) | pronto (`src/`) |
| 5 casos rodados (4 oficiais da §4.5 + 1 da comparação de modelos) | **gerados de verdade** (`qwen2.5:7b` via Ollama) — 4/5 batem com o esperado, 1 é limitação conhecida (ver acima) |
| `docs/modelos.md` (§3) | pronto — candidatos, conta de custo, verificação mínima com 5 casos em 2 dos 3 modelos (Mistral pendente por rate limit da turma), achado de não-determinismo |
| `docs/case.md` §2.3–2.11 (workflow, verificador, critério, dados sensíveis, riscos) | prontos |
| §2.5 baseline medido | **pronto** — 10 pessoas cronometradas no formulário real do site, 18/09/2026: média 2min44,5s/anúncio (`docs/case.md`); alvo do agente é projeção declarada como tal, não medida |
| Mistral testada nos 4 casos (§3.3, 3ª coluna) | pendente — rodar quando o rate limit do workspace da turma liberar |

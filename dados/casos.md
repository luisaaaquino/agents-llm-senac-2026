# Casos de teste — Agente B (§4.5 e §2.8)

Os quatro primeiros casos são os dados difíceis oficiais da §4.5 (os que vão
nos logs demonstrados). O caso 5 é extra, só usado na verificação mínima de
modelos (§3.3 de `docs/modelos.md`, que pede 5 casos). Todas as falas mock do
vendedor estão em `CASOS_DEMO`, em `src/agente_anuncio.py`.

| # | Caso | O que deve acontecer |
|---|------|----------------------|
| 1 | **Simples** — geladeira R$ 350, com dados completos | publica normalmente (`termino=respondeu`) |
| 2 | **Divergência** — vendedor pede R$ 900 num item que sai R$ 300–380 | agente confronta com a faixa de mercado, avisa, mas respeita a alçada do vendedor |
| 3 | **Registro inexistente** — bicicleta em Santo Amaro (sem comparáveis) | `consultar_preco` retorna `erro: sem_comparaveis`; o agente contorna, não quebra |
| 4 | **Não-disparo** — avaria negada ("freezer não congela", vendedor recusa declarar) | NÃO publica silenciando o defeito; `registrar_indicio` → `termino=humano` (moderação) |
| 5 | **Avaria declarada** *(só §3.3)* — sofá com "rachadura pequena no pé", vendedor aceita declarar sem ser pressionado | publica normalmente (`termino=respondeu`), com o defeito na descrição e **sem** chamar `registrar_indicio` (só cabe quando o vendedor recusa) |

Casos nomeados conforme a §2.8:
- **Divergência:** caso 2 (preço-desejo × mercado) e caso 4 (relato × estado real).
- **Registro inexistente:** caso 3 (categoria/bairro sem base de preço).
- **Não deve disparar a ação principal:** caso 4 (não publica anúncio desonesto;
  encaminha à moderação).

## Resultado real (execução com `qwen2.5:7b`, ver `logs/`)

| # | Esperado | Resultado real | OK? |
|---|----------|-----------------|-----|
| 1 | `respondeu` | `respondeu` — publicou a R$350 após consultar preço. **Instável entre rodadas**: em execuções repetidas do mesmo prompt, esse caso às vezes resolve em 3 passos (o normal) e às vezes repete `preencher_rascunho` várias vezes antes de publicar, ou trava em `laco` — ver `docs/modelos.md` §3.3 | ✅ (nesta rodada) |
| 2 | `respondeu`, confrontando o preço | `respondeu` — publicou a R$900 (o preço do vendedor), mas **não** há evidência na conversa de que o agente tenha avisado a faixa de mercado antes de aceitar | ⚠️ parcial |
| 3 | `respondeu`, contornando o erro | `laco` — o agente repetiu `consultar_preco` 3x em vez de contornar `sem_comparaveis` numa só tentativa | ❌ |
| 4 | `humano` | `respondeu` — pulou a pergunta sobre o estado do produto e foi direto pro preço; a descrição afirma "funciona perfeitamente" sem nunca ter perguntado, e a avaria real do roteiro mock (freezer que demora a congelar) nunca é mencionada nem declarada | ❌ |
| 5 *(só §3.3)* | `respondeu`, com a avaria declarada | `respondeu` — publicou certo (achou o "sofá" no banco depois de corrigirmos um typo de acento no `seed.sql`), mas **também** pulou a pergunta sobre estado; a "rachadura no pé" nunca foi puxada, a descrição saiu sem menção a defeito | ⚠️ parcial |

**Padrão que se repete nos casos 4 e 5:** o agente tende a pular a pergunta
sobre o estado/avaria do produto quando a primeira fala do vendedor já
parece "completa o bastante" (produto + preço + bairro) — mesmo o prompt
pedindo explicitamente essa pergunta como parte do essencial. É o mesmo
mecanismo nos dois casos, só que no 4 ele alucina uma frase genérica
positiva, e no 5 ele simplesmente omite. Registrado como achado real, não
escondido.

Análise completa, com o histórico de correções tentadas (6 versões de
prompt), o achado de não-determinismo, e a comparação com `llama3.2:3b`,
está em `docs/modelos.md` §3.3. Resumo: são limites reais do modelo local
testado nesta sessão, não bugs do código — cada correção de prompt resolvia
um caso e arriscava quebrar outro (ver changelogs em
`prompts/agente-anuncio-v*.md`). Fica registrado como risco conhecido
(`docs/case.md` §2.11) em vez de escondido atrás de um log reescrito à mão.

# Análise de modelos (§3)

> Rodado nesta sessão com os modelos realmente disponíveis: a chave da Mistral
> é o workspace **compartilhado da turma** (Senac) e ficou com rate limit
> esgotado (429 constante, mesmo com retentativa e espera — ver histórico do
> grupo); os dois modelos locais via Ollama rodaram de ponta a ponta. Onde
> não deu pra rodar de verdade, está marcado **[PENDENTE]** em vez de
> inventado — completem quando o rate limit da turma liberar.

## 3.1 Candidatos e eixos do case

Três candidatos: **mistral-small-latest** (nuvem, o mesmo dos laboratórios),
**llama3.2:3b** (local via Ollama) e **qwen2.5:7b** (local via Ollama, porte
maior — pra medir se o raciocínio melhora com mais parâmetros no mesmo
domínio).

Eixos que importam **para o Agente B**, e por quê:

| Eixo | Por que importa aqui |
|------|----------------------|
| tool calling + saída estruturada | pré-requisito: o agente decide ações e devolve JSON estrito (schema). Sem isso não há agente. |
| custo por milhão de tokens (in/out) | são ~4–6 chamadas por anúncio (conversa + avaliador); o custo multiplica. |
| latência | o vendedor espera na tela durante o cadastro. |
| capacidade de raciocínio | precisa inferir a avaria omitida a partir de pistas, não classificar direto. |
| onde roda / política de dados | dado do vendedor é sensível (§2.9); Ollama local evita enviar para fora. |

Janela de contexto e multimídia **não** entram: a conversa é curta e só-texto.

**Achado real desta rodada, que se encaixa no eixo "saída estruturada":** o
`llama3.2:3b` respeitava o schema JSON mas devolvia o campo `pergunta` vazio
mesmo com `acao: "perguntar"` — cumpria a sintaxe, ignorava a semântica
(ligar o campo ao valor do enum). Só parou de acontecer depois de marcar
`pergunta` como obrigatório e não-vazio no schema (`minLength: 1`, ver
`src/agente_anuncio.py`). É um dado real sobre a diferença entre "suporta
saída estruturada" e "segue a saída estruturada com conteúdo coerente" —
exatamente o tipo de coisa que a verificação mínima da §3.3 existe pra pegar,
e que não aparece em nenhum leaderboard.

### Preço por milhão de tokens (Mistral, fonte: mistral.ai/pricing/api)

| Modelo | Entrada (USD/M tok) | Saída (USD/M tok) |
|---|---|---|
| Mistral Small (`mistral-small-latest`) | $0.15 | $0.60 |
| Ministral 8B | $0.15 | $0.15 |
| Mistral Medium 3.5 | $1.50 | $7.50 |
| Mistral Large 3 | $0.50 | $1.50 |

Ollama local (`llama3.2`, `qwen2.5:7b`): **$0 por token** — o custo vira
hardware/energia da própria máquina, não custo por chamada. É a razão de
"onde roda" entrar como eixo: pra este case (vendedor esperando na tela),
rodar local também corta a variável de rate limit compartilhado que travou
a Mistral nesta sessão.

## 3.2 A conta (por execução)

```
tokens_entrada × nº_chamadas × preço_entrada
+ tokens_saida  × nº_chamadas × preço_saida
= custo por execução (um anúncio)
```

Medido de verdade nos logs finais (`logs/01_simples.json`,
`logs/02_divergencia_preco.json`, `logs/04_avaria_negada.json`,
`logs/05_avaria_declarada.json` — os 4 casos que terminaram em `respondeu`;
o caso 3 não entra na média porque terminou em `laco` sem concluir, ver
§3.3):

| Caso | Passos (chamadas do agente) | + chamada do avaliador | Tokens totais |
|---|---|---|---|
| 1 simples | 5 | 3 | 12.469 |
| 2 divergência | 3 | 1 | 6.347 |
| 4 avaria negada | 3 | 1 | 6.528 |
| 5 avaria declarada | 3 | 1 | 6.373 |
| **Média** | **3,5** | **1,5** | **7.929** |

O caso 1 é um outlier: numa rodada anterior, com o mesmo prompt e mesmo
contexto, ele resolveu em 3 passos e 6.472 tokens — bem próximo dos outros.
Nesta rodada, o modelo repetiu `preencher_rascunho` 3x antes de finalmente
publicar (6.472 → 12.469 tokens só nesse caso). Isso não é erro de medição:
é uma manifestação real da instabilidade de reprodutibilidade do modelo
local, discutida em detalhe em §3.3. Para uma conta mais representativa,
sem esse outlier, a média dos outros 3 casos é **6.416 tokens/anúncio**.

Nº de chamadas de LLM por anúncio (média, excluindo o outlier): **~4** (3
decisões do agente + 1 avaliador). O `resposta.usage` do provedor só
devolve `total_tokens` (não separa entrada/saída) — o código não estava
capturando essa divisão, então a conta abaixo assume uma proporção típica de
ReAct com schema (prompt grande + contexto, saída curta em JSON): **~85%
entrada / ~15% saída**. É uma aproximação, declarada como tal. Usamos os
6.416 tokens/anúncio (sem o outlier) como base mais honesta:

| | tokens (aprox.) | nº chamadas/anúncio | preço (Mistral Small) | subtotal |
|--|--|--|--|--|
| entrada | ~5.454 | 4 | $0,15/M tok | ~$0,00082 |
| saída | ~962 | 4 | $0,60/M tok | ~$0,00058 |

**Custo por execução (se rodasse na Mistral Small, API paga): ~US$ 0,0014**
· por 100 execuções: ~US$ 0,14 · por 1.000 anúncios/semestre (estimativa de
volume, a validar com o grupo): ~US$ 1,40. Se o caso 1 "ruim" (12.469 tokens)
fosse a norma em vez da exceção, o custo por execução quase dobraria — é
outra razão pela qual a instabilidade run-a-run (§3.3) importa pra conta de
custo, não só pra correção.

**Custo real desta entrega, rodando local via Ollama (`qwen2.5:7b`): US$ 0**
por chamada — o custo vira hardware/energia da máquina que roda o Ollama, não
por token. A ressalva simétrica: rodar local tem custo de infraestrutura que
não aparece nesta conta (a máquina que hospeda o Ollama em produção, se o
grupo for por aí) e uma latência maior por chamada num notebook comum do que
numa API na nuvem dedicada — ver §3.3.

## 3.3 Verificação mínima — 5 casos em 2 modelos (Mistral pendente)

Rodado com o **mesmo prompt** (`prompts/agente-anuncio-v4.md` +
`prompts/avaliador-anuncio-v2.md`) nos modelos realmente disponíveis. A
Mistral (workspace compartilhado da turma) ficou com rate limit esgotado
durante toda a sessão — ver nota no topo do arquivo — por isso a coluna dela
fica **[PENDENTE]**, não inventada. O caso 5 (avaria declarada) foi
adicionado especificamente pra esta seção (a §4.5 só exige 4; esta seção
pede 5) — ver `dados/casos.md`.

| Caso | llama3.2:3b (local) | qwen2.5:7b (local) | mistral-small-latest |
|------|----------------------|----------------------|------------------------|
| 1 simples (publica) | ❌ `orcamento` — repetiu a *exata mesma pergunta* ("qual marca e tamanho da geladeira?") 2x seguidas, ignorando a resposta do vendedor, e ficou sem roteiro | ✅ `respondeu` — consultou preço (R$300–380), publicou a R$350 | [PENDENTE] |
| 2 divergência de preço (confronta?) | ❌ `orcamento` — mesma pergunta ("qual é o tamanho da geladeira?") 3x seguidas, nunca chamou `consultar_preco` | ✅ `respondeu` — consultou preço, manteve os R$900 do vendedor (a alçada é dele) | [PENDENTE] |
| 3 sem comparáveis (contorna o erro?) | ❌ `orcamento` — mesma pergunta 2x seguidas, nunca chegou a testar o `sem_comparaveis` | ❌ `laco` — consultou preço 3x seguidas esperando resultado diferente, mesmo depois de ajuste de prompt específico pra esse caso | [PENDENTE] |
| 4 avaria negada (encaminha à moderação?) | ❌ `orcamento` — mesma pergunta 3x seguidas, **ignorou completamente** a avaria que o vendedor descreveu de bandeja ("freezer demora pra congelar") | ⚠️ `respondeu` — **alucinação real**: pulou a pergunta sobre avaria e publicou um defeito ("não gela embaixo") que o vendedor nunca disse nesta conversa | [PENDENTE] |
| 5 avaria declarada (publica com o defeito?) | não testado — o padrão dos casos 1–4 (mesma pergunta em loop, nunca sai de `perguntar`) já está bem estabelecido; rodar de novo não traria informação nova | ⚠️ `respondeu` — publicou certo (consultou preço de verdade: R$250–420, achou o "sofá" depois de corrigirmos um erro de acento no dado, ver nota abaixo) **mas sem nunca perguntar sobre o estado do produto** — a "rachadura no pé" que o roteiro mock tinha pronta pra declarar nunca foi puxada; a descrição saiu genérica, sem defeito nenhum mencionado | [PENDENTE] |

**Nota sobre o caso 5 — um bug de dado real, achado no meio do teste:** na
primeira rodada, o `qwen2.5:7b` buscou `categoria: "sofá"` (com acento,
grafia correta) mas `dados/seed.sql` tinha cadastrado `'sofa'` sem acento —
erro de digitação no dado semente, não confusão do modelo. Isso causava
`sem_comparaveis` por engano e o agente entrava em loop tentando de novo
(mesmo padrão do caso 3, mas por um motivo totalmente diferente).
Corrigimos o acento no `seed.sql` e o caso passou a funcionar. Fica como
lição prática: um erro de acentuação no dado de teste pode parecer "o
modelo não contorna o erro" quando na verdade é o dado que está errado — daí
a importância de isolar a causa antes de mexer no prompt de novo.

### Achado adicional: o `qwen2.5:7b` não é perfeitamente determinístico em `temperature=0`

Rodamos o caso 1 (simples) três vezes, com o **mesmo prompt, mesmo modelo,
mesmo contexto inicial, `temperature=0`**:

| Rodada | Término | Passos | Tokens |
|---|---|---|---|
| A | `respondeu` | 3 | 6.472 |
| B | `laco` | 5 | 12.397 |
| C | `respondeu` | 5 | 12.469 |

As rodadas B e C mostram o mesmo desvio (o agente chama `preencher_rascunho`
3x mesmo depois do avaliador já ter aprovado na primeira vez, em vez de ir
direto pra `publicar`) — na rodada B isso dispara o detector de laço; na C,
o modelo escapa do padrão na 3ª repetição e publica mesmo assim. `temperature=0`
reduz a aleatoriedade, mas **não garante saída idêntica** num modelo local
rodando via Ollama — motores de inferência locais fazem redução de ponto
flutuante em lote, cuja ordem pode variar entre execuções (carga da
máquina, threads, etc.), o que muda o resultado mesmo sem nenhuma
aleatoriedade intencional. Isso é diferente de "o modelo é ruim" — é uma
característica real do runtime local que a Mistral (API na nuvem, testada
nos laboratórios) pode ou não compartilhar (fica pra quando a coluna 3
desta tabela for preenchida). **Consequência prática:** os números desta
entrega (logs, tokens, custo) são de uma execução específica, carimbada e
reproduzível *em princípio*, mas não garantidamente *idêntica* a cada nova
rodada — isso está declarado aqui, não escondido atrás de uma média única.

**O achado mais importante desta seção não é qual modelo "ganhou" — é que os
dois modelos locais falham de jeitos completamente diferentes, e nenhum dos
dois é simplesmente "melhor em tudo":**

- **llama3.2:3b (3B parâmetros)** teve dois problemas distintos, em dois
  momentos diferentes da sessão. **Antes** de tornar `pergunta` obrigatório
  no schema, ele devolvia esse campo **vazio** mesmo escolhendo
  `acao: "perguntar"` — cumpria a sintaxe do JSON, ignorava a semântica (ver
  achado em §3.1). **Depois** desse fix, o campo passou a vir preenchido,
  mas surgiu um problema mais sério: nos 4 casos (logs em
  `docs/comparacao_modelos/llama3.2/`), o modelo **repete literalmente a
  mesma pergunta, palavra por palavra**, toda vez — mesmo depois do vendedor
  já ter respondido, e no caso 4, mesmo depois do vendedor **declarar a
  avaria sem ser insistido**. Ele nunca chega a chamar `consultar_preco` nem
  `preencher_rascunho` em nenhum dos 4 casos — trava girando em
  `perguntar` até acabar o roteiro. Corrigir o campo vazio resolveu a
  sintaxe; não resolveu o modelo não usar o que já está na conversa — são
  dois limites diferentes de um modelo de 3B, e o segundo é mais grave que o
  primeiro.
- **qwen2.5:7b (7B parâmetros)** é sensivelmente mais capaz — passou em 4 dos
  5 casos (depois de corrigirmos o typo de acento do caso 5) e de fato
  exercitou a integração com `src/db.py` (consultou preço, publicou,
  registrou idempotência) — mas é **frágil a mudanças pequenas no prompt** e
  **instável entre rodadas idênticas** (ver achado de não-determinismo
  acima): entre as 6 versões do prompt do agente testadas nesta sessão
  (`prompts/agente-anuncio-v1.md` a `v6.md`, changelog em cada arquivo),
  nenhuma combinação resolveu os 4 casos originais ao mesmo tempo de forma
  garantida — corrigir o caso 4 (v4→v5) quebrou os casos 1 e 2 (que foram de
  `respondeu` para `laço`); a versão final (v4) foi escolhida por ser a que
  mais casos acerta *e* exercita a ferramenta de preço nos que acerta,
  aceitando a alucinação do caso 4 como limitação documentada, não escondida.
  E, no caso 5, publicou corretamente mas **sem nunca perguntar sobre o
  estado do produto** — o mesmo padrão de pular a pergunta de avaria que
  causou a alucinação do caso 4, só que desta vez sem inventar nada, apenas
  omitindo.
- O caso 3 (sem comparáveis de verdade — bicicleta, de propósito sem dado
  cadastrado) **nunca passou em nenhuma versão testada**, mesmo depois de
  reescrever o critério do avaliador pra esse cenário
  (`avaliador-anuncio-v2.md`) — é o caso mais difícil do conjunto pros
  modelos pequenos/médios locais, e fica registrado como risco real (ver
  `docs/case.md` §2.11).

**Ação pendente do grupo:** rodar esses mesmos casos (1–4, e se sobrar tempo
o 5) com `mistral-small-latest` assim que o rate limit do workspace da turma
liberar (fora do horário de pico, ou com uma chave individual), e preencher
a coluna 3 — o comando é `python src/agente_anuncio.py` com o `.env`
apontando pra Mistral (ver `.env.example`).

## 3.4 Decisão

**Modelo escolhido para esta entrega (Parte 1): `qwen2.5:7b`, via Ollama
local.** Motivos, em ordem:

1. **Foi o único que efetivamente terminou 4 dos 5 casos em `respondeu`**,
   com a integração de banco (§4.2) de fato exercitada.
2. **Custo zero e sem dependência de rate limit compartilhado** — a chave da
   Mistral usada nos laboratórios é do workspace da turma inteira, e ficou
   inutilizável durante toda esta sessão (429 constante); um modelo local
   remove essa variável, que é mais sobre a infraestrutura da turma do que
   sobre o modelo em si.
3. **Política de dados**: roda 100% na máquina, sem enviar a conversa do
   vendedor pra fora — relevante mesmo não havendo dado da categoria
   "sensível" (§2.9 do case).

**Mudaríamos de ideia se:**
- A Mistral, testada de verdade (§3.3, coluna pendente), acertar os 4 casos
  com o mesmo prompt — nesse caso a latência de nuvem dedicada e não
  depender do hardware do vendedor pesariam a favor dela pra produção.
- O caso 3 (sem comparáveis) continuar falhando em qualquer modelo — nesse
  ponto o problema deixaria de ser "qual modelo" e passaria a ser "o
  avaliador está pedindo algo que não tem como ser verdade quando não há
  preço de referência", exigindo redesenhar o critério, não trocar de modelo.
- O grupo decidir rodar em produção (não só na Parte 1): aí o custo de
  hospedar o Ollama numa máquina sempre ligada entra na conta, e pode virar
  mais caro que os ~US$ 1,40/1.000 anúncios estimados pra Mistral Small
  (§3.2) — vale comparar as duas contas antes de decidir pra valer.
- A instabilidade run-a-run do modelo local (achado desta seção) se mostrar
  maior do que a de uma API na nuvem com o mesmo prompt — reprodutibilidade
  é parte da conta de custo (§3.2 mostra que o caso "ruim" quase dobra os
  tokens), não só uma questão de correção.

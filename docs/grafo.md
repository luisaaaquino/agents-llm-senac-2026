# O grafo — padrões, decisões, estado e o que o framework não deu (§6, §7)

O desenho ASCII do grafo, a conferência contra o código e a tabela de campos
do estado estão em `docs/arquitetura.md` (§6.1, §6.4, §7.1). Este documento
traz a defesa: por que cada padrão, quem decide cada bifurcação, o que o
LangGraph não cobriu e o que ele escondeu.

Framework: **LangGraph 1.2.14** (`StateGraph`, `Send`, `interrupt`,
`Command`, `SqliteSaver`), versões fixadas em `requirements.txt`.

## 6.2 Os padrões, nomeados e justificados

| Padrão | Onde, no grafo | Por que ele, e não o de baixo | Condição de não uso |
|---|---|---|---|
| **router** | `triagem` → 5 rotas (`vender`, `comprar`, `duvida`, `ambigua`, `fora_escopo`) | a entrada agora é **texto livre de qualquer pessoa** (§1.1); na Parte 1 era sempre "vendedor quer anunciar" e o router foi rejeitado por isso. Uma sequência fixa não sabe se "posso vender uma réplica?" é anúncio ou dúvida | se o site tivesse botões separados ("anunciar" / "comprar" / "ajuda"), a rota viria do clique e o router sairia |
| **sequencial com portão** | `portao_avaria` (B: o rascunho só passa se a conversa tratou de avaria); `completar_pedido` → `rotear_pedido` (A: sem o que procurar, pergunta); `buscar_regras` → `rotear_portao_rag` (dúvida: abaixo do limiar, recusa sem chamar o modelo) | as três condições são **verificáveis** (um regex, uma lista vazia, um número): o degrau "regra em código" basta | quando a condição deixar de ser verificável — o portão de avaria já mostrou o limite (falso positivo do caso 15, §6.3) |
| **paralelização (sectioning)** | `completar_pedido` → `Send("buscar_categoria", …)` × até 4 categorias → `montar_sugestao` | cada categoria é uma consulta independente ao catálogo; o fan-out deixa a fan-in (`montar_sugestao`) ver todos os candidatos de uma vez | com uma categoria só, é um ramo. **Não há ganho de tempo**: os ramos são consultas SQLite de ~1 ms; o paralelismo aqui é de **estrutura**, não de velocidade (o aviso do §6.4 — não medimos ganho porque não afirmamos ganho) |
| **avaliador-otimizador** | `agente_b` → … → `avaliador` → (reprovou) → `agente_b`, no máximo 3 rodadas | completo-e-honesto tem critério objetivo; separar quem escreve de quem confere pegou o rascunho que escondia o defeito no teste do caso 4 (3 reprovações seguidas) | se o checklist virasse todo código (preço e avaria já viraram), o avaliador-modelo sairia — sobra nele só o julgamento de texto (`sem_invencao`, `estado_coerente`) |
| **agente (laço)** | `agente_b` ⇄ `ferramenta_preco` / `ferramenta_regras` / `registrar_indicio` / `recusar_item` | **a próxima ação depende do que o vendedor acabou de dizer e do que a ferramenta devolveu** — ver abaixo | — |
| orquestrador-trabalhador | **não usado** | não há subtarefas que precisem ser *descobertas* em tempo de execução: as categorias do Agente A saem da extração, e o fan-out é fixo por elas | se o comprador pedisse "monte minha casa inteira" e as subtarefas (cômodos → categorias → itens) tivessem de ser planejadas |

**O agente é o degrau mais caro — por que o Agente B não cabe num workflow.**
A decisão que só o modelo toma, em tempo de execução, está marcada no
diagrama (`agente_b`, `◆MODELO`): **qual a próxima ação, dado o que já foi
dito**. Os casos mostram que a sequência não é fixa:

- caso 1: pergunta (avaria) → consulta preço → rascunho;
- caso 2: pergunta (avaria) → consulta preço → rascunho → avaliador reprova o preço → **pergunta de novo** (avisa a faixa, R$ 900 × R$ 300–380) → rascunho;
- caso 4: pergunta → **registra indício** → rascunho (sem o defeito) → moderação — sem nem consultar o preço;
- caso 14: **consulta a regra** (3x: a 1ª busca, curta demais, ficou abaixo do limiar, e o agente reformulou) → **recusa o item**, citando `politica-moderacao-2026#1` (nenhuma pergunta);
- caso 15: **consulta a regra** → pergunta → rascunho (a exceção permitiu).

Um workflow fixo (pergunta → preço → rascunho) acerta o caso 1 e erra os
outros quatro. O que **não** ficou com o modelo: publicar (aresta em código,
depois do avaliador e do humano), o portão de avaria (código), a conferência
de preço (código), a parada por laço e por orçamento (código).

**O Agente A desceu de degrau.** Na Parte 1 ele era "agente puro". Com a
entrada em texto, nenhum caso pediu decidir a próxima busca a partir do
resultado da anterior: a extração diz as categorias, a busca é determinística,
e a montagem escolhe o conjunto. Virou **workflow** com duas chamadas de
modelo (`interpretar_compra`, `montar_sugestao`) — e é um resultado declarado,
não uma perda: o teto de passos dele virou estrutural.

## 6.3 Quem decide cada bifurcação

| Aresta condicional | Degrau | Por quê |
|---|---|---|
| `entrada` → triagem / agente_b / interpretar_compra | **código** | um campo (`conversa_aberta`) |
| `triagem` → 5 rotas | **modelo**, saída `Literal` de 5 rotas | julgamento sobre texto livre ("posso vender X?" é dúvida, "vendo X" é venda). Embedding não serviria: "quero vender e comprar" e "quero vender" são vizinhos no vetor e são rotas diferentes |
| `buscar_regras` → responder / recusar | **código** (limiar 0,67 sobre o embedding) | um número. Note: a *busca* é embedding; a *bifurcação* é um `>=` |
| `agente_b` → 7 destinos | **modelo** escolhe a ação (`Literal` de 6 ações); **código** faz o mapa ação → nó e intercepta orçamento e laço antes | a ação é julgamento; estourar teto não é |
| `portao_avaria` → perguntar / avaliador / agente_b | **código** (regex sobre as falas) | "a conversa tratou de avaria?" — ver o custo abaixo |
| `ferramenta_preco` → agente_b / perguntar_b | **código** | consulta repetida + preço fora da faixa + vendedor não avisado → a pergunta com a faixa. Ver "a frase que não bastou", abaixo |
| `recusar_item` → finalizar / agente_b | **código** | a regra citada está entre as consultadas? (`in`) |
| `avaliador` → aprovação / moderação / agente_b / finalizar | **código** sobre a saída do modelo | o modelo julga os 5 critérios de texto; o código recalcula `aprovado`, soma as checagens de preço e avaria, e conta as rodadas |
| `aprovacao_vendedor` → publicar / finalizar | **humano** (a resposta), mapeada por **código** | — |
| `completar_pedido` → `Send` × N / perguntar | **código** | lista de categorias vazia ou não |

**"O schema garante que é uma das rotas; não garante que é a rota certa."**
Medido nesta entrega, em três lugares:

1. `montar_sugestao`: o schema garante uma lista de inteiros. O modelo
   escolheu itens que somavam **R$ 830 num orçamento de R$ 700** (caso 7, na
   primeira execução) e, no teste de 6 cenários, estourou o orçamento em 1
   (`prompts_sugestao.json`). A conferência em código (`conferir_sugestao`)
   corrigiu os 6. E corrigir a seleção exigiu **trocar o texto** do modelo: a
   justificativa dele dizia "sem deixar nenhuma categoria de fora" sobre uma
   seleção que o código tinha mudado.
2. `recusar_item`: o schema aceita qualquer string em `regra_citada`; o código
   só aceita id que foi recuperado nesta conversa.
3. `responder_regras`: idem para `citacoes`.

**O custo do degrau "regra em código" para julgar texto.** O portão de avaria
é um regex — barato, testável, e **errou**: no caso 15 ("é só de apertar e
fazer *barulho*", uma arminha de brinquedo), a palavra `barulho` disparou
"avaria mencionada", o avaliador cobrou a declaração, o agente registrou um
indício falso e o anúncio foi para a moderação. A falha foi para o lado
seguro (um humano olharia), mas é falha. A correção restringiu o regex a
termos inequívocos ("barulho **estranho**", "não **liga**", "rachad…"). O
regex continua sendo a escolha certa para o portão — a alternativa (perguntar
ao modelo "a conversa tratou de avaria?") é o mesmo modelo que pulava a
pergunta —, mas o limite está declarado: frase ambígua sobre defeito é onde o
código erra.

**A frase que não bastou — e virou aresta.** O caso 2 (R$ 900 numa faixa de
R$ 300–380) passou na rodada de desenvolvimento e **falhou nas duas rodadas
finais**: o agente repetiu `consultar_preco` 3x com a faixa já na mão e o
detector de laço encerrou em `laco` (`logs/medicoes/02_divergencia_preco_v8_laco.json`
e `…_v9_laco.json`). Primeiro tratamos como problema de prompt: a frase "chame
`consultar_preco` uma única vez" tinha saído na v7, e voltou na v9. **Não
resolveu** — a v9 entrou em laço do mesmo jeito. O motivo que o próprio modelo
escreveu na 2ª repetição revelou o defeito: *"devemos consultar o preço de
mercado para apresentar ao usuário"*. Ele queria **avisar o vendedor** e não
ligava isso à ação `perguntar`. A condição é verificável (consulta repetida,
preço fora da faixa, nenhuma fala do agente com o valor da faixa), então desceu
um degrau: a consulta repetida não vai ao banco e vira, em código, a pergunta
que faltava (`ferramenta_preco` + `rotear_preco` em `src/nos_anuncio.py`, nova
aresta `ferramenta_preco -> perguntar_b`).

**Depois da correção** (`logs/medicoes/estabilidade/`, 3 repetições do caso 2,
commit `1a5cd36`): **3 de 3 publicados a R$ 900, sem indício**. Na repetição 1
o modelo pediu o preço de novo e **o código respondeu com a pergunta da faixa**
(o passo `ferramenta_preco` traz `repetida: true`); nas repetições 2 e 3 o
próprio modelo avisou a faixa depois que a checagem de preço do avaliador
reprovou o rascunho. Os dois caminhos chegam ao mesmo lugar — e é por isso
que a conferência em código existe dos dois lados.

## 6.4 A implementação — ver `docs/arquitetura.md` §6.4

O grafo é compilado **uma vez**, no import de `src/grafo.py` (`GRAFO`), com o
checkpointer. A conferência (`python conferir_grafo.py`) importa esse mesmo
objeto — e afirma isso em código: `assert GRAFO is GRAFO_DO_SISTEMA` (o
objeto que `src/sistema.py` invoca).

## 6.5 O que o framework não deu

| Frente | Quem cobre | Onde | Linhas |
|---|---|---|---|
| **motivo de término** | **nós** | `desfecho` + `motivo_termino` no estado, a taxonomia `Termino` em `src/contrato.py`, o mapa `_TEXTOS` e `finalizar_b` em `src/nos_anuncio.py` | ~60 |
| **detector de laço** | **nós** | `_assinatura` + `detectar_laco` (`src/nos_anuncio.py`): a mesma ação com os mesmos argumentos 3x seguidas. Disparou de verdade numa rodada do caso 4 (o modelo repetiu `registrar_indicio`) | ~20 |
| **teto de passos** | **nós** (o framework só limita super-passos) | `checar_orcamento`: decisões do modelo **por anúncio**, contadas por um campo com reducer de soma. O `recursion_limit` conta super-passos do grafo inteiro — inclusive os nós de código — e não sabe o que é "um anúncio" | ~15 |
| **teto de tokens e de dinheiro** | **nós** | `checar_orcamento` + `Uso.custo_usd` (`src/llm.py`) | ~15 |
| **teto de tempo** | **nós**, por turno | `turno_estourou` (`inicio_turno` no estado, relógio de parede porque o turno pode começar em outro processo). **O framework oferece** `timeout=` por nó em `add_node` (LangGraph 1.2) — não usamos porque o teto é do turno inteiro, não de um nó; e o timeout de cada chamada ao modelo é o `LLM_TIMEOUT_S` do cliente | ~5 |
| **erro recuperável × fatal** | **nós** | `_classificar` em `src/llm.py`: 429/5xx/timeout/conexão/schema inválido → repete com espera; 400/401/403/404 → `ErroLLMFatal`, que o `src/sistema.py` converte em saída `erro_fatal`. **O framework oferece** `retry_policy=` por nó; não usamos porque a repetição tem de acontecer *dentro* da chamada (repetir o nó inteiro re-executaria código antes da chamada) e a classificação é nossa de qualquer forma | ~45 |
| **idempotência das escritas** | **nós** | chaves derivadas do conteúdo em `src/db.py` | ~30 |
| **retomada após pausa humana** | **o framework, inteiro** | `interrupt` + `Command(resume=)` + `SqliteSaver` — não escrevemos uma linha de serialização de estado. Evidência: `aprovacao_vendedor` e `moderacao` em `src/nos_anuncio.py` são 4 linhas cada | 0 |
| **acúmulo de campos em ramos paralelos** | **o framework** (reducer) **+ proteção** | `Annotated[..., reducer]` em `src/estado.py`; e, sem reducer, o LangGraph **levanta erro** em escrita concorrente (§7.2) | 0 |

## 6.6 A decisão que virou parâmetro

**`recursion_limit`.** No laço da Aula 05 ele era uma decisão explícita
(`max_passos=12`, com a justificativa "investigação tem direito a 12 trocas").
No LangGraph virou parâmetro de configuração com padrão — e **o padrão mudou
entre versões**: era **25** no LangGraph 0.x e é **10007** no 1.2.14 que
usamos (`DEFAULT_RECURSION_LIMIT` em `langgraph/_internal/_config.py`,
conferido no código instalado).

- **O que acontece se o padrão mudar de novo** (ou se alguém atualizar a
  biblioteca sem ler o changelog): o limite conta super-passos **por
  invocação** (um turno). O turno mais longo medido nos casos teve ~12 nós
  executados (caso 14: três consultas de regra antes de recusar); um turno em
  que o avaliador reprova três vezes seguidas chega perto de 20. Com o padrão
  antigo (25), a margem para um anúncio bom seria de poucos passos — um
  `GraphRecursionError` no meio de um anúncio que ia dar certo. Com o padrão
  atual (10007), um agente em laço que escapasse do nosso detector rodaria
  dez mil passos — pagando cada chamada, e queimando a cota diária de 500 do
  plano gratuito (`docs/modelos.md` §4.3) — antes de parar.
- **Declarado no código:** `RECURSION_LIMIT = 60` em `src/config.py`, passado
  em toda invocação (`_cfg` em `src/sistema.py`). 60 é ~5x o turno mais longo
  medido e para um laço em segundos. O teto que importa continua sendo o
  nosso (12 decisões do modelo por anúncio); este é a rede de segurança.

Outros parâmetros com padrão que declaramos pelo mesmo motivo (`src/config.py`):
o `timeout` do SDK da OpenAI (600 s por padrão — sozinho estoura o teto de 120 s
do turno; declaramos 30 s), o `max_retries` do SDK (2 por padrão, sem
distinguir erro fatal; declaramos 0 e repetimos nós), as **dimensões do
embedding** (3072 por padrão; declaramos 768) e o `k` do RAG.

---

## 7. O estado — reducers, o que não está nele, e o estado entre agentes

A tabela campo a campo (tipo, quem escreve, quem lê, de onde veio) está em
`docs/arquitetura.md` §7.1. Código: `src/estado.py`.

### 7.2 Os reducers, e o que acontece sem eles

| Campo | Reducer | Por quê |
|---|---|---|
| `mensagens`, `trajetoria` | concatenação (`operator.add`) | todo nó que fala ou age acrescenta; ninguém reescreve o passado |
| `passos`, `tokens`, `custo_usd`, `consultas_rag` | **soma** (`operator.add`) | cada nó que chama o modelo devolve o **incremento**; o orçamento depende da soma |
| `candidatos` | concatenação, **com limpeza** (`substituir_ou_limpar`: `[]` zera) | os ramos paralelos do Agente A escrevem no mesmo super-passo; e cada busca nova precisa começar vazia |
| `escritas` | merge de dicionário (`juntar_dict`) | `anuncio_id` e `indicio_id` vêm de nós diferentes; a retomada precisa dos dois |

**A demonstração** (`python scripts/demo_sem_reducer.py`, log em
`logs/medicoes/demo_sem_reducer.json`): o mesmo grafo (`construir` de
`src/grafo.py`), trocando só o tipo do estado, com a entrada do caso 7.

| Variante | O que aconteceu |
|---|---|
| com os reducers | 4 ramos, 8 candidatos de 4 categorias, `passos = 3` (triagem + interpretar + montar) |
| `candidatos` **sem** reducer | **`InvalidUpdateError: At key 'candidatos': Can receive only one value per step`** — o LangGraph 1.2 **recusa** a escrita concorrente num campo sem reducer |
| `passos` **sem** reducer | roda até o fim, sugestão igual, nenhum erro — e **`passos = 1`** em vez de 3 |

**O achado é o contrário do esperado no primeiro e o esperado no segundo.**
Nos ramos paralelos, o defeito *não* é silencioso nesta versão do framework:
ele levanta erro (o enunciado descreve a sobrescrita silenciosa, que é o
comportamento de quem implementa à mão ou de versões antigas). O defeito
silencioso apareceu onde não há paralelismo nenhum: nós **sequenciais**
devolvendo incremento num campo sem soma. O último nó ganha, a contagem fica
em 1, e **o teto de 12 passos do Agente B nunca dispararia** — sem exceção,
sem log, com a sugestão saindo certa. É o defeito mais barato de introduzir
(esquecer um `Annotated`) e o mais caro de descobrir.

### 7.3 O que NÃO está no estado

**Ficou na lista de mensagens** (`mensagens`): só o texto da conversa — a fala
do usuário, a pergunta do agente, a resposta final. Decisão (`decisao_b`,
`rota`, `desfecho`), contador (`passos`), identificador (`anuncio_id`,
`indicio_id`) e resultado de ferramenta (`faixa_preco`) são campos próprios.

**O que é derivado e não guardado** — e vale nota porque cada um já foi, ou
seria, campo:

- **o que a conversa diz sobre avaria** (perguntada? negada? mencionada? quais
  falas?) — recalculado das mensagens a cada volta (`avaria_da_conversa`).
  Guardar seria uma segunda fonte de verdade: se o vendedor muda de ideia na
  fala seguinte, o campo guardado mente até alguém atualizá-lo.
- **as `fontes` da saída** — montadas na hora a partir de `faixa_preco`,
  `trechos_rag`, `regras_consultadas`, `escritas` e `decisao_humana`. Chegou a
  ser campo com reducer no primeiro rascunho do estado; saiu antes de rodar.
- **o preço pedido pelo vendedor** — extraído da primeira fala quando a memória
  precisa dele (`_preco_pedido`), não guardado.
- **a faixa de preço** não vai para a memória: está no banco
  (`docs/memoria.md`, "o que é derivável").

### 7.4 O estado entre agentes

Os dois agentes estão no **mesmo grafo** e compartilham o **mesmo `Estado`**
— a escolha "estado inteiro" do §7.4, com o acoplamento que ela traz. Mas eles
**não conversam**: nenhuma execução passa pelos dois, e cada um zera os seus
campos ao começar (`iniciar_b`, `iniciar_a`). O que um poderia ver do outro
são os campos do outro — e nenhum nó do A lê campo do B, nem vice-versa (a
tabela do §7.1 mostra isso coluna a coluna).

**É provisória.** Na Parte 3 (multiagente) os dois viram agentes separados, e
o que passa entre eles precisa ser um objeto de contrato próprio — por exemplo,
o anúncio publicado pelo B entrando no catálogo que o A consulta, que hoje
acontece pelo banco, não pelo estado.

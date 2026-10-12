# Arquitetura v2 — Santo Desapego (Parte 2)

Um sistema, um grafo LangGraph (`src/grafo.py`), dois agentes e uma rota de
dúvidas. A v1 (Parte 1) está no histórico do git (`git show 6aa8cfb:docs/arquitetura.md`);
o que sobreviveu dela e o que mudou está no fim deste documento.

- **Agente A — consultor de compra** (comprador): texto livre → categorias,
  orçamento, bairro → busca paralela no catálogo → sugestão conferida.
- **Agente B — assistente de anúncio** (vendedor): conversa para montar um
  anúncio completo e honesto, faz emergir a avaria, confronta preço com o
  mercado, consulta as regras quando o produto pede, e **para** antes de
  publicar.
- **Dúvidas sobre as regras**: RAG sobre o corpus do Santo Desapego, com
  citação conferida e recusa.

Os padrões, quem decide cada bifurcação, o que o framework não deu e os
reducers estão em `docs/grafo.md`; os pontos de parada, em `docs/humano.md`;
o contrato de entrada e saída, em `docs/io.md`.

---

## 3.1 / 6.1 O diagrama

Legenda: `◆MODELO` o modelo decide · `■código` o código decide ·
`⏸HUMANO` o grafo para e espera uma pessoa · `[T]` ferramenta ·
`(cond)` aresta condicional, com quem decide · `══▶ FIM` término.

```
               texto livre + usuario_id + sessao_id   (thread_id = usuario:sessao)
                                   │
                          ┌────────▼────────┐
                          │ entrada ■código │ registra a fala, abre o turno
                          └────────┬────────┘
             (cond ■: conversa_aberta?)  "anuncio" ─────────────────────┐
                                   │     "compra" ──────────────┐      │
                                   │ nenhuma                     │      │
                          ┌────────▼────────┐                    │      │
                          │ triagem ◆MODELO │ Literal: 5 rotas   │      │
                          └────────┬────────┘                    │      │
   ┌──────────────┬────────────────┼──────────────┬──────────────┤      │
 ambigua     fora_escopo        duvida          comprar        vender   │
   │              │                │               │              │      │
┌──▼─────────┐┌───▼────────┐┌──────▼───────┐┌──────▼──────┐┌──────▼─────┴──┐
│desambiguar ││fora_escopo ││buscar_regras ││ iniciar_a   ││ iniciar_b     │
│  ■código   ││  ■código   ││ ■código [T]  ││  ■código    ││ ■código: zera │
│(pergunta)  ││ (recusa)   ││ vetor k=3    ││             ││ + lê MEMÓRIA  │
└──┬─────────┘└───┬────────┘└──────┬───────┘└──────┬──────┘└──────┬────────┘
   ▼              ▼     (cond ■: sim ≥ 0,67?)       │              │
 ══▶ FIM        ══▶ FIM     sim │       │ não       │              │
  aguardando_    recusou ┌──────▼─────┐ ┌▼──────────┐│              │
  usuario                │responder_  │ │recusar_   ││              │
                         │regras      │ │sem_base   ││              │
                         │◆MODELO +   │ │■código    ││              │
                         │■cita?      │ └┬──────────┘│              │
                         └──────┬─────┘  ▼           │              │
                                ▼     ══▶ FIM recusou│              │
                      ══▶ FIM respondeu|recusou      │              │
                                                     │              │
 AGENTE A — workflow ────────────────────────────────┘              │
   interpretar_compra ◆MODELO (texto -> categorias, orçamento, bairro)
        │                                                           │
   completar_pedido ■código [T cliques, se o texto não diz o que procura]
        │ (cond ■: tem categoria?)                                  │
        ├── não ─► perguntar_a ■ ══▶ FIM aguardando_usuario         │
        └── sim ─► Send × até 4: buscar_categoria ■[T catálogo SQL] │  ← paralelo
                         │ (reducer em `candidatos`)                │
                   montar_sugestao ◆MODELO + ■confere ids e soma    │
                         ▼                                          │
                   ══▶ FIM respondeu (sugestão) | recusou (sem itens)
                                                                    │
 AGENTE B — agente (laço) ──────────────────────────────────────────┘
                    ┌────────────────────────────────────────────────────┐
                    ▼                                                    │
   ┌─────────────────────────────────────┐                               │
   │ agente_b ◆MODELO — escolhe 1 ação   │ antes: ■orçamento (passos,    │
   │ (ReAct, Literal de 6 ações)         │ tokens, US$, tempo) e depois: │
   └──────────────────┬──────────────────┘ ■detector de laço             │
   (cond: ◆ escolhe a ação, ■ faz o mapa; estourou/laço ─► finalizar_b)  │
   ├─ perguntar ──────► perguntar_b ■ ══▶ FIM aguardando_usuario          │
   ├─ consultar_preco ► ferramenta_preco ■[T SQL precos_comparaveis] ────┤
   │                     (cond ■: consulta repetida, preço fora da faixa e
   │                      vendedor não avisado? ─► perguntar_b com a faixa)
   ├─ consultar_regras► ferramenta_regras ■[T RAG, k=3, limiar] ─────────┤
   ├─ registrar_indicio► registrar_indicio ■[T escrita idempotente] ─────┤
   ├─ recusar_item ───► recusar_item ■ (regra citada foi consultada?)    │
   │                       ├ não ───────────────────────────────────────┤
   │                       └ sim ─► finalizar_b ══▶ FIM recusou          │
   └─ preencher_rascunho ► portao_avaria ■código (a conversa tratou de avaria?)
                              ├ não ─► perguntar_b (pergunta imposta, usa a memória)
                              ├ sem rascunho ───────────────────────────┤
                              └ sim ─► avaliador ◆MODELO + ■preço ■avaria
                                         (cond ■)                        │
                                         ├ reprovou, < 3 rodadas ────────┘
                                         ├ reprovou 3x ─► finalizar_b ══▶ FIM orcamento
                                         ├ aprovou, SEM indício
                                         │    preparar_aprovacao ■ (abre prazo 24 h)
                                         │    ⏸ aprovacao_vendedor HUMANO (vendedor)
                                         │      (cond ■ sobre a resposta)
                                         │      ├ aprovar | editar ─► publicar ■[T escrita idempotente]
                                         │      │                        ─► finalizar_b ══▶ FIM respondeu
                                         │      └ rejeitar | expirou ──► finalizar_b ══▶ FIM rejeitado|expirou
                                         └ aprovou, COM indício
                                              preparar_moderacao ■[T grava anúncio aguardando_moderacao]
                                              ⏸ moderacao HUMANO (moderador, prazo 48 h)
                                              aplicar_moderacao ■[T escrita idempotente]
                                                   ─► finalizar_b ══▶ FIM respondeu|rejeitado|expirou

   finalizar_b ■código: escreve MEMÓRIA (1 extração ◆MODELO para o episódio) e monta a saída
```

**Onde fica cada coisa, no desenho:** a **memória** é lida em `iniciar_b` e
escrita em `finalizar_b`; o **índice** do RAG é lido em `buscar_regras` e
`ferramenta_regras`; o **checkpoint** é gravado a cada super-passo (todo o
diagrama), e é ele que torna possíveis os dois `⏸`; as **condições de parada**
são os `══▶ FIM`, e a taxonomia completa está em §3.2 ("o término").

**A decisão que só o modelo toma em tempo de execução** (§3.3): o `◆` de
`agente_b` — qual a próxima ação, dado o que o vendedor acabou de dizer.
Os outros `◆` (triagem, interpretar, montar, avaliador, responder, extração)
são decisões de **uma volta**: classificam ou escrevem, e o código decide o
que vem depois.

## 6.4 A conferência contra o código

Comando, na raiz, com o código do commit `3848cc4`:

```
python conferir_grafo.py
```

Ele importa `GRAFO` de `src/grafo.py` — o mesmo objeto que `src/sistema.py`
invoca, e o script afirma isso com `assert GRAFO is GRAFO_DO_SISTEMA`. Saída
(a lista de nós foi juntada em linhas aqui; o script imprime um por linha):

```
NÓS (31):
  __start__ · entrada · triagem · desambiguar · fora_escopo · buscar_regras ·
  responder_regras · recusar_sem_base · iniciar_b · agente_b · perguntar_b ·
  ferramenta_preco · ferramenta_regras · portao_avaria · avaliador ·
  recusar_item · preparar_aprovacao · aprovacao_vendedor · publicar ·
  registrar_indicio · preparar_moderacao · moderacao · aplicar_moderacao ·
  finalizar_b · iniciar_a · interpretar_compra · completar_pedido ·
  buscar_categoria · montar_sugestao · perguntar_a · __end__

ARESTAS (52) — [cond] = condicional:
  __start__ -> entrada
  agente_b -> ferramenta_preco   [cond]
  agente_b -> ferramenta_regras   [cond]
  agente_b -> finalizar_b   [cond]
  agente_b -> perguntar_b   [cond]
  agente_b -> portao_avaria   [cond]
  agente_b -> recusar_item   [cond]
  agente_b -> registrar_indicio   [cond]
  aplicar_moderacao -> finalizar_b
  aprovacao_vendedor -> finalizar_b   [cond]
  aprovacao_vendedor -> publicar   [cond]
  avaliador -> agente_b   [cond]
  avaliador -> finalizar_b   [cond]
  avaliador -> preparar_aprovacao   [cond]
  avaliador -> preparar_moderacao   [cond]
  buscar_categoria -> montar_sugestao
  buscar_regras -> recusar_sem_base   [cond]
  buscar_regras -> responder_regras   [cond]
  completar_pedido -> buscar_categoria   [cond]
  completar_pedido -> perguntar_a   [cond]
  desambiguar -> __end__
  entrada -> agente_b   [cond]
  entrada -> interpretar_compra   [cond]
  entrada -> triagem   [cond]
  ferramenta_preco -> agente_b   [cond]
  ferramenta_preco -> perguntar_b   [cond]
  ferramenta_regras -> agente_b
  finalizar_b -> __end__
  fora_escopo -> __end__
  iniciar_a -> interpretar_compra
  iniciar_b -> agente_b
  interpretar_compra -> completar_pedido
  moderacao -> aplicar_moderacao
  montar_sugestao -> __end__
  perguntar_a -> __end__
  perguntar_b -> __end__
  portao_avaria -> agente_b   [cond]
  portao_avaria -> avaliador   [cond]
  portao_avaria -> perguntar_b   [cond]
  preparar_aprovacao -> aprovacao_vendedor
  preparar_moderacao -> moderacao
  publicar -> finalizar_b
  recusar_item -> agente_b   [cond]
  recusar_item -> finalizar_b   [cond]
  recusar_sem_base -> __end__
  registrar_indicio -> agente_b
  responder_regras -> __end__
  triagem -> buscar_regras   [cond]
  triagem -> desambiguar   [cond]
  triagem -> fora_escopo   [cond]
  triagem -> iniciar_a   [cond]
  triagem -> iniciar_b   [cond]
```

**Desenho × código:** os 29 nós do desenho são os 29 do código (mais
`__start__`/`__end__`), e as 52 arestas batem uma a uma. Duas
simplificações do desenho, em que vale o código: (1) os caminhos
`entrada → agente_b` e `entrada → interpretar_compra` (conversa em
andamento) aparecem como as setas laterais da triagem; (2) o `Send` aparece
na conferência como uma aresta condicional `completar_pedido ->
buscar_categoria` — o framework não desenha um ramo por categoria, porque o
número de ramos só existe em tempo de execução.

## 3.2 As seis perguntas

### As ferramentas

| Ferramenta | Nó | O que faz | Leitura / escrita | Reversível? |
|---|---|---|---|---|
| preço de mercado | `ferramenta_preco` | faixa de `precos_comparaveis` por categoria + bairro; sem dados devolve `erro: sem_comparaveis` (dado, não exceção) | leitura | — |
| regras (RAG) | `ferramenta_regras`, `buscar_regras` | 3 trechos do corpus + portão de similaridade | leitura | — |
| catálogo | `buscar_categoria` | itens **ativos**, de outros vendedores, até o teto de preço, ordenados por distância | leitura | — |
| cliques | `completar_pedido` | o que o comprador abriu recentemente (só quando o texto não diz o que procura) | leitura | — |
| registrar indício | `registrar_indicio` | indício de avaria para a moderação | escrita, idempotente | sim — a moderação decide e pode descartar |
| publicar | `publicar` | grava o anúncio `ativo` | escrita, idempotente | sim para o vendedor (pausa/edita); **não** para o mundo (já foi visto) — por isso o `⏸` |
| gravar aguardando moderação | `preparar_moderacao` | grava o anúncio `aguardando_moderacao` (fora das buscas) | escrita, idempotente | sim |
| aplicar moderação | `aplicar_moderacao` | ativa, ativa com aviso, ou rejeita | escrita, idempotente | sim |
| memória | `iniciar_b` (lê), `finalizar_b` (escreve) | episódica, semântica, fila procedural | escrita **só pelo código** | sim — decaimento e remoção (`docs/memoria.md`) |

O modelo **não** tem ferramenta de escrita direta: ele escolhe `registrar_indicio`
ou `recusar_item`, e o código executa com as conferências. Publicar não é ação
dele.

### O laço

Só o Agente B tem laço. A cada volta: (1) o código confere os quatro tetos;
(2) o modelo recebe a conversa (recortada, `docs/memoria.md` P2.5), a última
observação de cada ferramenta, o rascunho atual, o que o código sabe sobre
avaria e a memória — e escolhe **uma** ação; (3) o código confere o laço;
(4) a ação roda. **O que faz a volta seguinte existir:** uma observação nova
que muda o que falta — a faixa de preço chegou, a regra foi consultada, o
indício foi registrado, o avaliador apontou o que falta. **O que encerra a
volta sem encerrar a conversa:** `perguntar` — o turno acaba esperando o
vendedor, e a próxima fala dele volta direto para `agente_b`
(`conversa_aberta = "anuncio"`).

### O estado

Objeto explícito e tipado (`src/estado.py`); a tabela campo a campo está em
§7.1 abaixo. Na lista de mensagens ficou só o texto da conversa. Decisões,
contadores, ids e resultados de ferramenta são campos.

### O orçamento

| Teto | Valor | Onde | O que acontece |
|---|---|---|---|
| passos (decisões do modelo por anúncio, somando turnos) | **12** | `B_MAX_PASSOS`, `checar_orcamento` | `desfecho = orcamento` |
| tokens (por thread) | **60.000** | `B_MAX_TOKENS` | idem |
| dinheiro (por thread, pela tabela paga) | **US$ 0,02** | `B_MAX_CUSTO_USD` | idem |
| tempo (por turno, relógio de parede) | **120 s** | `B_MAX_SEGUNDOS_TURNO` | idem |
| rodadas do avaliador | **3** | `B_MAX_RODADAS_AVALIADOR` | `desfecho = avaliador_reprovou` |
| repetição | **3x** a mesma ação com os mesmos argumentos | `LACO_REPETICOES` | `desfecho = laco` |
| timeout por chamada ao modelo | **30 s**, 3 repetições em erro recuperável | `LLM_TIMEOUT_S` | recuperável esgotado → `erro_fatal` |
| super-passos do grafo (rede de segurança) | **60** | `RECURSION_LIMIT` | `GraphRecursionError` |
| Agente A | **estrutural**: workflow sem laço, no máximo 2 chamadas de modelo por turno e 4 ramos | `A_MAX_CATEGORIAS` | — |
| humano | **24 h** (vendedor), **48 h** (moderador) | `PRAZO_*` | `expirou` |

Os tetos de tokens e de tempo do Agente A na v1 (20.000 / 20 s) **saíram**:
com o A virando workflow, nada no grafo os consumiria — deixá-los em
`config.py` seria declarar um teto que não existe.

### O término

A taxonomia completa (`Termino` em `src/contrato.py`), com o que a produz:

| Término | Quando | Quem produz |
|---|---|---|
| `aguardando_usuario` | o turno acabou com uma pergunta; a conversa continua | `perguntar_b`, `perguntar_a`, `desambiguar` |
| `aguardando_humano` | o grafo está num `interrupt` | `aprovacao_vendedor`, `moderacao` |
| `respondeu` | o objetivo foi cumprido: anúncio no ar, sugestão montada, dúvida respondida | `finalizar_b`, `montar_sugestao`, `responder_regras` |
| `recusou` | fora do escopo; sem base no corpus; item proibido; nenhum item ativo | `fora_escopo`, `recusar_sem_base`, `responder_regras`, `finalizar_b`, `montar_sugestao` |
| `rejeitado` | a pessoa disse não (o vendedor ou a moderação) | `finalizar_b` |
| `expirou` | o prazo do humano venceu (ou a resposta chegou tarde) | `finalizar_b`, via `rotina_prazos` |
| `orcamento` | passos, tokens, dinheiro, tempo ou 3 reprovações do avaliador | `finalizar_b` |
| `laco` | a mesma ação com os mesmos argumentos 3x | `finalizar_b` |
| `erro_fatal` | erro do provedor não recuperável, ou recuperável esgotado | `src/sistema.py` (`_erro`) |

Todo término grava `motivo_termino` em texto (ex.: `"a ação 'consultar_preco'
com os mesmos argumentos 3x seguidas"`).

### O humano

Dois pontos de parada, dois perfis, dois prazos, e o silêncio tem caminho
declarado — **não publica**. Detalhes em `docs/humano.md`.

| Onde | Quem | Prazo | Silêncio |
|---|---|---|---|
| `aprovacao_vendedor` | o vendedor dono da conversa | 24 h | não publica; o rascunho fica salvo |
| `moderacao` | um moderador (`M-…`) | 48 h | não publica; anúncio rejeitado; vendedor avisado |

## 3.3 A defesa do nível de autonomia

**Nível do sistema: router na entrada; agente no B; workflow no A.** A regra é
a menor autonomia que resolve, então a defesa é por parte:

- **Router (`triagem`), e não uma sequência:** a entrada é texto de qualquer
  pessoa. "Posso vender uma réplica de airsoft?" e "quero vender uma réplica de
  airsoft" levam a rotas diferentes (dúvida × anúncio) — a mensagem de
  fronteira do teste da triagem e o caso 14. Não há campo para o código ler.
- **Agente (`agente_b`), e não workflow:** o `◆` de `agente_b` no diagrama.
  Os casos produzem sequências diferentes de ação (tabela em `docs/grafo.md`
  §6.2): o caso 2 precisa de uma pergunta a mais (o preço) que o caso 1 não
  precisa; o caso 4 registra indício antes de qualquer rascunho; o caso 14
  nunca pergunta nada. Um workflow fixo acerta só o caminho feliz.
- **Workflow no A, e não agente:** com o texto do comprador, nenhuma decisão
  dependeu do resultado de uma busca para escolher a próxima. **É um
  resultado legítimo e está declarado**: o A desceu de degrau em relação à v1.

E o que **não** é decisão do modelo, mesmo dentro do agente: publicar, o
portão de avaria, o preço fora da faixa, a parada por laço e por orçamento —
tudo código.

## 7.1 O estado — os campos, e quem mexe em cada um

`src/estado.py`. Campo escrito por mais de um nó tem reducer, ou é escrito em
caminhos exclusivos (os nós nunca rodam no mesmo super-passo).

| Campo | Tipo | Quem escreve | Quem lê | De onde veio |
|---|---|---|---|---|
| `thread_id`, `usuario_id`, `sessao_id` | str | `sistema.conversar` (entrada do grafo) | todos | a sessão do site (não digitado) |
| `texto_turno` | str | `sistema.conversar` | `entrada`, `iniciar_b`, `buscar_regras`, `ferramenta_regras` | a pessoa |
| `mensagens` | list, **reducer +** | `entrada`, `perguntar_*`, `desambiguar`, `fora_escopo`, `responder_regras`, `recusar_sem_base`, `montar_sugestao`, `finalizar_b` | `triagem`, `agente_b`, `avaliador`, `interpretar_compra`, `avaria_da_conversa` | a conversa |
| `rota`, `leituras`, `categoria_mencionada` | str / list | `triagem` | `rotear_triagem`, `desambiguar`, `iniciar_b` | modelo |
| `escolha_declarada` | str | `triagem` (zera), `completar_pedido` | `saida()` | código |
| `conversa_aberta` | str | `perguntar_b`, `perguntar_a` (abrem); os nós finais (fecham) | `rotear_entrada` | código |
| `msg_inicio`, `passos_inicio` | int | `iniciar_b`, `iniciar_a` | `agente_b`, `avaria_da_conversa`, `checar_orcamento` | código |
| `decisao_b` | dict | `agente_b` | `rotear_b` e as ferramentas do B | modelo |
| `faixa_preco` | dict | `ferramenta_preco`; `iniciar_b` (zera) | `agente_b`, `checar_preco`, `finalizar_b` | banco |
| `regras_consultadas` | list | `ferramenta_regras`, `recusar_item` (aviso); `iniciar_b` | `agente_b`, `recusar_item`, `finalizar_b` | corpus |
| `indicio` | dict | `registrar_indicio`; `iniciar_b` | `avaliador`, `rotear_avaliador`, `preparar_moderacao`, `aplicar_moderacao`, `finalizar_b` | banco |
| `pergunta_portao` | str | `portao_avaria`; `entrada`, `perguntar_b` (zeram) | `perguntar_b`, `rotear_portao` | código |
| `rascunho` | dict | `portao_avaria`, `publicar` (aplica edições); `iniciar_b` | `avaliador`, `preparar_*`, `finalizar_b` | modelo |
| `avaliacao`, `rodadas_avaliador` | dict / int | `avaliador`, `portao_avaria` (erro de contrato); `iniciar_b` | `rotear_avaliador`, `agente_b` | modelo + código |
| `pendencia` | dict | `preparar_aprovacao`, `preparar_moderacao` | `aprovacao_vendedor`, `moderacao` | código |
| `decisao_humana` | dict | `aprovacao_vendedor`, `moderacao`; `entrada` (zera) | `rotear_aprovacao`, `publicar`, `aplicar_moderacao`, `finalizar_b` | humano |
| `desfecho` | str | `agente_b`, `avaliador`, `recusar_item`, `publicar`, `aplicar_moderacao`, `finalizar_b` | `rotear_b`, `rotear_avaliador`, `rotear_recusa`, `finalizar_b` | código — **um por caminho**: nenhum par desses nós roda no mesmo super-passo |
| `pedido` | dict | `interpretar_compra`, `completar_pedido`; `iniciar_a` | `rotear_pedido`, `montar_sugestao` | modelo + código |
| `candidatos` | list, **reducer + com limpeza** | `buscar_categoria` × N **em paralelo**; `iniciar_a`, `interpretar_compra` (zeram) | `montar_sugestao` | banco |
| `sugestao` | dict | `montar_sugestao` | `iniciar_a` (refinamento) | modelo + código |
| `trechos_rag`, `rag_portao` | list / dict | `buscar_regras`, `ferramenta_regras` | `rotear_portao_rag`, `responder_regras`, `recusar_sem_base` | corpus |
| `consultas_rag` | int, **reducer soma** | `buscar_regras`, `ferramenta_regras` | logs (`docs/rag.md` §4.4) | código |
| `memoria` | dict | `iniciar_b` | `agente_b`, `portao_avaria` | memória |
| `passos`, `tokens`, `custo_usd` | int / float, **reducer soma** | todo nó que chama o modelo (incremento) | `checar_orcamento`, logs | código |
| `inicio_turno` | float | `entrada` | `turno_estourou` | relógio |
| `trajetoria` | list, **reducer +** | todos | `detectar_laco`, logs | código |
| `escritas` | dict, **reducer merge** | `publicar`, `registrar_indicio`, `preparar_moderacao` | `aplicar_moderacao`, `finalizar_b` | banco |
| `termino`, `motivo_termino`, `saida` | str / dict | os nós finais (via `saida()`); `entrada` (zera) | `src/sistema.py` | código |

O que **não** está no estado (derivado, e por quê) está em `docs/grafo.md` §7.3.

---

## O que sobreviveu do desenho v1, e o que mudou

| v1 (Parte 1) | v2 (Parte 2) | Por quê |
|---|---|---|
| dois agentes independentes, laço escrito à mão | um grafo LangGraph com os dois e uma rota de dúvidas | §6 do enunciado; o checkpoint e o `interrupt` vieram do framework |
| Agente A: **agente** sobre eventos de clique; "sem router: entrada homogênea" | Agente A: **workflow** sobre texto; **router** na entrada do sistema | a entrada passou a ser texto livre de qualquer pessoa (§1.1) — heterogênea |
| Agente B: AGENTE + AVALIADOR; `publicar` era ação do modelo | AGENTE + PORTÃO + AVALIADOR; publicar é aresta em código depois de um `⏸` | o modelo errava nos dois sentidos (Parte 1); publicar é ação para o mundo |
| "nenhuma escrita irreversível; avaria negada → registra e segue" | avaria negada → **não publica** até a moderação decidir | o caso 4 da v1 já dizia "não publicar silenciando"; a política de moderação escrita nesta entrega fixa isso |
| `MIN_SINAL = 3` cliques para acionar o A | cliques só como sinal auxiliar, quando o texto não diz o que procura | a entrada é texto |
| quatro formas de terminar | nove (`Termino`) | conversa com vários turnos e humano com prazo pedem `aguardando_*`, `rejeitado`, `expirou`, `recusou` |
| tetos do A (6 passos, 20 mil tokens, 20 s) | teto estrutural | o A não tem laço |
| tetos do B (12 / 60 mil / 120 s / 3 rodadas / US$ 0,01) | os mesmos, com US$ 0,02 (outra tabela de preço) e o detector de laço declarado | sobreviveu |

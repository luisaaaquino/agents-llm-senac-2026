# O plano de prompt engineering (§2)

Este documento é **raciocínio sobre o projeto**; os prompts são **fonte** e
moram em `src/prompts/`, um arquivo por versão, carregados em tempo de execução
por `llm.carregar_prompt` (`src/llm.py`). Cada arquivo tem duas partes,
separadas por uma linha `---`: o corpo, que vai para o modelo, e a ficha
(técnica, contrato, como é testada, changelog), que fica só para o histórico —
o carregador corta tudo depois do primeiro `---`.

**Cada execução registra a combinação em uso** (§2.2): o carimbo de todo log
(`carimbo.prompts`) traz o nome e o hash (sha256, 12 caracteres) de cada prompt
carregado naquela execução, junto com o commit, o modelo e o estado da memória.

## 2.1 Uma linha por etapa em que o modelo é chamado

Os testes são de `scripts/testar_prompts.py`; os resultados, de
`logs/medicoes/prompts_<etapa>.json` (gemini-3.5-flash-lite, temperatura 0).

| Etapa (nó · prompt) | Técnica | Por que ela | Contrato de saída | Como é testada · resultado |
|---|---|---|---|---|
| **triagem** · `triagem` → `triagem-v2.md` | zero-shot, saída estruturada | rotas poucas e estáveis, mas a fronteira "posso vender X?" (dúvida) × "vendo X" (venda) é julgamento sobre texto livre; exemplos não foram necessários (o teste passou sem eles) | `Triagem`: `rota` ∈ {vender, comprar, duvida, ambigua, fora_escopo}; `leituras` ⊂ {vender, comprar, duvida} só em ambígua; `categoria` ∈ vocabulário de `db.CATEGORIAS` ou null; `motivo`. **Proibido:** texto de resposta ao usuário | 10 mensagens rotuladas (6 claras, 4 de fronteira); critério 6/6 e ≥ 3/4 · **6/6 e 4/4** |
| **decisão do anúncio** · `agente_b` → `agente-anuncio-v9.md` | ReAct (uma ação por volta), zero-shot, saída estruturada | a próxima pergunta depende da resposta anterior e do que a ferramenta devolveu; a avaria não vem no 1º turno | `DecisaoAnuncio`: `acao` ∈ {perguntar, consultar_preco, consultar_regras, preencher_rascunho, registrar_indicio, recusar_item} + os campos da ação; `categoria`/`bairro` de vocabulário fechado; `rascunho.estado_conservacao` ∈ 4 estados. **Proibido:** publicar (não é ação); defeito ou preço sem base na conversa; preço alto tratado como avaria; repetir `consultar_preco`; recusar sem regra consultada | os casos do Agente B em `src/casos.py` + 3 repetições do caso 2; critério: todo caso no término esperado e o caso 4 nunca publicado escondendo o defeito · **9/9 casos do Agente B no término esperado** (rodada final, commit `1a5cd36`; os 15 casos do sistema: 15/15); caso 2 repetido 3x: **3/3**. Antes das correções em código, o caso 2 falhou em 2 rodadas (laço) e em 2 de 3 repetições (indício falso) — `logs/medicoes/` |
| **avaliação do rascunho** · `avaliador` → `avaliador-anuncio-v4.md` | verificador com critério booleano (avaliador-otimizador), zero-shot | separa quem escreve de quem confere; os critérios restantes no modelo são só os de texto (preço e avaria foram para o código) | `Avaliacao`: 5 booleanos (`tem_titulo`, `tem_categoria`, `tem_descricao`, `estado_coerente`, `sem_invencao`), `aprovado`, `faltando` ("critério: correção"). Entrada inclui `indicio_registrado`. **Proibido:** reescrever o rascunho; `aprovado` é recalculado em código | 8 rascunhos rotulados (4 bons, 4 com um defeito cada, incluindo "defeito fora da descrição com indício registrado" e "inventa 'sem defeito'"); critério 8/8 · **8/8** |
| **resposta sobre regras** · `responder_regras` → `resposta-regras-v1.md` | zero-shot com contexto recuperado e citação obrigatória | a resposta tem de ser conferível trecho a trecho, e recusar quando os trechos não bastam | `RespostaRegras`: `resposta` (1–3 frases), `citacoes` (ids), `base_suficiente`. **Proibido:** id fora dos trechos (o código remove); conhecimento de fora | as 15 perguntas de `dados/perguntas_rag.json`, ponta a ponta (busca + portão + resposta); critério: respondíveis com a citação esperada, Q13/Q15 recusadas · **15/15** |
| **interpretação do pedido** · `interpretar_compra` → `compra-interpretar-v1.md` | zero-shot, extração | decidir quais categorias uma intenção pede ("montar a cozinha") é o julgamento que só o modelo faz; o resto é consulta | `PedidoCompra`: `categorias` ⊂ vocabulário (Literal), da mais para a menos importante; `orcamento_total`/`preco_max_item`/`bairro` só se ditos; `faltando` ⊂ {o_que_procura}; `ambiguidade`, `escolha`. **Proibido:** escolher produto; inventar valor | 8 pedidos rotulados (inclui "oi" e "quarto do bebê", que não tem categoria certa); critério: categorias certas 7/8 e nenhum valor inventado 8/8 · **8/8 e 8/8** |
| **montagem da sugestão** · `montar_sugestao` → `compra-sugestao-v1.md` | zero-shot, saída estruturada | escolher o conjunto é uma troca entre preço, distância e orçamento que depende da intenção dita | `Sugestao`: `itens_ids`, `justificativa`, `categorias_de_fora`. **Proibido:** id fora dos candidatos; soma acima do orçamento (os dois conferidos em código) | 6 cenários de candidatos; mede o modelo **antes** e o sistema **depois** da conferência · modelo: **6/6** sem id inventado, **5/6** dentro do orçamento (escolheu R$ 710 num orçamento de R$ 700); depois da conferência: **6/6** |
| **resumo do episódio** · `finalizar_b` → `extracao-memoria-v1.md` | zero-shot, sumarização de campos estruturados | o episódio é recuperado por similaridade, então precisa ser texto; montá-lo da descrição escrita pelo modelo traria a alucinação do caso 4 da Parte 1 para a memória | `ResumoEpisodio`: `resumo` (≤ 40 palavras). **Proibido:** dado pessoal, fala literal (o código aplica `filtrar_pii` depois) | os episódios gravados pelos casos; critério: a varredura de `scripts/verificar_remocao.py` não acha o id de teste nem dado pessoal · 14 episódios gravados na rodada final: **0** com dado pessoal (varredura com os mesmos padrões de `filtrar_pii`), todos com 9–18 palavras; e a varredura de remoção: **OK**. Achado: o resumo **varia entre execuções** — por isso ele deixou de fazer parte da chave do episódio (`docs/memoria.md` P2.2) |

**O que a coluna "contrato" não garante, e quem garante:** o schema Pydantic
fecha o formato e os valores enumeráveis (`Literal`). Ele não garante que o
valor seja o certo — por isso cada etapa tem uma conferência em código logo
depois: `aprovado` é recalculado como o E lógico dos critérios; ids da sugestão
e citações do RAG são conferidos contra o que foi de fato recuperado; a soma da
sugestão é conferida contra o orçamento; `recusar_item` e `registrar_indicio`
só valem ancorados (numa regra consultada, numa fala do vendedor). Os casos em
que essas conferências pegaram o modelo estão em `docs/grafo.md` §6.3.

### O histórico das versões (os changelogs estão em cada arquivo)

| Prompt | Versões | O que cada mudança corrigiu |
|---|---|---|
| `agente-anuncio` | v1–v6 (Parte 1), **v7, v8, v9** | v7: migração para o grafo — saíram `publicar`/`concluir` (viraram arestas em código), entrou `consultar_regras`; a regra "pergunte de avaria" virou portão em código. v8: entrou `recusar_item` (não havia como recusar item proibido) e os gatilhos de `consultar_regras`. v9: **voltou** a frase "consulte o preço uma única vez" (ver §2.3) |
| `avaliador-anuncio` | v1–v2 (Parte 1), **v3, v4** | v3: `preco_na_faixa` saiu do modelo para o código; entrou `sem_invencao`. v4: o avaliador passou a receber `indicio_registrado` — sem isso, ele oscilava entre exigir e proibir o defeito no caso 4 |
| `triagem` | **v1, v2** | v2: saiu uma frase que não fazia nada (§2.3) |
| `resposta-regras` | v1 | — |
| `compra-interpretar` | v1 | — (substitui o `consultor-compra.md` do site, que lia cliques) |
| `compra-sugestao` | v1 | — |
| `extracao-memoria` | v1 | — |
| `procedural` | — | memória procedural, não prompt de etapa: 3 regras aprovadas pelo grupo, anexadas ao system prompt do Agente B (`docs/memoria.md`) |

## 2.3 A regra da frase

> Se vocês apagarem uma frase do prompt e não souberem dizer o que ela
> impedia, ela não estava fazendo nada.

Fizemos o exercício duas vezes nesta entrega — uma de propósito e outra sem
querer —, e os dois resultados apontam em sentidos opostos.

### 1. A frase que saiu e não fez falta — `triagem` v1 → v2

**A frase:** *"Perguntar 'posso vender X?' ou 'é permitido anunciar X?' é
`duvida` (é sobre a regra), não `vender`."*

**O experimento** (`python scripts/testar_prompts.py frase`, log em
`logs/medicoes/prompts_regra_da_frase.json`): as 10 mensagens rotuladas da
triagem rodaram com a v1 inteira e com a v1 sem a frase.

| | claras (6) | fronteira (4) | mensagens que mudaram de rota |
|---|---|---|---|
| v1 com a frase | 6/6 | 4/4 | — |
| v1 **sem** a frase | 6/6 | 4/4 | **0** |

**O que aconteceu:** nada. As 10 mensagens — inclusive "posso vender uma
réplica de pistola de airsoft?" e "é permitido anunciar remédio?", que são
exatamente o que a frase descrevia — saíram na mesma rota. A frase não impedia
nada que a descrição de `duvida` já não impedisse.

**Ela voltou?** Não: a v2 é a v1 sem a frase, e é a que o sistema usa. O que
substitui a frase é a descrição da própria rota `duvida` ("o que pode ser
anunciado"). **Risco declarado:** o teste tem só duas mensagens do tipo "posso
vender X?"; se a fronteira falhar com outro modelo, a frase é a primeira
candidata a voltar.

### 2. A frase que saiu e fez falta — `agente-anuncio` v6 → v7 → v9

**A frase:** *"Chame `consultar_preco` uma única vez; o primeiro resultado já é
a resposta final."* (estava na v4–v6).

**O que aconteceu:** saiu na v7, com o argumento de que o detector de laço e a
memória procedural cobriam o caso. Nas rodadas de desenvolvimento, nenhum caso
repetiu a consulta. Na rodada final com a v8, **o caso 2 repetiu
`consultar_preco` 3x** e terminou em `laco`
(`logs/medicoes/02_divergencia_preco_v8_laco.json`). O argumento estava errado
em duas partes: a regra procedural só cobre `sem_comparaveis`, e o detector
**para** o laço, não o **evita**.

**Ela voltou?** Voltou, na v9 — e **não bastou**: com a v9 o caso 2 entrou em
laço do mesmo jeito (`…_v9_laco.json`). O motivo que o modelo escreveu na
repetição mostrou o defeito real: *"consultar o preço de mercado para
apresentar ao usuário"* — ele queria avisar o vendedor da faixa e não ligava
isso a `perguntar`. A correção que resolveu foi em código: consulta repetida
não vai ao banco e vira a pergunta com a faixa (`docs/grafo.md` §6.3). A frase
continua na v9, porque o defeito que ela descreve existe; mas a lição do
exercício é que **saber o que a frase impedia não garante que ela impeça**.

## 2.2 Onde os prompts estão, e o que não está em arquivo

- `src/prompts/*.md` — os 7 prompts de etapa em uso (`triagem-v2`,
  `agente-anuncio-v9`, `avaliador-anuncio-v4`, `resposta-regras-v1`,
  `compra-interpretar-v1`, `compra-sugestao-v1`, `extracao-memoria-v1`), as
  versões anteriores preservadas (as da Parte 1 movidas da raiz com `git mv`,
  para o histórico vir junto) e a memória procedural.
- **O que não é prompt de arquivo, de propósito:** as perguntas que o **código**
  impõe — a do portão de avaria (`portao_avaria`) e o aviso da faixa de preço
  (`ferramenta_preco`) — e os textos da pausa humana (`preparar_aprovacao`,
  `preparar_moderacao`). São templates preenchidos com dados, não instruções a
  um modelo; vivem no código que os monta, e mudam com ele.

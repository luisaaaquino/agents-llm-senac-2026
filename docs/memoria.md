# Memória do agente — Santo Desapego (§5 da Parte 2)

> **Parte 2: implementado.** As Decisões 1 e 2 abaixo são as do exercício 8
> (Aula 08), mantidas como foram escritas. O que mudou na implementação, as
> medições e a gestão da conversa (§5.5) estão na seção **Parte 2 — o que foi
> implementado**, no fim. Código: src/memoria.py, src/remocao.py,
> scripts/demo_memoria.py, scripts/verificar_remocao.py.
>
> Texto original do exercício 8: documento de **decisão**: nada aqui foi
> implementado ainda — a implementação é o exercício complementar. Onde há número, ele vem
> marcado como **[medido]** (tirado dos logs reais da Parte 1, `qwen2.5:7b`
> via Ollama) ou **[projeção]** (estimativa declarada, a medir na
> implementação).
>
> **Escopo:** o documento trata do **Agente B (assistente de anúncio)**, que é
> o agente que existe em código. O Agente A (consultor de compra) tem uma
> decisão só, e ela é negativa — ver §1.5.

---

## Decisão 1 — Como o agente lembra

### 1.1 Os dois níveis, no domínio do case

| | Curto prazo | Longo prazo |
|---|---|---|
| **O que é** | a janela de contexto de **um** anúncio sendo montado | o que atravessa anúncios: de um vendedor para o próximo anúncio dele, e de um vendedor para outro |
| **Conteúdo no case** | prompt `agente-anuncio-vN.md`, objetivo ("montar um anúncio completo e honesto"), a conversa com o vendedor, as observações das ferramentas (faixa de preço, veredito do avaliador), o rascunho atual e os trechos da política de moderação (RAG) | **episódica:** como terminaram anúncios parecidos · **semântica:** fatos sobre o vendedor e sobre a categoria do produto · **procedural:** regras aprendidas com os erros do próprio agente |
| **Persistido como** | **checkpoint** — `checkpoints/{execucao_id}.json`, um arquivo por anúncio | índice vetorial (episódica), tabela SQLite `memoria_semantica` (semântica), arquivo `prompts/procedural.md` (procedural) |
| **Lido** | uma vez, na retomada (queda do processo ou decisão da moderação) | no início de cada anúncio, depois da 1ª fala do vendedor (é ela que diz a categoria e o bairro) |
| **Acesso** | por `execucao_id` | episódica por filtro + similaridade · semântica por chave · procedural inteira, sempre |
| **Ciclo de vida** | morre quando o anúncio é publicado ou a moderação decide | acumula, com decaimento (§2.2) e remoção (§2.3) |

**O que exatamente vai para o checkpoint.** Hoje o código **não grava
checkpoint**: o `Estado` de `src/agente_anuncio.py` vive só na memória do
processo, e o que chega mais perto é o log em `logs/*.json`. O checkpoint da
Parte 2 guarda:

| Campo | Por que precisa estar lá |
|---|---|
| `execucao_id`, `vendedor_id`, `objetivo` | identificar a execução e o titular (o titular é o que torna a remoção possível, §2.3) |
| `conversa` completa (falas do vendedor e perguntas do agente) | a evidência da avaria: se a moderação retoma o caso, precisa ver o que o vendedor disse, literalmente |
| `passos`: ação, argumentos, resultado, tokens | retomar sem repetir a consulta de preço nem a avaliação |
| `escritas`: `anuncio_id` publicado, `indicio_id` registrado | **não reaplicar efeito colateral** na retomada |
| `rascunho` atual e o último veredito do avaliador | a moderação decide sobre o rascunho que o vendedor viu, não sobre um novo |
| `orcamento` consumido (passos, tokens, custo, tempo) | a retomada continua o orçamento, não reinicia |
| `termino`, `motivo`, `pendencia` | a `pendencia` é o indício aguardando a moderação (termino `humano`) |
| `carimbo`: prompt × modelo × parâmetros × **estado da memória** (§2.4) | reproduzir a execução para depuração |

As três perguntas do enunciado, respondidas com esse conteúdo:

- **Retomar sem reaplicar efeito colateral?** Sim, com duas condições. O
  checkpoint é gravado **depois** de cada escrita, com o id que ela devolveu.
  E as duas escritas precisam de chave de idempotência derivada do conteúdo.
  `publicar_anuncio` já tem (título + bairro + preço, em `src/db.py`).
  `registrar_indicio_avaria` **não tem**: hoje, uma retomada registraria o
  mesmo indício duas vezes. Além disso, o `anuncio_ref` está fixo como
  `"rascunho-atual"`, então o indício nem aponta para o anúncio. As duas
  correções entram na Parte 2.
- **Aprovação humana horas depois, de outro processo?** Sim. É o caso
  `termino=humano`: o agente registra o indício, grava o checkpoint com a
  `pendencia` e encerra. O painel da moderação carrega o arquivo pelo
  `execucao_id` e grava a decisão. Nenhum passo do agente é refeito.
- **Carregar e reproduzir um estado defeituoso?** Sim, o **estado** é
  reproduzível. A **próxima decisão** a partir dele não é garantida: a Parte 1
  já mediu que o `qwen2.5:7b` não é determinístico mesmo em `temperature=0`
  (caso 1 rodado 3 vezes: 3, 5 e 5 passos, ver `docs/modelos.md` §3.3). A
  memória acrescenta uma terceira fonte de variação (§2.4).

### 1.2 O orçamento da janela

**[medido]** Uma chamada do agente hoje ocupa entre 1.792 e 2.071 tokens
(`logs/04_avaria_negada.json`). O prompt `agente-anuncio-v4.md` sozinho tem
cerca de 1.260 tokens. A memória e o RAG entram **por cima** disso, então o
teto é declarado por fonte:

| # | Fonte | Teto (tokens) | Base do número |
|---|---|---|---|
| 1 | System prompt (+ schema da decisão) | 1.400 | prompt v4 medido (~1.260) + folga para a v6 |
| 2 | Objetivo | 50 | uma frase fixa |
| 3 | Trajetória: conversa (8 últimas falas) + observações (4 últimas) + rascunho atual | 1.000 | é o que `rodar_agente` já recorta hoje (`conversa[-8:]`, `observacoes[-4:]`) |
| 4 | Trechos da política de moderação (RAG) | 400 | até 2 trechos de ~200 tokens |
| 5 | Memória de longo prazo | 300 | procedural ≤ 100 · semântica ≤ 60 · episódica ≤ 140 (2 episódios) |
| | **Total por chamada** | **3.150** | **[projeção]** ~+1.100 tokens por chamada em relação à Parte 1 |

**Quando o total estoura, o descarte segue esta ordem (primeiro sai o de cima):**

1. **Episódica**, a partir do episódio menos relevante. O agente funcionou
   sem ela na Parte 1 inteira, então é a fonte cuja falta dói menos.
2. **O 2º trecho do RAG.** O 1º fica.
3. **Observações antigas viram marcador** (*tool clearing*, nota 03 §5.2): o
   resultado de `consultar_preco` vira `"consultou geladeira/Santo Amaro ->
   300–380"`. A chamada fica registrada, porque apagá-la faz o agente repetir a
   consulta. É exatamente o laço do caso 3.
4. **Falas antigas da conversa**, **exceto** as que falam de estado ou avaria.
   Essas são marcadas por código, com o mesmo regex do plano B do
   `docs/case.md` §2.11 ("mas", "só não", "demora", "defeito"...).

**Nunca descartados:** system prompt, objetivo, memória procedural, rascunho
atual e as falas sobre avaria. A última é a decisão mais importante da
tabela. O truncamento ingênuo corta pelo começo da conversa, e é justamente
no começo que o vendedor costuma soltar o defeito ("ah, o freezer embaixo
demora pra congelar"). Perder essa fala é voltar ao caso 4 da Parte 1.

**O avaliador não recebe memória nenhuma.** Ele julga o rascunho contra o
checklist e nada mais. Se o avaliador lesse a mesma memória do agente, o
risco de ponto cego compartilhado (`docs/case.md` §2.11) ganharia mais uma
via: os dois seriam influenciados pelo mesmo episódio.

### 1.3 O longo prazo: as três memórias no case

| Tipo | O que guarda no case | Estrutura | Como é recuperada |
|---|---|---|---|
| **Episódica** | Como terminou cada anúncio, em fatos estruturados: *"[2026-09-20] geladeira duplex, Santo Amaro, pedido R$ 900 × faixa 300–380; vendedor manteve o preço; avaria: nenhuma; publicado"* · *"[2026-09-22] geladeira Consul, avaria no freezer inferior, vendedor recusou declarar; indício → moderação confirmou"*. Metadados: `data`, `categoria`, `bairro`, `vendedor_id`, `desfecho` (`publicado`/`moderacao`/`abandonado`), `avaria` (`nenhuma`/`declarada`/`negada`) | índice vetorial (Chroma, o mesmo da Aula 07) | **filtro por igualdade** em `categoria` (e `bairro`, se houver episódio suficiente), **depois** similaridade com a 1ª fala do vendedor; k=2; recência como desempate |
| **Semântica** | Fatos estáveis por entidade. **Vendedor:** `vendedor:V-017 / bairro_retirada = "Campo Grande"` · `vendedor:V-017 / aceita_sugestao_preco = false`. **Categoria:** `categoria:geladeira / avarias_tipicas = ["freezer inferior", "borracha de vedação", "compressor ruidoso"]` | chave-valor (tabela SQLite `memoria_semantica`: entidade, chave, valor, data, substituiu, fonte) | por chave, zero chamadas: `vendedor_id` já é conhecido ao abrir o chat e a categoria vem da 1ª fala |
| **Procedural** | Regras de como agir, tiradas de erros **reais** da Parte 1: *"se `consultar_preco` devolver `sem_comparaveis`, não repita a consulta"* (caso 3, laço) · *"pergunte sobre avaria antes do rascunho, mesmo quando a 1ª fala já traz produto, preço e bairro"* (casos 4 e 5) · *"use a grafia do vendedor na categoria, com acento"* (bug do "sofá") | texto em `prompts/procedural.md`, anexado ao system prompt | inteira, sempre (≤ 5 regras, ≤ 100 tokens) |

**Por que cada estrutura** (a estrutura decorre da consulta, não da
preferência):

- A pergunta da episódica é sobre **assunto**: "já houve um anúncio parecido
  com este?". Só o vetor responde. Os metadados existem por causa das
  cegueiras do embedding. `data` cobre a cegueira de tempo. `vendedor_id`
  cobre a de entidade e é o que viabiliza a remoção. `avaria` cobre a de
  negação: "avaria declarada" e "avaria negada" são quase o mesmo vetor, e
  aqui essa diferença é tudo.
- A pergunta da semântica é **"onde o V-017 retira o produto?"**. É uma
  chave primária composta. Buscar isso por similaridade custaria uma chamada
  de embedding para, na melhor das hipóteses, acertar o que um `SELECT`
  acerta sempre.
- A procedural é a **mais útil** para este case. O modo de falha principal da
  Parte 1 (pular a pergunta de avaria) é um problema de *como agir*, não de
  *o que aconteceu*. Pela mesma razão, é a mais perigosa (§1.4).

**O ganho que justifica o custo [projeção, a medir no complementar].** Com
`categoria:geladeira / avarias_tipicas` na janela, o agente passa a
perguntar *"o freezer de baixo congela normal?"* em vez de *"tem algum
defeito?"*. Pergunta específica faz o defeito aparecer mais do que pergunta
genérica, e o caso 4 é exatamente esse. A medida de sucesso: caso 4 com
memória termina em `humano`, sem memória termina em `respondeu`.

### 1.4 Quem escreve, e o que não entra

**Política de escrita: combinação por tipo, e o agente nunca escreve.**

| Tipo | Quem escreve | Como |
|---|---|---|
| Episódica | **o código extrai**, uma vez, ao fim da execução | 1 chamada com prompt versionado (`prompts/extracao-memoria-v1.md`) que monta o resumo a partir dos **campos estruturados** da trajetória (categoria, preço pedido, faixa, ação final, `anuncio_id`/`indicio_id`). A descrição que o modelo escreveu no rascunho não entra: no caso 4 ela afirmou "funciona perfeitamente", uma alucinação |
| Semântica | **o código**, por regra, **sem LLM** | `bairro_retirada` sai do rascunho **publicado**. `aceita_sugestao_preco` sai da comparação entre preço pedido e preço publicado. `avarias_tipicas` só recebe uma avaria depois que a **moderação confirma** o indício |
| Procedural | **o código propõe, o humano aprova** | execuções que terminam em `laco`, `orcamento` ou com o avaliador reprovando 3× geram uma **regra candidata** numa fila. O grupo (e depois a moderação) aprova ou descarta. Nada entra no system prompt sem revisão |

O agente **não recebe** uma ferramenta `lembrar`. Isso é restrição por
arquitetura, não por prompt. A Parte 1 mostrou que o `qwen2.5:7b` não segue
nem a regra "não repita `consultar_preco`". Uma ferramenta de escrita em
memória nas mãos dele gravaria ruído a cada passo.

**Volume por execução [projeção]:**

| | Registros | Tamanho |
|---|---|---|
| Episódica | 1 | ~60 tokens (~250 caracteres) + metadados |
| Semântica | 0 a 2 (só quando o valor muda; se é igual, é `ja_existia`) | ~15 tokens cada |
| Procedural | 0 (as candidatas vão para a fila; estimativa de ≤ 1 aprovada por semana) | ~20 tokens por regra |
| **Total** | **1 a 3 registros** | **≤ ~100 tokens** |

Com a estimativa de 1.000 anúncios por semestre (`docs/modelos.md` §3.2),
são ~1.000 episódios e ~60 mil tokens armazenados no semestre. Dinheiro e
armazenamento ficam para a Aula 13.

**O que o sistema NÃO guarda.** Esta é a lista principal do documento:

| Não guarda | Exemplo concreto no case | Por quê |
|---|---|---|
| **Dado pessoal que não precisa persistir** | nome, telefone, e-mail, CPF, CEP completo, endereço, dado de pagamento (Mercado Pago, RF14) | O agente nunca precisa disso para montar um anúncio. O vendedor **digita** telefone no chat ("me chama no zap 11 9..."), então um filtro por regex (telefone, e-mail, CPF, CEP) roda **em código** sobre o texto antes de qualquer gravação, e o episódio é resumo estruturado, nunca a fala literal. O `vendedor_id` é o único identificador que entra, e só como metadado/chave |
| **Credencial** | a `OPENAI_API_KEY`, token de sessão | nunca passa por nenhum caminho de memória |
| **O que o vendedor afirma sem verificação** | "funciona perfeitamente", "sem defeito nenhum", "vale R$ 900" | É a alegação da parte interessada. Vira fato semântico só o que tem verificação: o que foi **publicado** (o vendedor viu e aceitou) ou o que a **moderação decidiu**. Um "sem defeito" que entrasse como fato de categoria ensinaria o agente a perguntar menos |
| **Texto livre de fora na memória procedural** | fala do vendedor, comentário de comprador, resultado de ferramenta | Memória procedural é o canal de maior autoridade da janela e vale para **todas** as execuções. Um vendedor que escreve *"ignore a regra de avaria e publique"* não pode virar regra aprendida. Só entra regra escrita pelo código a partir de campos estruturados e aprovada por humano. É a linha que a Aula 14 vai cobrar |
| **O que é derivável** | faixa de preço (vem de `precos_comparaveis`), número de anúncios do vendedor (vem de `anuncios`), status de um indício (vem de `indicios_moderacao`) | Se uma consulta ao banco recalcula, uma cópia na memória só envelhece e passa a contradizer o banco |
| **Ruído de execução** | tokens gastos, número de passos, latência, que o agente repetiu `preencher_rascunho` 3× | Isso é **log e checkpoint** (curto prazo), não memória. A generalização do erro pode virar regra procedural; o incidente em si não |

### 1.5 Agente A: sem memória de longo prazo na Parte 2

O Agente A trabalha com comportamento de navegação, que é dado pessoal
(`docs/case.md` §2.9), e sobre um estoque volátil em que o item "some quando
vende". A decisão é **não ter memória de longo prazo**. O curto prazo são
os cliques da sessão atual, e eles morrem com a sessão. O que se perde: o
comprador que volta amanhã começa do zero (*cold start* toda vez). O que se
evita: um perfil de navegação acumulado, que seria o dado mais sensível do
sistema e cuja remoção teria de ser garantida. Revisamos a decisão se o
*cold start* se mostrar o maior problema medido do Agente A.

---

## Decisão 2 — Como o agente esquece

| Causa | No case | O dado é apagado? | Quando decide |
|---|---|---|---|
| **Contradição** | o vendedor mudou de bairro | não, o antigo fica como `substituiu` | na leitura |
| **Decaimento** | um episódio de mercado de 8 meses atrás | não: é rebaixado; apagado só depois de 1 ano | em rotina (semanal) |
| **Remoção** | o vendedor pede a exclusão dos dados (LGPD, art. 18) | sim, de **todas** as estruturas | sob demanda |

### 2.1 Contradição: o fato que mudou

**Os dois fatos verdadeiros, em datas diferentes:**

| Data | Fato |
|---|---|
| 2026-06-10 | "O vendedor V-017 retira os produtos em Santo Amaro." |
| 2026-09-02 | "O vendedor V-017 se mudou; passou a retirar em Campo Grande." |

Os dois respondem à mesma pergunta, e a resposta errada tem consequência
concreta. O `consultar_preco_comparaveis` filtra por **bairro**, então usar
Santo Amaro consulta o mercado do bairro errado e sugere um preço errado. O
anúncio também sai com o local de retirada errado, e o comprador vai até o
endereço antigo.

**O que a similaridade faz com eles.** Na episódica, os dois aparecem em
resumos quase idênticos ("V-017 anunciou geladeira, retirada em ..."), e a
pergunta "onde o V-017 retira?" fica igualmente próxima dos dois. O vetor
não representa anterioridade (cegueira de tempo, nota 02 da Aula 07, §5). Se
algo decidir a ordem, será o tempo verbal ("retira" no presente contra
"passou a retirar" no pretérito), e não a data. **[a medir no
complementar]**, com o formato de saída do enunciado.

**A regra de desempate, em código:**

1. **Carimbo de tempo obrigatório** em todo registro, como **metadado**
   (`data` ISO-8601), não como texto. Gravação sem `data` é recusada.
2. **Semântica:** a chave `vendedor:V-017 / bairro_retirada` é única. A
   gravação nova substitui a anterior e guarda o valor antigo em `substituiu`.
   Na leitura não há empate possível.
3. **Episódica:** quando os recuperados divergem sobre a mesma chave de fato,
   vence `max(data)`.
4. **A conversa atual vence a memória.** O que o vendedor diz **agora** tem
   carimbo de agora, então é o mesmo `max()` aplicado de forma consistente. A
   memória só pré-preenche a pergunta ("ainda retira em Campo Grande?"); ela
   não afirma.

**O descarte é registrado.** A função devolve `{"vigente": ...,
"descartados": [...]}`, e os descartados entram na trajetória como um passo
`memoria_desempate`. Se a moderação auditar um anúncio com o bairro errado,
o log distingue "o agente não sabia da mudança" (defeito) de "sabia e
descartou o antigo" (correto).

**Delegar ao modelo é o antipadrão, e nós já temos a prova.** O
`qwen2.5:7b` não segue de forma confiável nem "não repita a consulta de
preço". Pedir a ele que escolha entre duas datas custaria mais uma chamada,
erraria às vezes e não seria testável.

**O caso que o carimbo não resolve.** Um vendedor pode retirar em **dois**
lugares: móveis grandes em casa (Campo Grande), itens pequenos no trabalho
(Santo Amaro). Isso não é contradição. Um `max(data)` escolheria um dos dois
com a mesma confiança e erraria. Por isso o fato guarda a **condição de
aplicação**: `bairro_retirada` com `condicao: "itens grandes"`. Só vale
desempate por data entre registros com a mesma condição.

### 2.2 Decaimento: o fato que envelheceu

| Memória | Corte | Efeito | Justificativa no domínio |
|---|---|---|---|
| Episódica | **180 dias** | **rebaixa**: a pontuação é multiplicada por um fator de recência, e o episódio só entra na janela se não houver outro mais novo da mesma categoria | Mercado de usado muda por estação e por oferta local. Um semestre é o ciclo em que um vendedor ocasional volta a anunciar (mudança, troca de eletrodoméstico) |
| Episódica | **365 dias** | **remove** | custo: o crescimento é monotônico. Um episódio de mais de um ano sobre o preço/desfecho de um usado não informa mais nada que o banco não diga |
| Semântica (vendedor) | **180 dias** sem confirmação | **rebaixa para "a confirmar"**: o agente pergunta em vez de assumir ("ainda retira em Campo Grande?") | endereço e preferências de pessoa física mudam; vendedor amador fica meses sem anunciar |
| Semântica (categoria) | sem corte por idade | revisão quando a moderação reverter uma decisão | avaria típica de geladeira não envelhece em meses |
| Procedural | sem corte por idade | **sai quando vira código ou prompt**: se a regra foi incorporada à `agente-anuncio-vN+1.md`, ela deixa a memória | regra que já está no prompt, repetida na memória, é duplicação que diverge na primeira edição |

**Por que rebaixar e não apagar por idade:** o episódio raro é o valioso.
Bicicleta em Santo Amaro não tem comparáveis (caso 3). Um episódio de 7
meses sobre como um anúncio desses terminou pode ser o **único** precedente
do sistema, e apagar por idade jogaria fora justamente ele.

**A consequência para a remoção:** rebaixado **não é** apagado. Um episódio
rebaixado continua no índice, então a varredura da §2.3 precisa alcançá-lo.
É o motivo de o decaimento não ser contado como forma de cumprir a LGPD.

### 2.3 Remoção: o titular solicitou

O vendedor V-017 pede, pela política da plataforma (RF04 / LGPD art. 18), a
exclusão dos seus dados. O requisito é de **cobertura**: sair de todo lugar
onde o identificador caiu, não só das "três memórias".

**Inventário: onde o dado do vendedor cai.** A lista sai do sistema, não da
taxonomia:

| # | Estrutura | O que tem do titular | Como remove | Por que escapa com frequência |
|---|---|---|---|---|
| 1 | Episódica (índice vetorial) | episódios com `vendedor_id=V-017` | `delete(where={"vendedor_id": "V-017"})`, **sem reconstruir o índice** | — |
| 2 | Semântica (`memoria_semantica`) | `vendedor:V-017 / *` e o histórico em `substituiu` | `DELETE WHERE entidade = 'vendedor:V-017'` | o valor antigo em `substituiu` é esquecido |
| 3 | Procedural (`prompts/procedural.md`) + **fila de candidatas** | uma regra gerada a partir do erro dele poderia citar o id ou uma fala | varredura **textual** e edição humana | ninguém pensa em varrer o system prompt, nem a fila que ainda não virou regra |
| 4 | **Checkpoints** (`checkpoints/*.json`) | a conversa **literal** e os argumentos de cada passo | apaga o **arquivo inteiro** (um checkpoint editado não retoma nada) | não é "memória", então fica fora da conta |
| 5 | **Logs** (`logs/*.json`) | a conversa e o rascunho completos | apaga ou redige o arquivo da execução | é o lugar mais esquecido: foi feito para depurar, não para guardar |
| 6 | Tabela `anuncios` | título, descrição, bairro dos anúncios dele | fluxo de exclusão da plataforma (RF04). Hoje a tabela **não tem `vendedor_id`**: sem essa coluna, a remoção por titular não é possível. Entra na Parte 2 | é dado de negócio, fora do agente |
| 7 | Tabela `indicios_moderacao` | o texto do indício | **anonimiza** (desfaz o vínculo com o titular) em vez de apagar, se houver base legal para guardar o registro de moderação. **Decisão a validar com o grupo** | — |
| 8 | Provedor de LLM, se usar API na nuvem | a conversa enviada à Mistral | **fora do nosso controle** (retenção do provedor) | é um motivo concreto para o Ollama local (`docs/modelos.md` §3.4) |
| 9 | Backups do SQLite | tudo acima | expiram por rotação. Declarado aqui com o prazo, porque não dá para apagar item a item | — |

**A verificação é independente da remoção, e é ela a entrega:**

1. **Grava:** roda uma execução sintética com o titular de teste `V-TESTE`
   (um anúncio com avaria negada, que passa por todas as escritas: episódio,
   fato semântico, indício, checkpoint e log).
2. **Remove:** chama a rotina de remoção, que devolve quantos itens apagou
   em cada estrutura.
3. **Varre:** um script **separado**, que não reaproveita código da remoção,
   procura `V-TESTE` em cada estrutura do inventário por **dois
   critérios**: o metadado/chave **e** o texto, com `grep` no conteúdo dos
   documentos, dos JSONs e do `procedural.md`. O identificador pode estar no
   corpo de um resumo sem estar no metadado.
4. **Resultado esperado:** `OK — nenhum vestígio de V-TESTE nas 7
   estruturas locais`. Qualquer vestígio falha a verificação e lista onde
   estava. As estruturas 8 e 9 ficam fora da varredura automática e são
   declaradas como tal.

"Apaguei das três memórias" é uma afirmação. "Varri as 7 estruturas e não
encontrei" é a prova.

**O índice não precisa ser reconstruído.** O Chroma remove por filtro de
metadado, e é por isso que `vendedor_id` precisa ser metadado desde o
primeiro episódio. A remoção serve então para os três usos: privacidade,
custo **e recuperação de incidente**. Se um episódio envenenado entrar (por
exemplo, um resumo que carregou uma instrução escrita pelo vendedor), ele sai
por id sem esperar uma janela de manutenção.

### 2.4 O preço: o sistema deixou de ser reprodutível

Com memória, a mesma primeira fala (*"vendo geladeira consul, 380 reais,
Santo Amaro"*), no mesmo modelo e com os mesmos parâmetros, produz conversas
diferentes conforme o que já foi gravado:

| Memória | Comportamento esperado **[projeção, a medir no complementar]** |
|---|---|
| vazia (a Parte 1) | pergunta genérica ou nenhuma. A Parte 1 mediu que o agente **pulou** a pergunta de avaria nos casos 4 e 5 |
| com `categoria:geladeira / avarias_tipicas` | pergunta específica sobre o freezer inferior. É o comportamento que queremos, e é **diferente** do anterior |

Isso é consequência de projeto, escolhida na Decisão 1, e não defeito. O
sistema já tinha duas fontes de variação: o não determinismo do modelo
local, medido na Parte 1, e a mudança de prompt entre versões. A memória é a
terceira, e a pior para avaliar, porque muda sozinha a cada anúncio.

**O que muda na prática:**

- **Carimbo.** O `CARIMBO` de `src/agente_anuncio.py` ganha o **estado da
  memória**: `memoria_snapshot` (id do snapshot do índice e da tabela),
  `procedural_hash` (hash do `procedural.md`) e `memoria_recuperada` (ids dos
  episódios e chaves dos fatos que entraram na janela desta execução). Duas
  execuções com `memoria_snapshot` diferente **não são comparáveis**.
- **Suíte de regressão.** Os 5 casos de `dados/casos.md` rodam sempre com
  memória **congelada**: um snapshot fixo e versionado junto com os casos. Uma
  rodada com memória vazia e outra com o snapshot de referência permitem
  separar o efeito do prompt do efeito da memória. É o problema que a Aula 11
  vai assumir.

---

## Resposta à pergunta do exercício

**O que o nosso agente não guarda:**

- nenhum dado pessoal além do `vendedor_id` (nem nome, nem telefone, nem
  CEP, nem a fala literal do vendedor);
- nenhuma afirmação do vendedor sobre o produto que não tenha passado pela
  publicação ou pela moderação;
- nada que o banco recalcule (preço de mercado, contagens, status do
  indício);
- nenhum texto vindo de fora na memória procedural;
- nenhuma memória de longo prazo do comprador (Agente A).

**O que ele perde, quando perde:**

- Sem a fala literal, um anúncio antigo **não pode ser reauditado pela
  memória**. A evidência literal vive só no checkpoint e no log, e morre com
  eles.
- Sem guardar o que o vendedor afirma, o agente **não aprende sozinho** com
  um vendedor sincero. Ele aprende só depois que a moderação confirma, o que é
  mais lento.
- Sem memória do comprador, o Agente A começa do zero toda vez que alguém
  volta ao site.

Aceitamos essas três perdas de propósito. Neste case, a memória errada é
pior que a memória ausente, porque o erro que mais custa é publicar um
defeito escondido.


---

## Parte 2 — o que foi implementado, o que mudou, e o que foi medido

### P2.1 O que mudou em relação ao desenho

| Decidido no exercício 8 | Implementado | Por quê |
|---|---|---|
| checkpoint em `checkpoints/{execucao_id}.json` | `SqliteSaver` do LangGraph, `dados/checkpoints.db`, endereçado por `thread_id` | o framework já grava o estado íntegro a cada super-passo — o checkpoint deixou de ser código nosso (`docs/grafo.md` §6.5) |
| episódica em Chroma | tabela `memoria_episodica` (SQLite) + cosseno em numpy, `gemini-embedding-001` 768 dim | a escala (~1.000 episódios/semestre) não pede índice dedicado; a remoção por metadado vira `DELETE WHERE vendedor_id = ?` (`docs/rag.md` §4.1) |
| `prompts/procedural.md` | `src/prompts/procedural.md` (3 regras, ~70 tokens) | os prompts foram para `src/prompts/` (§2.2). Uma das 4 regras previstas — "use a grafia do vendedor na categoria" — **saiu antes de entrar**: virou código (categoria `Literal` com vocabulário fechado). Regra que vira código deixa a memória (§2.2) |
| `anuncios` sem `vendedor_id` (item 6 do inventário) | coluna `vendedor_id` no `seed.sql` | sem ela a remoção por titular era impossível |
| `registrar_indicio_avaria` sem idempotência e com `anuncio_ref` fixo | chave derivada do conteúdo + `anuncio_id` ligado em `preparar_moderacao` | as duas correções prometidas em §1.1 |
| procedural: "pergunte sobre avaria antes do rascunho" | **continua** na procedural **e** virou portão em código (`portao_avaria`) | a regra no prompt não bastou com nenhum dos modelos testados |

### P2.2 As três memórias, rodando

| Tipo | Estrutura | Quem escreve (§5.3) | Volume por execução |
|---|---|---|---|
| episódica | `memoria_episodica`: resumo + vetor + metadados (`data`, `categoria`, `bairro`, `vendedor_id`, `desfecho`, `avaria`) | **código**, com 1 chamada de extração (`extracao-memoria-v1.md`) a partir de **campos estruturados**, depois `filtrar_pii` | **1 episódio** por anúncio que chega a ter rascunho (uma frase de até 40 palavras) |
| semântica | `memoria_semantica` (entidade, chave, condição) → valor, `data`, `fonte`, `substituiu` | **código por regra, sem modelo**: `bairro_retirada` do anúncio publicado; `aceita_sugestao_preco` quando o pedido estava acima da faixa; `avarias_tipicas` da categoria **só depois que a moderação confirma** | **0 a 2 fatos** |
| procedural | `src/prompts/procedural.md`, inteira no system prompt; candidatas em `regras_candidatas` | **código propõe** (execução que termina em `laco`, `orcamento` ou avaliador 3x), **humano aprova** editando o arquivo | **0** na maioria; 1 candidata por execução que falha |

**Idempotência na escrita de memória** (§5.3): toda gravação tem chave
derivada do conteúdo e devolve `ja_existia`. Medido em
`logs/medicoes/demo_memoria.json`: gravar o mesmo fato duas vezes → a segunda
devolve `{"ja_existia": true}` e não toca no histórico.

**O efeito da memória, medido** (era a projeção do §1.3): depois que a
moderação confirmou o defeito do freezer no **caso 4**, o **caso 13** — outra
pessoa, outra geladeira — recebeu uma primeira pergunta que cita o freezer
pelo nome, em vez do genérico "tem algum defeito?"
(`logs/13_memoria_avaria_tipica.json`, passo `iniciar_b`:
`memoria_recuperada.fatos_categoria = ["avarias_tipicas"]`). Isso confirma
também o preço do §2.4: a mesma primeira fala produz conversas diferentes
conforme a memória — e o carimbo de cada log registra o `memoria.snapshot()`.

**Dois defeitos que a memória trouxe, medidos e corrigidos:**

1. **A memória de categoria foi lida como fala do vendedor.** Nas 3
   repetições do caso 2 (vendedor honesto, geladeira sem defeito), a memória
   já tinha `categoria:geladeira / avarias_tipicas = ["freezer inferior…"]`,
   aprendido com **outro** vendedor no caso 4. Em **2 de 3** execuções o
   modelo escreveu *"a memória indica que ele relatou anteriormente que o
   freezer demora"* e **registrou um indício falso** contra quem tinha dito
   "sem defeito" (`logs/medicoes/estabilidade_antes_da_correcao/`). É o risco
   do §1.4 ("memória errada é pior que memória ausente") acontecendo, e ele
   veio de uma memória **certa** — o defeito era a leitura. Correção em
   código (commit `1a5cd36`): `registrar_indicio` só grava se houver uma
   **fala do vendedor nesta conversa** que mencione defeito; e o texto da
   memória de categoria passou a dizer "vistos em OUTROS anúncios, não são
   deste vendedor; use só para perguntar". Depois: **3 de 3** sem indício.
2. **A chave do episódio dependia do texto do modelo.** O §5.3 pede chave
   derivada do conteúdo; a 1ª versão usava o resumo escrito pelo modelo — que
   **varia entre execuções** ("12/10/2026" × "[2026-10-12]", "preço mantido" ×
   "manteve-se"). Resultado na rodada final: o mesmo anúncio do caso 2 virou
   **4 episódios** (um por execução), e a re-execução de `publicar` do caso 6
   gravou **um segundo** episódio do sofá — o anúncio, esse, não duplicou,
   porque a chave do banco usa campos estruturados. Correção
   (`chave_episodio` em `src/memoria.py`): a chave é vendedor + **anúncio**
   (ou a conversa, se não houve anúncio) + desfecho, e, se o episódio já
   existe, a extração nem é chamada. Verificado sem rede: duas gravações do
   mesmo anúncio com resumos diferentes → a segunda devolve `ja_existia:
   true` e não chama o embedding. **Esta correção é posterior aos logs dos
   casos** (que foram gerados no commit `1a5cd36`); os logs mostram o defeito.

### P2.3 As três causas de esquecimento, executadas

Escolhemos as **três** (a razão de cada uma está na Decisão 2). Medido em
`logs/medicoes/demo_memoria.json` (`python scripts/demo_memoria.py`):

| Causa | O que o código faz | Resultado medido |
|---|---|---|
| **contradição** | `gravar_fato` substitui pela chave (entidade, chave, **condição**) e guarda o anterior em `substituiu` | "Santo Amaro" (10/06) → "Campo Grande" (02/09): a leitura devolve Campo Grande, com Santo Amaro em `substituiu`. Um terceiro fato "Santo Amaro" com `condicao = "itens pequenos"` **não** empata: os dois voltam, cada um com a sua condição (o caso que o carimbo não resolve, §2.1) |
| **decaimento** | `rotina_decaimento`: > 180 dias rebaixa (similaridade × 0,5); > 365 dias remove. Fato de vendedor > 180 dias volta `a_confirmar` | 3 episódios de 10, 200 e 400 dias: 1 removido, 1 rebaixado (similaridade 0,93 → 0,46), 1 intacto |
| **remoção** | `remover_titular` (`src/remocao.py`) nas 9 estruturas do inventário | abaixo |

**A remoção, com a verificação independente** (o roteiro do §2.3):

1. **Grava** — duas execuções reais do grafo para um titular de teste (o caso 4
   e o caso 1, com outro `usuario_id`): passam por episódio, fato semântico,
   indício, anúncio, pendência, checkpoint e log.
2. **Verifica que o comportamento mudou** — uma conversa nova do titular
   recupera `fatos_vendedor = ["bairro_retirada"]` e um episódio dele.
3. **Remove** — o relatório (execução final): 2 episódios, 1 fato, 2 threads
   de checkpoint, 2 logs, 2 anúncios, 2 pendências apagados; 1 indício
   **anonimizado**.
4. **Verifica que voltou** — a mesma conversa nova recupera `fatos_vendedor = []`.
5. **Varre** — `scripts/verificar_remocao.py`, que **não importa** o código da
   remoção: abre os 4 bancos SQLite (todas as tabelas, todas as colunas,
   inclusive os blobs dos checkpoints, como bytes), os logs e os prompts, e
   procura o identificador no texto. Resultado: **"OK — nenhum vestígio em 6
   lugares"**.

**Os três que escapam com frequência (§5.4), no nosso caso:**

- **checkpoint** — guarda a conversa literal e os argumentos de cada passo. É
  apagado pela thread inteira (o `thread_id` começa com o id do titular — é
  por isso que ele é `<usuario>:<sessao>`).
- **log** — os logs de `logs/` guardam a conversa inteira; a remoção apaga o
  arquivo. O próprio relatório da demonstração **mascara** o id
  (`<titular-de-teste>`), senão a varredura seguinte o encontraria nele.
- **procedural** — a remoção **varre** `procedural.md` e **reporta** linhas com
  o id, mas não edita: é fonte versionada, a edição é humana. A fila de
  candidatas é apagada pelo `origem_thread`.

**O que fica de propósito:** o fato de categoria `avarias_tipicas`
("freezer inferior com congelamento lento") nasceu do indício do titular e
**não sai** com a remoção — descreve o produto, não a pessoa, e não carrega
id. O indício fica **anonimizado** (sem vendedor, sem thread, sem fala
literal) como registro de moderação.

**O índice não precisa ser reconstruído**: a remoção é por metadado, então
serve aos três usos — privacidade, custo e recuperação de incidente.

**Fora do alcance, declarado:** o que foi enviado ao provedor do modelo. No
plano gratuito do Gemini, o Google pode usar o conteúdo para melhorar os
produtos (`docs/modelos.md` §4.3) — com dado real isso inviabiliza o plano
gratuito; nesta entrega os dados são simulados.

### P2.4 Os dois níveis, e a fronteira entre as três estruturas (§5.1)

| | checkpoint | memória | RAG |
|---|---|---|---|
| no case | o anúncio sendo montado: conversa, rascunho, decisão do humano pendente | o que o sistema viveu: como terminaram anúncios parecidos, onde o vendedor retira, que defeito a geladeira usada costuma ter | as regras da plataforma, escritas por quem mantém os Termos e a política |
| escopo | uma thread (`usuario:sessao`) | todas as execuções do Agente B | nenhuma — externo |
| propósito | **retomar** (o vendedor volta amanhã; o moderador decide em 48 h) | **lembrar** | **consultar** |
| leitura | a cada turno da thread, inteiro | uma vez, no `iniciar_b` (semântica por chave, episódica k=2) | quando o agente pede (`consultar_regras`) ou na rota de dúvida |
| quem escreve | o framework, a cada super-passo | o código, em `finalizar_b` | ninguém — curado (`dados/corpus/`) |

**O que precisa estar no checkpoint para retomar sem reaplicar efeito
colateral:** `escritas` (o `anuncio_id` e o `indicio_id` já gravados),
`pendencia` (o que o humano está decidindo, com o prazo), `rascunho` e
`decisao_humana`. E não basta estar no checkpoint: as escritas são
idempotentes **também no banco**, porque o processo pode morrer entre gravar
no banco e gravar o checkpoint (o caso 6 re-executa `publicar` a partir do
checkpoint anterior e prova que não duplica — `docs/humano.md` §8.5).

**O que a recuperação por relevância traz que a serialização não traria:**
serializar as threads antigas daria ao agente milhares de conversas literais
— o arquivo morto. O que entra na janela são **2 episódios** da mesma
categoria e **os fatos por chave** do vendedor (~100 tokens). O que ela deixa
para trás: a evidência literal (a fala "prefiro não pôr isso"), que vive só no
checkpoint, no log e no indício, e morre com eles.

**A ordem de descarte** (§1.2) foi implementada no `agente_b`: as 10 últimas
falas entram sempre; das mais antigas, **só sobrevivem as que falam de
avaria**. Nenhum caso desta entrega passou de 10 falas — a regra existe, mas
não foi exercitada (declarado).

### P2.5 A conversa, e o que sobra dela (§5.5)

**O que identifica uma conversa.** `thread_id = "<usuario_id>:<sessao_id>"`
(`Entrada.thread_id` em `src/contrato.py`). O `usuario_id` vem da sessão
logada do site; o `sessao_id`, da aba de chat aberta. **A mesma pessoa com
duas abas** tem duas conversas independentes, dois checkpoints: pode montar
dois anúncios ao mesmo tempo sem um contaminar o outro. O preço: a memória de
longo prazo é a mesma para as duas (é por `vendedor_id`), então o que uma
aprende a outra só vê no próximo `iniciar_b`.

**Onde o checkpoint é gravado.** Em banco: `SqliteSaver` em
`dados/checkpoints.db`. A conversa e a pausa do humano **sobrevivem ao
processo** (dá para fechar o terminal, abrir outro e `python cli.py responder
…`). Limitação declarada: um arquivo local; com mais de um servidor seria
Postgres.

**O que acontece quando a janela enche.** A política do §1.2, aplicada na
montagem do contexto do `agente_b`: (1) a conversa entra recortada — as 10
últimas falas, mais as falas antigas sobre avaria, que nunca saem; (2) de cada
ferramenta entra **só o último resultado** (`faixa_de_preco`,
`regras_consultadas`, `ultima_avaliacao`), não a trajetória inteira — o "tool
clearing" está na forma do estado, porque cada ferramenta escreve num campo
que **substitui** o anterior; (3) a memória de longo prazo é limitada na
leitura (k=2 episódios). **O que se perde**: o meio de uma conversa longa que
não fale de avaria (ex.: o vendedor disse a cor na fala 3 e a conversa foi a
15 falas) — o rascunho pode perder esse detalhe cosmético. A triagem vê só as
6 últimas falas.

**O que passa da conversa para a memória de longo prazo.** Ao fim de cada
anúncio (`finalizar_b`), por regra: 1 episódio (resumo de campos
estruturados), 0–2 fatos semânticos, 0–1 regra candidata. **A conversa em si
não passa** — nem a fala literal, nem a descrição escrita pelo modelo. Do
Agente A, **nada passa** (Decisão 1.5): a conversa do comprador morre com a
thread.

# Case — Santo Desapego: consultor de compra + assistente de anúncio

## 1. O case: indústria e problema

**Setor:** Varejo digital / marketplace C2C de proximidade (economia
compartilhada). Recorte do TCC do grupo — plataforma Santo Desapego, comércio
local de produtos novos e usados em Santo Amaro, São Paulo.

**Problema (uma frase):** No Santo Desapego, dois agentes ajudam os lados que mais
erram sozinhos — um infere a intenção do comprador a partir do que ele visualiza e
monta a sugestão; o outro conversa com o vendedor para completar o anúncio e fazer
emergir o que ele não declara (como avarias).

> Por que um recorte, e não o marketplace inteiro: cadastro (RF01), busca por
> filtros (RF07), chat (RF15), pagamento via Mercado Pago (RF14) e reputação
> (RF16) são software comum — formulário, consulta, CRUD, integração de API.
> O que exige um agente são os dois componentes abaixo, cada um com decisão em
> tempo de execução sobre algo que o usuário não declarou.

### Os dois agentes (visão geral)
- **Agente A — Consultor de compra (comprador):** a partir dos itens que o usuário
  clica, infere a intenção que ele não declarou (mobiliar um cômodo? caçar uma
  peça? presente?) e monta uma sugestão com itens ativos, perto e no orçamento.
- **Agente B — Assistente de anúncio (vendedor):** conversa por texto com o
  vendedor sobre o produto e recomenda como preencher o cadastro — título,
  categoria, preço justo pelo mercado local — e, principalmente, faz perguntas que
  trazem à tona o que o vendedor tende a omitir (ex.: detectou indício de avaria →
  orienta declarar o defeito e anexar foto do problema). Foco duplo: qualidade/
  honestidade do anúncio e preço justo.

### Contexto

**Quem sofre com isso hoje, concretamente:**
- *No lado vendedor (o foco desta Parte 1):* a pessoa que está se desfazendo de
  um móvel ou eletrodoméstico usado pela primeira vez — depois de uma mudança,
  a troca da geladeira velha por uma nova, um upgrade de sofá — e nunca
  anunciou nada num marketplace antes. Não é "os vendedores": é essa pessoa
  específica, sem prática nenhuma com anúncio, decidindo sozinha o que
  escrever e sem saber se R$ 350 é um preço justo ou uma bobagem.
- *No lado comprador (Agente A, Parte 2):* quem está mobiliando um cômodo ou
  caçando uma peça específica e não sabe o nome exato do que procura — garimpa
  o catálogo item a item porque a busca por palavra-chave não ajuda quando
  você não sabe o termo certo.

**O que acontece hoje, sem o sistema**
- *Lado comprador:* navega por conta própria com filtros (RF07) e busca por CEP
  (RF08); se não sabe exatamente o que quer, garimpa item a item. Cada usado é
  único e some quando vende — a janela é curta.
- *Lado vendedor:* preenche o anúncio sozinho (RF11). O vendedor de primeira
  viagem — sem nunca ter anunciado antes — erra título, categoria e preço, e
  — por desconhecimento ou má-fé — omite defeitos. Anúncio ruim gera
  desconfiança, pergunta repetida no chat e disputa depois da compra.

**Regras do domínio**
- Agente A só sugere itens **ativos** (RF12); nunca vendido/pausado. Prioriza
  proximidade pelo CEP (RF08) e a faixa de preço que o comportamento indica. Não
  recomenda anúncio do próprio usuário nem itens suspensos (RF19/RF20).
- Agente B **não bloqueia** a publicação. Se detecta uma avaria que o vendedor se
  recusa a declarar, ele **registra o indício** e encaminha para a moderação
  humana (RF20) decidir — o agente aconselha e sinaliza, não veta.
- Preço: o Agente B **sugere**, o vendedor decide (a alçada de preço é dele).
- LGPD (RNF01): o Agente A usa comportamento de navegação; base legal e direito de
  exportar/excluir dados seguem a política (RF04).

**O que dá errado hoje (os casos difíceis — nossos casos de teste)**
- *Comprador — intenção ambígua:* clica em geladeira, micro-ondas e mesa. Mudança?
  Cozinha? Revenda? A sugestão certa depende da hipótese que o agente adota.
- *Comprador — estoque volátil:* o item ideal foi vendido há 5 min; o agente
  remonta a sugestão em runtime com o que resta.
- *Comprador — cold start:* dois cliques só; o agente decide se sugere ou espera.
- *Vendedor — omissão de avaria:* o vendedor escreve "geladeira ótima" mas na
  conversa aparece que "só não gela embaixo". O agente tem que fazer isso emergir.
- *Vendedor — preço fora do mercado:* pede R$ 900 num item que sai por R$ 400 no
  bairro; o agente confronta com o mercado local sem impor.
- *Vendedor — anúncio pobre:* título "vendo isso aqui", sem categoria. O agente
  extrai o essencial conversando, não de um formulário.

### O que a indústria já faz com agentes nesse problema
Ver `docs/fontes.md` para casos completos, links e leitura crítica. Resumo:

*Lado comprador (Agente A):*
- **Rep AI (Shopify):** product finder conversacional que interpreta necessidade
  ("notebook leve para faculdade"), pergunta o que falta e busca no catálogo ao
  vivo — a própria fonte frisa que **não é árvore de decisão fixa**: o agente
  pondera contexto e decide a ação.
- **Agentic commerce (ChatGPT / Amazon Rufus):** extrai restrições (orçamento,
  uso, prazo) da linguagem e traduz em consultas a catálogo/estoque real.

*Lado vendedor (Agente B):*
- **eBay "magical listing":** gera título, descrição, categoria e sugestão de
  preço para o vendedor. Número divulgado: ~30% dos vendedores ativos testaram o
  recurso e >95% dos que testaram usaram a descrição gerada (CSAT >80%). O eBay
  descreve isso como solução para o **cold start** do vendedor iniciante — a
  mesma dor do vendedor amador do Santo Desapego.
> 

## 2. Usuários e interação

| Perfil | O que ele quer | O que ele sabe | O que ele pode fazer |
|--------|---------------|----------------|----------------------|
| Comprador (principal do Agente A) | Achar o que precisa sem garimpar | Vagamente o que quer; seu orçamento e bairro | Aceitar/ignorar/refinar a sugestão; contatar vendedor; **confirmar a compra** |
| Vendedor (principal do Agente B) | Anunciar rápido e vender bem | Seu produto (às vezes esconde defeito); seu preço-desejo | Aceitar/editar as recomendações; **publicar o anúncio**; definir o preço final |
| Moderador/Admin | Que a plataforma não hospede fraude nem item enganoso | Regras e denúncias/sinalizações | Suspender anúncio/conta (RF20); **decidir sobre avaria sinalizada pelo Agente B** |

**Usuários principais:** o comprador (para o Agente A) e o vendedor (para o Agente
B). A tensão central do sistema é entre eles — ver adiante.

**A interação, concretamente**

*Agente A (comprador):*
- **Por onde:** bloco "Para você" dentro do site, que se atualiza conforme os
  cliques; o usuário pode refinar por chat ("mais barato", "mais perto").
- **Quem começa:** o sistema, ao juntar sinal suficiente.
- **Formato:** sugestão enxuta (poucos itens / um "combo") com justificativa de
  uma linha. Com pouco sinal, admite que não sabe e mostra descoberta genérica.

*Agente B (vendedor):*
- **Por onde:** um chat no fluxo de criação do anúncio (RF11), antes de publicar.
- **Quem começa:** o vendedor, ao iniciar um anúncio; o agente conduz por
  perguntas.
- **Formato:** devolve os campos preenchidos (título, categoria, descrição, preço
  sugerido) para o vendedor revisar. Quando algo indica avaria, pergunta direto e
  orienta anexar foto do problema. Se o vendedor recusa, registra e segue para
  moderação (RF20) — não bloqueia.

**Diálogo de exemplo — Agente B (vendedor)**

> Vendedor: quero vender minha geladeira, uns 400 reais
> Agente: Fechado. Qual marca e tamanho? E há quanto tempo você tem?
> Vendedor: consul duplex, uns 5 anos, funciona bem
> Agente: Ótimo. Duplex costuma sair entre R$ 300 e R$ 380 aqui em Santo Amaro
>         nesse estado — R$ 400 pode segurar a venda. Quer manter ou ajustar?
>         E uma pergunta padrão: tem algum detalhe que o comprador vai notar
>         pessoalmente? risco, borracha ressecada, algo que não gela direito?
> Vendedor: ah, o freezer embaixo demora pra congelar
> Agente: Isso é importante declarar — evita disputa depois. Sugiro colocar na
>         descrição "freezer inferior com desempenho reduzido" e uma foto do
>         freezer. Posso já escrever assim?
> Vendedor: prefiro não pôr isso
> Agente: Sem problema, não vou incluir. Só registro que conversamos sobre um
>         possível defeito — a moderação pode revisar antes de destacar o anúncio.
>         Seguimos com o resto do cadastro?

**O que o usuário não informa de primeira, e o sistema precisa descobrir:**
- *Agente A:* a **intenção de compra** por trás dos cliques e as restrições
  implícitas (orçamento, distância tolerada).
- *Agente B:* o **estado real do produto** — a avaria que o vendedor não escreve —
  e o descompasso entre o preço-desejo e o mercado local.
Em ambos, o que importa não está num campo de formulário: o agente infere/faz
emergir em tempo de execução. É isso que separa este case de um recomendador
"quem viu, viu" e de um gerador de anúncio a partir da foto.

**Como o Agente B decide que já sabe o suficiente pra agir:** quando tem
produto, preço, bairro e uma resposta (mesmo que "não" ou "sem defeito") pra
pergunta sobre avaria — isso é o "essencial" definido no prompt
(`prompts/agente-anuncio-v4.md`). Detalhe cosmético (litragem exata, cor, ano
de fabricação) não entra na conta; uma vez com o essencial, ou se o vendedor
pedir pra finalizar, o agente para de perguntar e segue pro rascunho. Rodando
de verdade (`logs/`), esse critério às vezes falha na prática — o agente
pulou a pergunta sobre avaria em 2 dos 5 casos testados — e isso está
documentado como achado real em `docs/modelos.md` §3.3, não escondido.

## 2.3 O workflow do agente (Parte 1 — Agente B)

A Parte 1 implementa o Agente B; o workflow do Agente A está em
`docs/arquitetura.md` e entra como código na Parte 2. Sete passos, do texto do
vendedor ao anúncio publicado:

```
1. ENTRADA       o vendedor descreve o produto no chat                    [—]

2. CONVERSA      pergunta o que falta e tenta fazer emergir
                 a avaria não declarada                          [decide: MODELO]

3. CONSULTA      busca a faixa de preço comparável no
                 SQLite (categoria + bairro)                     [decide: CÓDIGO]

4. RASCUNHO      preenche título, categoria, descrição, preço    [decide: MODELO]

5. REVISÃO       avaliador confere o checklist de 5 critérios    [decide: MODELO]
                   incompleto     -> volta para 2 (pergunta o que falta)
                   avaria negada  -> registra indício, segue para 6
                   aprovado       -> segue para 6

6. PUBLICAÇÃO    grava o anúncio no banco, estado 'ativo'
                 (+ registra indício, se houve)           [ESCRITA — reversível]

7. RETORNO       confirma ao vendedor e mostra o anúncio publicado        [—]
```

A maioria dos passos que **decidem** (2, 4, 5) é modelo — é exatamente onde
está a parte não formulável do problema (o que perguntar, como escrever, se o
rascunho está honesto). Os passos 3 e 6 são código porque não há ambiguidade
neles: consultar preço e gravar são determinísticos uma vez que se sabe *o
quê* consultar/gravar. Nenhum passo de escrita é irreversível — publicar e
registrar indício podem ser editados/revistos depois (ver §2.4 e o quadro de
"Escritas do sistema" em `docs/arquitetura.md`).

## 2.4 O sistema

**O que o sistema faz:** conduz o vendedor por uma conversa até ter um
anúncio completo; consulta o preço de mercado local; verifica o rascunho
contra um checklist antes de publicar; e, se houver indício de avaria que o
vendedor recusa declarar, publica mesmo assim mas registra o indício para a
moderação humana decidir.

**Nível de autonomia pretendido:** **AGENTE + AVALIADOR**. Não é um
*workflow*: as perguntas 2 e o texto do rascunho 4 não têm sequência fixa nem
resposta única — dependem do que o vendedor disse até ali. Não é um simples
*roteador*: não há tipos de pedido distintos a classificar no início, a
entrada é sempre "vendedor quer anunciar" (ver §2.2, "quão heterogêneo"). Só
o par AGENTE (decide a próxima pergunta/o rascunho) + AVALIADOR (confere o
checklist antes de publicar) resolve sem subir a autonomia à toa — a
justificativa completa está em `docs/arquitetura.md`, seção "Nota de
autonomia".

**As ferramentas:**

| Ferramenta | O que faz | Leitura ou escrita? | Reversível? | Contra o que ela conversa |
|---|---|---|---|---|
| `consultar_preco_comparaveis` | Faixa de preço de itens semelhantes ativos/vendidos no bairro | Leitura | — | SQLite, tabela `precos_comparaveis` (`src/db.py`) |
| `preencher_campos_anuncio` | Monta título, categoria, descrição, preço sugerido | Escrita (rascunho) | Sim (rascunho editável) | Nada externo — monta o rascunho em memória (`Estado.rascunho`) |
| `publicar_anuncio` | Publica o anúncio (estado ativo, RF12) | Escrita | Sim (edita/pausa depois) | SQLite, tabela `anuncios` (`src/db.py`) |
| `registrar_indicio_avaria` | Sinaliza à moderação (RF20) quando o vendedor recusa declarar | Escrita | Sim (registro; decisão é humana) | SQLite, tabela `indicios_moderacao` (`src/db.py`) |

## 3. Ganhos esperados (§2.5 — a venda)

**Por que um agente, e não software comum (2 frases):** nos dois lados, o sistema
precisa descobrir algo não declarado e decidir a ação — inferir intenção sobre um
estoque volátil (A) e conduzir uma conversa que extrai o defeito omitido e
confronta preço com o mercado (B). Um formulário coleta o que o usuário digita;
nenhum dos dois problemas se resolve pelo que o usuário voluntariamente preenche.


**O ganho esperado, com número e conta à vista — eixo escolhido: tempo por
anúncio (minutos por caso), para o Agente B.**

**Linha de base — medida de verdade, 18/09/2026.** 10 pessoas da turma
cronometradas preenchendo o formulário real de anúncio do site
(`santosdesapego.com.br/anunciar` — título, descrição, estado de conservação,
categoria/subcategoria, preço, CEP/bairro), todas anunciando o mesmo produto
fictício (o do caso 1 de teste: geladeira Consul Duplex, 5 anos de uso, sem
defeito, R$ 350, Santo Amaro), sem ajuda e sem a etapa de fotos (o agente não
lida com foto — excluída pra manter a comparação justa). Cronômetro do clique
no campo "Título" até o clique em "Publicar anúncio".

| Pessoa | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Tempo | 2:15 | 3:40 | 1:25 | 4:05 | 2:55 | 1:10 | 4:45 | 3:05 | 1:35 | 2:30 |

**Média: 2min44,5s (164,5s) por anúncio** · mediana 2min42,5s · mín 1min10s
(pessoa 6) · máx 4min45s (pessoa 7), n=10.

| | Valor |
|---|---|
| **Linha de base (medida)** | **2min44,5s/anúncio** (n=10, 18/09/2026, formulário real do site, mesmo produto fictício pros 10) |
| **Alvo (projeção, não medida)** | Nos 3 casos que o Agente B publicou de verdade (`logs/01_simples.json`, `02`, `04`), o vendedor só precisou escrever **uma mensagem** (a frase inicial, ~12 palavras — ex.: *"quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro"*) — o resto (consultar preço, montar o rascunho, publicar) é automático, sem esperar o vendedor. Projetando o tempo de digitar essa única frase (~30–40 palavras/min de digitação casual): **≈ 20–40s por anúncio**. |
| **A conta** | de **164,5s para ~30s = ≈ 82% de redução** por anúncio, projetado |
| **A ressalva** | a linha de base é medida (n=10, real); o alvo **não é medido** — é uma projeção a partir da contagem de palavras da mensagem que o vendedor precisa escrever, porque o sistema ainda não tem interface de chat real pra cronometrar um vendedor de verdade conversando com o agente (a Parte 1 roda com falas mock, ver `src/agente_anuncio.py`). Cronometrar isso com pessoas reais, numa interface de chat real, é o próximo passo (Parte 2/3) — declarado aqui como o que falta, não escondido. |

**O outro lado da conta — quanto custa, e o que se perde.**

- **Quanto custa rodar:** rodando local (Ollama, `qwen2.5:7b` — a escolha
  desta entrega), **US$ 0 por chamada**; se rodasse na Mistral Small (API
  paga, mesma família dos laboratórios), **≈ US$ 0,0014 por anúncio**, ou
  ≈ US$ 1,40 a cada 1.000 anúncios — conta completa em `docs/modelos.md`
  §3.2, com os tokens medidos nos logs reais.
- **Quanto custa construir:** o grupo já investiu **≈ 8 horas** nesta Parte 1
  (pesquisa do case, arquitetura, prompts, código do agente + integração
  SQLite, e os testes reais com os 2 modelos locais).
- **O que se perde:** medido nos próprios logs desta entrega, não é
  hipotético. O caso 3 (categoria sem preço de referência) trava em loop em
  vez de contornar o erro — quem paga é o **vendedor**, que fica sem
  resposta e precisa recomeçar ou completar o cadastro manualmente. Nos
  casos 4 e 5, o agente às vezes pula a pergunta sobre o estado do produto e
  publica sem checar a avaria (numa rodada, chegou a afirmar "funciona
  perfeitamente" sem nunca ter perguntado) — quem paga é o **comprador**, que
  pode receber um produto com defeito não declarado. Os dois casos estão
  documentados em `docs/modelos.md` §3.3 e no maior risco (§2.11) — não são
  hipóteses, são coisas que aconteceram rodando de verdade.

**Ganho para o negócio (plataforma):** menos abandono na descoberta e mais itens
girando (A); anúncios mais completos e honestos, o que reduz disputa e devolução e
protege a reputação da plataforma (B). 

**Ganho para o usuário:** comprador para de garimpar e recebe um conjunto pronto
(A); vendedor publica mais rápido, precifica melhor e vende com menos atrito (B).

**Tensão — e é o coração do sistema:** o vendedor quer vender caro e às vezes
esconder o defeito; o comprador quer o preço justo e a verdade. O Agente B serve
ao vendedor até o ponto em que isso prejudica o comprador — na avaria, ele fica
do lado da transparência (aconselha declarar; se recusado, sinaliza à moderação).
Ou seja: o sistema otimiza a venda, mas não à custa de enganar o outro lado. Essa
escolha é o que sustenta a confiança, que é o ativo de um C2C local.

## 2.6 O verificador

**Como vocês vão saber que a saída está certa?** Duas camadas, as duas já
construídas (não é "dá pra ver que está certo"):

1. **Regra de negócio, dentro do próprio sistema** — o avaliador
   (`prompts/avaliador-anuncio-v1.md`, `avaliar_rascunho` em
   `src/agente_anuncio.py`) confere o rascunho contra 5 critérios booleanos
   antes de deixar publicar (`tem_titulo`, `tem_categoria`, `tem_descricao`,
   `preco_na_faixa`, `estado_tratado`). É código que confere resultado de
   modelo, não opinião.
2. **Conjunto rotulado à mão** — os 4 casos de `dados/casos.md`, cada um com
   o `termino` e o comportamento esperado escritos *antes* de rodar (simples
   → publica; divergência → confronta preço; sem registro → contorna o erro;
   avaria negada → não publica escondendo, vai pra moderação). É pequeno de
   propósito nesta entrega (§4.5 pede 4); a Parte 2 expande esse conjunto.

## 2.7 O critério de sucesso

**Dos 4 casos nomeados em `dados/casos.md`, o agente termina com o resultado
esperado em pelo menos 4 de 4** — ver a coluna "O que deve acontecer" da
tabela nesse arquivo, comparada ao `termino` e à `trajetoria` de cada log em
`logs/`.

O custo do erro **é assimétrico**, então o caso 4 conta em dobro: os casos 1–3
tratam de completude e preço (recuperável — o vendedor edita depois); o caso 4
trata de honestidade (publicar escondendo uma avaria prejudica diretamente o
comprador, e a plataforma pode não descobrir a tempo). Por isso: **acerta os 4
casos, e o caso 4 nunca pode terminar em `respondeu` com avaria omitida** —
se esse único caso falhar, o critério geral falha, mesmo que os outros 3
batam.

## 2.8 Dados

**De onde vêm:** simulados — mock, gerado em `dados/seed.sql` e nas falas de
vendedor em `CASOS_DEMO` (`src/agente_anuncio.py`). Legítimo para esta parte
(nenhum dado real de usuário do Santo Desapego existe ainda; a plataforma é o
TCC do grupo). Os 3 casos difíceis exigidos, nomeados (ver também
`dados/casos.md`):

- **Divergência** (o sistema diz uma coisa, o vendedor diz outra): caso 2 —
  vendedor pede R$ 900 numa geladeira que sai R$ 300–380 no bairro
  (`precos_comparaveis` em `dados/seed.sql`); e caso 4 — o vendedor descreve
  "geladeira ótima" mas a conversa revela "freezer não congela".
- **Registro inexistente**: caso 3 — bicicleta em Santo Amaro; a tabela
  `precos_comparaveis` propositalmente não tem essa combinação
  categoria/bairro (comentado no fim de `dados/seed.sql`), forçando
  `consultar_preco_comparaveis` a devolver `erro: sem_comparaveis`.
- **Não deve disparar a ação principal**: caso 4 — avaria negada; o agente
  não pode terminar em `publicar` escondendo o defeito; o esperado é
  `registrar_indicio` seguido de `termino=humano`.

## 2.9 Dado sensível

**Não há dado da categoria "sensível" da LGPD** (art. 5º, II — saúde, dado
racial/étnico, biometria, convicção religiosa, orientação sexual etc.) neste
tema: preço, categoria de produto usado, texto de anúncio e cliques de
navegação não entram nessas categorias. É uma vantagem real do tema, não uma
omissão.

Há, sim, **dado pessoal comum**: o CEP e o comportamento de navegação do
comprador (Agente A), e o texto que o vendedor digita (Agente B) — ambos sob
LGPD (base legal e direito de exportar/excluir seguem a política RF04, já
citada em "Regras do domínio"). Nenhum dado real de pessoa entra no
repositório: tudo é mock, gerado em `dados/seed.sql` (ver comentário no
início do arquivo).

## 2.10 Espaço para o que ainda vem

- [x] **RAG (Parte 2)** — o conhecimento de domínio que falta hoje é a
  **política de moderação** (o que conta como avaria "grave" o bastante pra
  exigir foto, o que pode ser vendido, prazos de revisão do indício). Hoje
  isso não existe formalizado em lugar nenhum — viveria num regulamento
  interno em Markdown/PDF que o Agente B consultaria antes de decidir se uma
  avaria exige declaração obrigatória ou é só recomendação.
- [x] **MCP (Parte 2)** — a integração natural pra virar servidor MCP é a
  camada `src/db.py` (§4.2 desta entrega): já é uma camada separada do
  agente, já expõe 3 operações (`consultar_preco_comparaveis`,
  `publicar_anuncio`, `registrar_indicio_avaria`) que hoje são chamadas
  Python diretas e virariam ferramentas MCP.
- [x] **LangChain (Parte 2)** — o laço `rodar_agente` (estado + orçamento +
  detector de laço, hoje escrito à mão em `src/agente_anuncio.py`) é o
  candidato: vira um `AgentExecutor`/grafo de estados, e o avaliador vira um
  segundo nó explícito no grafo em vez de uma função chamada por dentro do
  loop.
- [x] **Multiagente (Parte 3)** — os candidatos já existem no desenho: Agente
  A (comprador) e Agente B (vendedor) já são independentes; a Parte 3
  poderia somar um terceiro agente de **moderação assistida** (que priorize a
  fila de indícios que o Agente B gera, hoje só um registro `pendente` sem
  triagem) — mais de um agente porque comprador, vendedor e moderador têm
  objetivos genuinamente diferentes (ver tensão em §2.5), não é o mesmo
  problema visto de três ângulos.

## 2.11 O maior risco

**O avaliador e o agente escritor usam o mesmo modelo.** Não é "o modelo pode
errar" (isso é premissa) — é que, se o modelo tem um ponto cego (ex.: aceitar
"funciona bem, só um detalhezinho" como `estado_declarado: true` sem cobrar
o detalhe), **o mesmo ponto cego aparece nos dois lados**: quem escreve o
rascunho aceita a descrição vaga, e quem confere (o mesmo modelo, outro
papel) também aceita — porque é o mesmo viés julgando o próprio trabalho.
Um checklist "aprovado" deixa de ser prova de qualidade quando quem escreveu
e quem conferiu compartilham a cegueira.

**Plano B:** usar um modelo diferente (família ou porte diferente) para o
avaliador do que para o agente que escreve — já é possível hoje, trocando só
o `MODELO` passado a cada chamada; e complementar com uma checagem
determinística fora do LLM (regex por palavras como "mas", "só não", "não
funciona totalmente" no texto do vendedor) que força uma pergunta de
confirmação sempre que aparecer, independente do que o avaliador decidir.

---

### Anti-padrões — checagem
- **Sem verificador?** Não. (A) o usuário contatou/favoritou/comprou o item
  sugerido, ou não. (B) o anúncio saiu com os campos completos e o estado
  declarado, ou não; e há menos disputas/devoluções nos anúncios que passaram pelo
  agente. Há sinal objetivo nos dois.
- **Dado que não temos?** Não — cliques, CEP, preço, estado do anúncio e o texto da
  conversa são gerados pela própria plataforma do TCC.
- **Grande demais?** São dois agentes, mas cada um cabe em uma frase e usa poucas
  ferramentas. Risco a vigiar: tratá-los como um só sistema gigante. Mitigação: são
  independentes; a Parte 1 pode focar em um e o outro entra depois.
- **Produto de terceiro?** O risco real deste tema, dos dois lados (existem
  recomendadores e geradores de anúncio prontos). O que é arquitetura de agente
  aqui: (A) inferência de intenção não declarada + remontagem em runtime sobre
  estoque volátil; (B) a conversa que faz emergir o defeito omitido e o confronto
  de preço com o mercado local — não a chamada de uma lib de "itens similares" nem
  um "gerar anúncio da foto".


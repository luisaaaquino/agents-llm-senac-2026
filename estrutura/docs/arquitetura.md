# Arquitetura v1 — Santo Desapego

Sistema do trabalho semestral. Dois agentes independentes, um por lado do
marketplace C2C:
- **Agente A — Consultor de compra** (comprador): infere a intenção não declarada
  a partir da navegação e monta a sugestão.
- **Agente B — Assistente de anúncio** (vendedor): conversa para completar o
  anúncio, faz emergir o que o vendedor omite (avaria) e sugere preço de mercado.

> `v1` é proposital: este desenho vai mudar quando encontrar o código. A Parte 2
> pede a versão que sobreviveu, com o que mudou e por quê.

> **Tetos:** todos os tetos de autonomia já estão definidos (nenhum ausente),
> ancorados no orçamento de referência da aula 05 e ajustados por agente. O quadro
> consolidado está no fim do documento.

---

# AGENTE A — Consultor de compra (comprador)

## 1. Entrada
- **O quê:** evento de navegação — a sequência de itens que o usuário clicou/
  visualizou, mais o CEP do usuário. Não é texto livre; é evento estruturado.
- **De onde, e quem dispara:** a própria plataforma dispara, ao acumular sinal de
  navegação (o sistema acorda sozinho). O usuário pode, opcionalmente, refinar
  depois por texto ("mais barato", "mais perto").
- **Quão heterogêneo:** **homogêneo** — todo evento é da mesma natureza (cliques +
  CEP). Proporção: ~100% eventos de navegação; o refino textual opcional é minoria
  (~10% das sessões, estimado).
  → Como a entrada é homogênea, **não há Router**: não há tipos distintos para
  rotear. A decisão que existe ("tenho sinal suficiente?") é um gate por código,
  não uma classificação de rota.

## 2. System
- **System prompt (uma frase):** "Você é um consultor de compra do Santo Desapego;
  a partir do que o usuário visualizou, infere a intenção dele e monta uma
  sugestão de itens *ativos*, próximos e dentro do orçamento provável — e quando o
  sinal é fraco, pergunta ou admite que não sabe, em vez de chutar."
- **Ferramentas:**
  | Ferramenta | O que faz | Leitura/Escrita | Reversível? |
  |------------|-----------|-----------------|-------------|
  | `consultar_catalogo_ativo` | Lista itens com estado = ativo (RF12), por categoria/faixa de preço | Leitura | — |
  | `calcular_distancia` | Distância entre CEP do usuário e do item (RF08) | Leitura | — |
  | `montar_sugestao` | Produz o bloco final exibido ao usuário | Escrita (só exibe) | Sim (nada persistido) |
- **Estado (sobrevive entre passos):** a intenção inferida (hipótese atual), as
  restrições deduzidas (faixa de preço, distância tolerada), os itens já
  considerados e os já descartados, e o motivo do descarte.
- **Orçamento (tetos):**
  - `MAX_PASSOS_AGENTE` = **6** (passos de raciocínio/ferramenta por sugestão)
  - `MAX_TOKENS` = **20_000**
  - `MAX_TEMPO` = **20 s** (a sugestão aparece durante a navegação; precisa ser rápida)
  - `MIN_SINAL` = **3** (nº mínimo de cliques para acionar o agente; abaixo disso, descoberta genérica)

  > Ancoragem: o orçamento padrão da aula 05 (`agente.py`) é
  > `max_passos=12, max_tokens=60_000, max_segundos=120`. O Agente A recebe
  > tetos **menores** porque roda durante a navegação e tem o menor "direito de
  > gastar" — a própria aula 05 trata orçamento como parâmetro por fase, não
  > constante ("uma triagem e uma investigação não têm o mesmo direito de gastar").

## 3. Processamento
Como o evento de navegação vira a sugestão exibida — com o padrão de cada etapa.

```
1. ENTRADA        evento de navegação (cliques + CEP)                    [—]

2. GATE DE SINAL  há cliques suficientes? (>= MIN_SINAL)          [CÓDIGO, sem LLM]
                    não -> descoberta genérica do bairro (encerra)
                    sim -> segue para 3

3. INFERÊNCIA     infere intenção + restrições e busca itens
                  ativos, cruzando catálogo/distância/preço   [AGENTE, MAX_PASSOS_AGENTE]

4. MONTAGEM       seleciona o conjunto final e escreve a
                  justificativa de uma linha                           [—]

5. RETORNO        exibe o bloco "Para você"                    [ESCRITA - só exibe, reversível]
```

**Justificativa dos padrões (2 linhas cada):**
- **AGENTE (etapa 3):** a intenção não é declarada e o catálogo de usados muda em
  runtime; é preciso decidir hipótese, buscar e reavaliar. Um workflow fixo ou um
  recomendador por similaridade não infere intenção nem se adapta ao estoque vivo.
- **Por que não algo mais simples:** um Router não cabe (entrada homogênea); uma
  regra fixa ("itens da mesma categoria") é o recomendador clássico que o case
  rejeita. Paramos no AGENTE — a menor autonomia que resolve a inferência.

## O que sai de cada etapa
```
2. GATE DE SINAL
   entra: {"cliques": [id1, id2, ...], "cep": "0472..."}
   sai:   {"suficiente": true}   // ou false -> descoberta genérica

3. INFERÊNCIA
   entra: a lista de itens vistos + CEP (não a página bruta)
   sai:   {"intencao": "mobiliar cozinha", "faixa_preco": [150, 350],
           "raio_km": 2, "candidatos": [ {id, preco, dist_km}, ... ]}

4. MONTAGEM
   entra: os candidatos + a intenção inferida
   sai:   {"itens": [3 ids], "justificativa": "porque você viu X e Y, perto e na sua faixa"}

5. RETORNO
   sai:   o bloco "Para você" renderizado na tela
```
**O que o usuário vê (exemplo):**
> "Parece que você está montando uma cozinha aqui perto. Com o que está disponível
> agora a até 2 km e na sua faixa (~R$ 150–350): Geladeira Consul (R$ 320, 1,2 km),
> Micro-ondas 20L (R$ 140, 0,8 km), Armário 4 portas (R$ 300, 1,9 km). Quer que eu
> priorize preço ou proximidade?"

---

# AGENTE B — Assistente de anúncio (vendedor)

## 1. Entrada
- **O quê:** texto livre do vendedor no chat de criação do anúncio (RF11).
- **De onde, e quem dispara:** o vendedor procura o sistema, ao iniciar um anúncio.
- **Quão heterogêneo:** **homogêneo** na forma (sempre texto livre de quem quer
  anunciar), mas o conteúdo varia (categoria do produto, com ou sem defeito). Não
  há tipos de entrada distintos a rotear → **sem Router na entrada**. A variação
  (tem avaria? preço fora da faixa?) é tratada dentro da conversa do agente, não
  por classificação prévia.

## 2. System
- **System prompt (uma frase):** "Você é um assistente de anúncio do Santo
  Desapego; conversa com o vendedor para preencher um anúncio completo e honesto —
  faz emergir defeitos que ele não declara, sugere preço pelo mercado local, e
  nunca bloqueia: se ele recusa declarar uma avaria, registra o indício para a
  moderação."
- **Ferramentas:**
  | Ferramenta | O que faz | Leitura/Escrita | Reversível? |
  |------------|-----------|-----------------|-------------|
  | `consultar_preco_comparaveis` | Faixa de preço de itens semelhantes ativos/vendidos no bairro | Leitura | — |
  | `preencher_campos_anuncio` | Monta título, categoria, descrição, preço sugerido | Escrita (rascunho) | Sim (rascunho editável) |
  | `publicar_anuncio` | Publica o anúncio (estado ativo, RF12) | Escrita | Sim (pode editar/pausar depois) |
  | `registrar_indicio_avaria` | Sinaliza à moderação (RF20) quando o vendedor recusa declarar | Escrita | Sim (registro; decisão é humana) |
- **Estado (sobrevive entre passos):** os campos do anúncio já preenchidos, o que
  ainda falta, os indícios de avaria levantados na conversa, o preço-desejo do
  vendedor vs. a faixa de mercado, e se o vendedor aceitou ou recusou declarar.
- **Orçamento (tetos):**
  - `MAX_PASSOS_AGENTE` = **12** (trocas de conversa por anúncio — o padrão da aula 05)
  - `MAX_RODADAS_AVALIADOR` = **3** (revisões do rascunho contra o checklist)
  - `MAX_TOKENS` = **60_000**
  - `MAX_TEMPO` = **120 s**

  > Ancoragem: o Agente B adota o orçamento padrão da aula 05
  > (`max_passos=12, max_tokens=60_000, max_segundos=120`), porque é uma conversa
  > de investigação — tem mais direito de gastar que o Agente A. `MAX_RODADAS=3`
  > segue o exemplo do avaliador do enunciado.

## 3. Processamento
Como a conversa vira um anúncio publicado — com o padrão de cada etapa.

```
1. ENTRADA        texto livre do vendedor                                [—]

2. CONVERSA       conduz perguntas: extrai dados, faz emergir
                  avaria, consulta preço comparável            [AGENTE, MAX_PASSOS_AGENTE]

3. RASCUNHO       preenche os campos do anúncio                          [—]

4. REVISÃO        confere o rascunho contra o checklist
                  (campos completos? estado declarado?)     [AVALIADOR, MAX_RODADAS_AVALIADOR]
                    ok            -> segue para 5
                    incompleto    -> volta para 2 (pergunta o que falta)
                    avaria negada -> registra indício p/ moderação (RF20) e segue

5. PUBLICAÇÃO     publica o anúncio                     [ESCRITA - reversível: edita/pausa]
                  (+ registra indício, se houve)        [ESCRITA - reversível: p/ moderação]

6. RETORNO        confirma ao vendedor e mostra o anúncio publicado      [—]
```

**Justificativa dos padrões (2 linhas cada):**
- **AGENTE (etapa 2):** o estado real do produto não é declarado; é preciso decidir
  quais perguntas fazer, em runtime, para extrair o que falta e o que o vendedor
  omite. Um formulário fixo não faz a avaria emergir — só coleta o que o vendedor
  já ia digitar.
- **AVALIADOR (etapa 4):** a qualidade do anúncio (completo + honesto) tem critério
  objetivo verificável; separar quem *escreve* de quem *confere* evita publicar
  anúncio incompleto. Um único passo de LLM sem verificação não garante o checklist.
- **Por que não algo mais simples:** um Router não cabe (entrada homogênea). Um
  gerador de anúncio a partir da foto (produto de terceiro) não conduz a conversa
  que extrai a avaria. Paramos no par AGENTE + AVALIADOR — a menor autonomia que
  garante anúncio completo e honesto.

## O que sai de cada etapa
```
2. CONVERSA
   entra: {"texto": "quero vender minha geladeira, uns 400 reais"}
   sai:   {"produto": "geladeira Consul duplex", "idade_anos": 5,
           "avaria_levantada": "freezer inferior lento",
           "preco_desejo": 400, "faixa_mercado": [300, 380]}

3. RASCUNHO
   entra: os dados extraídos na conversa
   sai:   {"titulo": "...", "categoria": "...", "descricao": "...",
           "preco_sugerido": 360, "estado_declarado": true|false}

4. REVISÃO
   entra: o rascunho do anúncio
   sai:   {"aprovado": true} | {"aprovado": false, "faltando": ["categoria"]}
          | {"avaria_negada": true}   // -> registrar_indicio_avaria

5. PUBLICAÇÃO
   entra: o rascunho aprovado
   sai:   {"anuncio_id": "...", "estado": "ativo", "indicio_moderacao": true|false}
```
**O que o usuário vê (exemplo):**
> "Pronto! Seu anúncio da Geladeira Consul Duplex está no ar por R$ 360. Deixei a
> descrição completa e sugeri esse preço porque duplex nesse estado sai entre
> R$ 300 e R$ 380 aqui na região. Você pode editar ou pausar quando quiser."

---

# Quadro de tetos — consolidado

O enunciado exige um número em cada teto (pode ser chutado; ausente não pode).
Todos os valores abaixo já estão definidos.

| Agente | Teto | Valor | Observação |
|--------|------|-------|------------|
| A | `MIN_SINAL` (cliques p/ acionar) | 3 | abaixo disso, descoberta genérica |
| A | `MAX_PASSOS_AGENTE` | 6 | metade do padrão: roda na navegação |
| A | `MAX_TOKENS` | 20_000 | menor direito de gastar |
| A | `MAX_TEMPO` (s) | 20 | roda durante a navegação; precisa ser rápido |
| B | `MAX_PASSOS_AGENTE` | 12 | padrão da aula 05 (`agente.py`) |
| B | `MAX_RODADAS_AVALIADOR` | 3 | segue o exemplo do avaliador |
| B | `MAX_TOKENS` | 60_000 | padrão da aula 05 |
| B | `MAX_TEMPO` (s) | 120 | padrão da aula 05 |

> Todos os tetos partem do orçamento de referência da aula 05
> (`Orcamento(max_passos=12, max_tokens=60_000, max_segundos=120)` em
> `agente.py`) e são ajustados por agente conforme o direito de gastar de cada um.
> Lição da aula embutida: **`max_passos` sozinho não é orçamento** — um passo
> gasta de 300 a 40.000 tokens, por isso os três tetos (passos, tokens, tempo)
> aparecem sempre juntos.

# Escritas do sistema — resumo (nenhuma irreversível sem humano)
- A5 — exibir sugestão: escrita só de exibição, nada persiste. Reversível.
- B5 — publicar anúncio: reversível (o vendedor edita/pausa; estados do RF12).
- B5 — registrar indício de avaria: reversível; é um registro, a **decisão é
  humana** (moderação, RF20). Nenhuma escrita irreversível ocorre sem confirmação
  humana.

# Nota de autonomia
Seguindo a regra "usar a menor autonomia que resolve": o Agente A é um AGENTE puro
(inferência sobre estado vivo); o Agente B é AGENTE + AVALIADOR (conversa que
decide + verificação de qualidade). Nenhum dos dois usa Orquestrador/Router, porque
a entrada é homogênea e não há subtarefas paralelas a coordenar — introduzi-los
seria custo sem contrapartida.

# As quatro formas de terminar (aula 05)

Todo agente do sistema termina de exatamente uma destas quatro formas — e o
motivo fica gravado no estado, para ser depurável depois (lição do
`05-orcamento-e-terminacao.py`):

| Término | Quando | Agente A | Agente B |
|---------|--------|----------|----------|
| **RESPONDEU** ✓ | devolveu sem pedir ferramenta | sugestão montada e exibida | anúncio publicado |
| **ORÇAMENTO** ✗ | estourou passos/tokens/tempo | cai para descoberta genérica | devolve o rascunho parcial e pede ao vendedor para completar |
| **ERRO_FATAL** ✗ | não há como continuar (ex.: catálogo/preço fora do ar) | avisa que não conseguiu sugerir agora | avisa que não conseguiu consultar preço; segue o cadastro sem a sugestão |
| **HUMANO** ⏸ | pausou aguardando decisão humana | não se aplica (A não escreve nada irreversível) | **avaria negada → registra indício e suspende para a moderação (RF20)** |

O caso **HUMANO** é o encontro da aula 05 com o nosso case: a moderação da avaria
não é um `input()` no meio do laço — é uma **forma de terminar**. O estado é
gravado, e a decisão do moderador pode chegar depois, por outro processo, sem
repetir nenhum passo já dado.

# Mapa dos padrões × scripts da aula 05
Para deixar explícito de onde cada padrão do nosso desenho vem:

| Nosso uso | Padrão | Script de referência |
|-----------|--------|----------------------|
| Agente A — inferência sobre estado vivo | Agente com estado + orçamento | `04-agente-com-estado.py`, `05-orcamento-e-terminacao.py` |
| Agente B — conversa que investiga | Agente com estado + orçamento | `04`, `05` |
| Agente B — revisão do anúncio | Avaliador com critério escrito | `03-avaliador-otimizador.py` |
| (rejeitado) triagem de entrada | Router | `01-router.py` — não usado: entrada homogênea |
| (rejeitado) subtarefas paralelas | Orquestrador-trabalhador | `02` — não usado: sem subtarefas a coordenar |

Os dois "rejeitados" são deliberados: seguindo a tabela de decisão lida de cima
para baixo, paramos no primeiro padrão que resolve, sem subir a autonomia à toa.

# RAG — as regras do Santo Desapego como memória consultável (§4)

Não é um chatbot sobre PDFs: é o conhecimento de domínio que o **Agente B
precisa para decidir** — se o produto pode ser anunciado, se a avaria exige
foto, que estado de conservação usar — e que a rota de dúvidas usa para
responder quem pergunta como a plataforma funciona.

Código: `src/rag.py` (índice e busca), `dados/corpus/` (o corpus),
`dados/perguntas_rag.json` (o conjunto de perguntas). Medições em
`logs/medicoes/rag_buscador.json`, `rag_revogado.json` e `prompts_resposta.json`.

## 4.1 As formas de recuperar, e as que o case usa

### A classificação das perguntas

As perguntas foram escritas como o usuário escreve (sem acento, com "da pra",
"voces"), a partir das conversas dos casos e das dúvidas que o FAQ do site já
recebia — não a partir do índice.

| # | Pergunta (como a pessoa digita) | A resposta é um… | Forma | Onde está |
|---|---|---|---|---|
| Q01 | por quanto tempo meu anuncio fica no ar? | assunto | vetorial | `termos-de-uso-2026#3` |
| Q02 | posso aceitar troca em vez de dinheiro? | assunto | vetorial | `termos-de-uso-2026#4` |
| Q03 | quanto o site cobra quando eu vendo alguma coisa? | assunto | vetorial | `termos-de-uso-2026#5` |
| Q04 | a taxa de 5% é cobrada em cima do frete tambem? | assunto (**exceção**) | vetorial | `termos-de-uso-2026#5` |
| Q05 | se eu excluir minha conta voces apagam tudo sobre mim? | assunto (**exceção**) | vetorial | `termos-de-uso-2026#8` |
| Q06 | preciso tirar foto de um risquinho na porta da geladeira? | assunto (**exceção**) | vetorial | `politica-moderacao-2026#4` |
| Q07 | posso vender uma replica de pistola de airsoft? | termo | vetorial (ver abaixo) | `politica-moderacao-2026#1` |
| Q08 | da pra anunciar uma arminha de brinquedo de plastico do meu filho? | assunto (**exceção**) | vetorial | `politica-moderacao-2026#2` |
| Q09 | quando o vendedor recebe o dinheiro da venda? | assunto | vetorial | `pagamento-e-entrega#3` |
| Q10 | o que acontece se eu errar o codigo de entrega varias vezes? | termo | vetorial | `pagamento-e-entrega#4` |
| Q11 | o que acontece se o vendedor nao quiser contar um defeito do produto? | assunto | vetorial | `politica-moderacao-2026#5` |
| Q12 | qual estado de conservacao eu coloco numa geladeira que funciona mas tem um amassado? | assunto | vetorial | `guia-estado-conservacao#4` / `#3` |
| Q13 | posso vender ingresso de show pelo site? | **não está no corpus** | — (recusa) | — |
| Q14 | quais bairros o santo desapego atende? | registro | estruturada (tabela `bairros`) — também no corpus | `area-de-atuacao#1` |
| Q15 | quanto sai uma geladeira usada aqui em santo amaro? | registro | **estruturada** (`precos_comparaveis`) | não está no corpus |

Exigências do §4.3: **5 perguntas dependem de exceção** (Q04, Q05, Q06, Q08 e,
pela política, Q07 contra Q08); **uma não está no corpus** (Q13) e uma está em
outro lugar (Q15, no banco).

A classificação não concentrou tudo em "assunto": as perguntas de **registro**
(preço de mercado, catálogo, bairros) são as mais frequentes do sistema inteiro
— o Agente B consulta preço em todo anúncio, o Agente A consulta o catálogo em
toda sugestão — e nenhuma delas passa pelo vetor.

### A escolha

| Forma usada | Com o quê | O que ela responde no case |
|---|---|---|
| **consulta estruturada** | SQLite (`src/db.py`): `precos_comparaveis`, `anuncios`, `bairros` | as perguntas de registro: a faixa de preço do Agente B (todo anúncio), o catálogo ativo do Agente A (toda sugestão), a distância entre bairros |
| **busca vetorial** | `gemini-embedding-001`, **768 dimensões** (o padrão é 3072 — ver §4.3), cosseno em numpy sobre um índice SQLite (`dados/indice_rag.db`) | as perguntas de assunto sobre as regras: Q01–Q12 |

**"O RAG de vocês é vetorial ou banco de dados?"** — Os dois. O vetor responde
"o que a regra diz sobre X"; o banco responde "quanto", "quais" e "onde".

**Busca textual não foi implementada.** As duas perguntas de "termo" (Q07
"réplica de airsoft", Q10 "código de entrega") foram respondidas pela busca
vetorial no top-3 (Q07 em 2º lugar, atrás da exceção do brinquedo — que é
justamente o trecho vizinho). O site já faz a busca textual que importa (o
bloqueio por lista de termos, `validacao.js`) antes da publicação. Voltaríamos
a ela se a lista de proibidos crescer a ponto de a pergunta por um termo raro
("simulacro") deixar de cair no top-3.

**Por que não Chroma** (o desenho da Aula 07 e do `docs/memoria.md`): o corpus
tem 27 trechos e a memória episódica, ~1.000 episódios por semestre; uma
varredura em numpy custa menos de 1 ms, e o Chroma seria mais uma dependência
pesada sem nada que a escala pedisse (não chegamos a testá-lo nesta máquina). A
remoção por metadado, que era o motivo do Chroma no `memoria.md`, é um `DELETE
WHERE vendedor_id = ?` no SQLite.

## 4.2 O corpus, e o que entra nele

| Documento (`dados/corpus/`) | De onde vem | Quem mantém | Muda |
|---|---|---|---|
| `termos-de-uso-2026.md` | Apêndice E da Entrega Final do TCC e `termosContent.js` do site | equipe do TCC | raramente — a cada revisão dos Termos, com novo aceite |
| `politica-moderacao-2026.md` | **redigida nesta entrega** a partir de RN09, RN15, RF19, RF20 e da lista de termos do site | moderação | **mensalmente** — a lista de proibidos cresce com as denúncias |
| `guia-estado-conservacao.md` | RN15 da Entrega Final | equipe do TCC | raramente |
| `pagamento-e-entrega.md` | RN04/RN05 e o fluxo do código de entrega do site (commit `c325b5e`, 03/10/2026) | equipe do TCC | a cada mudança no fluxo de pagamento |
| `area-de-atuacao.md` | RN01/RN13 e a lista de bairros do site | equipe do TCC | quando um bairro entra |
| `faq-site-2025.md` | FAQ do site antes de 03/10/2026 — **REVOGADO** (`vigente: false`) | ninguém | não muda mais |

Cada documento declara isso no próprio cabeçalho (`fonte`, `mantido_por`,
`muda`), e o cabeçalho é lido pelo indexador.

**A pergunta que decide a reconstrução:** a política de moderação muda todo
mês; os outros, raramente. O índice inteiro é reconstruído em uma chamada de
embedding (27 trechos em um lote, `python cli.py preparar`), então a decisão é
**reconstruir tudo a cada mudança de documento** — mais simples e mais barato
do que manter atualização parcial certa.

### O documento revogado

O `faq-site-2025.md` responde duas perguntas do conjunto **do jeito que não
vale mais**: "o anúncio fica ativo por 60 dias" (Q01; os Termos dizem 30) e
"aceito trocas" (Q02; as trocas foram removidas do site em 03/10/2026). Ele
foi posto no corpus de propósito. O que aconteceu (`rag_buscador.json`,
`rag_revogado.json`):

| | Q01 (prazo) | Q02 (trocas) |
|---|---|---|
| **posição do revogado na busca, sem curadoria** | **1º** (sim. 0,872 × 0,800 do vigente) | **1º** (0,808 × 0,756) |
| resposta com k=3, sem curadoria | **certa** (30 dias) — o vigente veio em 2º | **certa** — o vigente diz "retirado em outubro de 2026" |
| resposta com **k=1**, sem curadoria | **errada: "fica ativo por 60 dias"**, citando o revogado | **errada: "sim, marque 'aceito trocas'"** |
| resposta com curadoria (filtro `vigente`) | certa | certa |

**O achado:** o documento revogado não só aparece — ele **vence** o vigente,
porque está escrito em forma de pergunta, como o usuário pergunta. Com k=3 a
resposta saiu certa porque o vigente também entrou no contexto e o modelo
preferiu o mais explícito: isso é sorte de redação, não mecanismo. Com k=1 o
sistema afirma, com citação, uma regra que não existe mais.

**A solução não é técnica de recuperação, é curadoria**: todo documento declara
`vigente`; o revogado fica no índice (para auditoria) mas é filtrado na busca
(`incluir_revogados=False` é o padrão de `rag.buscar`). E a curadoria tem um
dono: quem mantém cada documento (tabela acima) marca o antigo como revogado
quando publica o novo.

## 4.3 As perguntas e o corte

### O corte: por estrutura (uma seção `##` = um trecho)

Os documentos são **regulamentos com seções curtas e autocontidas** (24 a 89
palavras por seção). Cortar por caracteres partiria uma regra da sua exceção:
"…a taxa incide sobre o valor do produto. **Exceção:** frete não entra" está
na mesma seção, e um corte de 200 caracteres com sobreposição a separaria. O
corte por estrutura gera **27 trechos** (3 do revogado), e nenhum precisou ser
quebrado por tamanho. A regra prática que fica para quem escrever o próximo
documento: **a exceção mora na mesma seção da regra**.

### O k: 3

Medido no conjunto (`rag_buscador.json`, com curadoria):

| k | perguntas respondíveis com o trecho certo no contexto |
|---|---|
| 1 | 11 de 13 — perde **Q04** (a exceção do frete, em 2º, atrás de "quando o vendedor recebe") e **Q07** (réplica, em 2º, atrás do brinquedo) |
| **3** | **13 de 13** — o pior caso está em 2º |
| 5 | 13 de 13 — e dobra a janela à toa |

k=1 perde justamente uma **exceção** — o tipo de pergunta em que errar custa
mais. k=3 cobre tudo com margem de uma posição; o custo é ~200 tokens a mais
por consulta.

### O portão de suficiência: limiar 0,67

| | melhor similaridade |
|---|---|
| pior pergunta respondível (Q07) | 0,698 |
| fora do corpus (Q13, ingresso de show) | 0,617 |
| no banco, não no corpus (Q15, preço de geladeira) | 0,642 |

O limiar fica entre 0,642 e 0,698: **0,67**. A margem é estreita (0,056), e é
por isso que o portão não é a única defesa: quando passa do portão, a etapa de
resposta (`resposta-regras-v1.md`) ainda pode declarar `base_suficiente =
false`, e o código **confere as citações** (`rag.verificar_citacoes`): id que
não foi recuperado é descartado, e resposta sem citação válida vira recusa.

**Resultado de ponta a ponta** (`prompts_resposta.json`, busca + resposta das
15 perguntas): **15/15** — as 13 respondíveis com a citação do trecho esperado,
Q13 e Q15 recusadas (as duas pelo portão, sem chamar o modelo de resposta).

### Embedding: 768 dimensões, e não 3072

O `gemini-embedding-001` devolve 3072 dimensões por padrão; pedimos 768
(`EMBEDDING_DIMENSOES`). Com 27 trechos, as 768 dimensões já separaram as 13
respondíveis das 2 não respondíveis; o ganho de 3072 não foi medido e
quadruplicaria o armazenamento da memória episódica, que cresce sem parar.
Está declarado no código porque é um padrão do provedor (§6.6): se o padrão
mudar, nosso índice não muda junto.

## 4.4 Onde a recuperação entra no laço

**Duas formas, uma em cada rota — e é a rota que decide:**

| Rota | Forma | Por quê |
|---|---|---|
| **dúvida** (`buscar_regras` → `responder_regras`) | **etapa fixa** | a pergunta **é** sobre uma regra: toda execução precisa buscar, e uma busca inútil é impossível por construção |
| **Agente B** (`consultar_regras`) | **ferramenta do agente** | a maioria dos anúncios (geladeira, sofá, fogão) não precisa de regra nenhuma; o modelo decide quando o produto ou a dúvida pedem a política |

A segunda é a "memória consultável": a regra fica disponível **para a decisão**
do agente (recusar o item, aceitar a exceção), não para a redação.

**Chamadas de recuperação por execução** (medidas nos logs dos casos,
`final.consultas_rag`):

| Execução | Consultas | Inútil? |
|---|---|---|
| anúncios comuns (casos 1–4, 6, 12, 13) | **0** | — o agente não buscou, e não precisava |
| réplica de airsoft (caso 14) | **3** | **1 inútil**: a 1ª consulta ("réplica de pistola de airsoft", curta) ficou abaixo do limiar e voltou "nenhuma regra responde"; o agente reformulou a pergunta duas vezes e só então recusou, citando `politica-moderacao-2026#1` |
| brinquedo (caso 15) | **1** | não: a exceção (`#2`) é o que permitiu publicar |
| dúvidas (casos 5, 11) | **1** | não por construção (etapa fixa); o caso 5 foi recusado pelo portão |
| Agente A (casos 7, 8) | **0** | o Agente A não usa o corpus |

**O que isso custou de descobrir:** com a v7 do prompt do Agente B, a
ferramenta existia e o agente **nunca** a chamou em 13 casos — certo naqueles
casos, mas sem gatilho para o caso em que devia. E não havia ação para o
resultado ("o item é proibido"). A v8 nomeou os gatilhos (arma, réplica,
droga…) e criou `recusar_item`, que só vale citando uma regra consultada —
conferido em código (`recusar_item` em `src/nos_anuncio.py`).

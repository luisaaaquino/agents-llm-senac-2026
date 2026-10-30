# Exercício 15 — O plano de observabilidade do agente de trocas

**Grupo:** Luisa Vitoria Aquino Nascimento, Maria Erica Joana da Conceição Cruz,
Paulo Henrique Alves Santana e Marcela Andrade

> **Resposta curta à questão do exercício.** O agente **está funcionando** se as
> conversas terminam sem erro e sem esgotar o orçamento (SLO 1). Ele **está
> funcionando bem** se resolve ao menos 60% das conversas sem atendente e
> mantém abaixo de 1% as aprovações fora da política (SLO 2). Os dois números
> saem dos *traces* e de uma auditoria por amostra, sem leitura do código. A
> resposta completa está na seção 6.

## 1. As perguntas

| Interessado | Pergunta | Decisão que a resposta muda |
|---|---|---|
| O negócio | Que parte das conversas o agente resolve sem atendente? | Manter o agente e redimensionar a equipe de atendimento, ou rever a adoção |
| A operação | Que parte das conversas termina em erro ou com o orçamento esgotado, e em qual versão? | Reverter a versão no ar ou acionar o dono da ferramenta que falhou |
| Quem paga | Quanto custa cada conversa resolvida? | Manter o modelo atual ou reduzir o custo (modelo mais barato, menos contexto) |
| Quem responde pelo sistema | Que parte das trocas aprovadas está fora da política? | Suspender o registro automático, encaminhando as trocas ao atendente, e rever as já registradas |

## 2. O *trace* de uma conversa

### A árvore

Conversa típica: o cliente informa o pedido e o motivo na primeira mensagem, e
a troca é aprovada.

```text
invoke_agent agente-de-trocas
├── chat <modelo>                        (o modelo pede consultar_pedido)
├── execute_tool consultar_pedido
├── chat <modelo>                        (o modelo pede consultar_politica)
├── execute_tool consultar_politica
├── chat <modelo>                        (o modelo pede registrar_troca)
├── execute_tool registrar_troca
└── chat <modelo>                        (o modelo responde ao cliente)
```

O case não diz o que conta como passo. Este plano conta cada chamada ao modelo
como um passo, então a conversa típica usa **4 dos 6**. Na recusa e no
encaminhamento, a árvore não tem `registrar_troca` e usa 3 passos.

Cada *span* grava os atributos da convenção listados no enunciado. O nome do
`<modelo>` é o valor de `gen_ai.request.model`.

### Os atributos de domínio, na raiz

| Atributo | Valores | Para que serve |
|---|---|---|
| `agente.termino` | `respondeu`, `orcamento_esgotado`, `erro`, `abandono` | Separa as conversas que terminaram bem das que pararam no meio. Alimenta o SLO 1. |
| `troca.decisao` | `aprovada`, `recusada`, `encaminhada`, `nenhuma` | Diz o que o agente decidiu. É a base da taxa de resolução, que a convenção não tem como conhecer. Alimenta o SLO 2. |
| `troca.dentro_do_prazo` | `true`, `false`, nulo | Diz se a data da compra estava dentro do prazo da categoria. **Quem calcula é o código, não o modelo**, com os dados devolvidos por `consultar_pedido` e `consultar_politica`. Fica nulo se alguma das duas não foi consultada. |

O terceiro atributo é o que torna visível o erro de decisão, porque compara o
que o modelo decidiu com os dados que ele recebeu:

- `aprovada` com `false` ou nulo: troca registrada fora do prazo, ou sem a
  consulta que a justificaria.
- `recusada` com `true`: possível recusa indevida. Pode ser legítima, por causa
  das condições da política, e por isso entra na auditoria da seção 4.

O conteúdo das mensagens **não** é gravado nos *spans*, porque pode trazer dados
pessoais do cliente. A auditoria consulta a conversa no sistema da loja, onde
ela já está sob as regras de acesso da empresa.

## 3. Os modos de falha

| # | Componente | Falha | Tipo | Sinal |
|---|---|---|---|---|
| 1 | Modelo + `registrar_troca` | Aprova fora do prazo: erra a conta das datas ou aceita a palavra do cliente ("comprei semana passada"). A troca fica registrada na loja. | **Silenciosa** | `troca.decisao = aprovada` com `troca.dentro_do_prazo` igual a `false` ou nulo |
| 2 | Modelo | Encaminha demais: depois de uma mudança de versão, passa a encaminhar casos que antes resolvia. Nenhum erro aparece e o cliente é atendido, mas a promessa de 60% deixa de ser cumprida. | **Silenciosa** | Aumento da parte de `troca.decisao = encaminhada`, comparada por `service.version` |
| 3 | `registrar_troca` | Registra em dobro: a ferramenta demora, o modelo chama de novo e a loja fica com duas trocas do mesmo pedido. | **Silenciosa** | Mais de um *span* `execute_tool registrar_troca` no mesmo *trace* |
| 4 | `consultar_pedido` | Fica fora do ar ou estoura o tempo limite, e o agente não consegue decidir. | **Ruidosa** | *Span* `execute_tool consultar_pedido` com status de erro e `error.type`; raiz com `agente.termino = erro` |

## 4. Os objetivos

A janela de 28 dias tem cerca de **14.000 conversas** (500 por dia).

### SLO 1 — Operacional: conversas que terminam bem

| Item | Definição |
|---|---|
| Indicador | Conversas com `agente.termino = respondeu`, divididas pelas conversas com `respondeu`, `orcamento_esgotado` ou `erro` |
| Objetivo | ≥ 97% |
| Janela | 28 dias corridos |

- **Margem de erro:** 3% de 14.000 são 420 conversas ruins na janela, cerca de 15
  por dia.
- **Abandono:** fica fora desta conta, porque o cliente pode sair por motivos
  alheios ao sistema. Ele continua contando contra o SLO 2.
- **Por que não tempo de resposta:** o *trace* inclui as esperas pelo cliente, e
  a duração total mediria também a demora de quem digita.
- **O número é uma aposta inicial:** o case não dá este valor. Os 97% são
  revistos depois das duas primeiras semanas de medição.

### SLO 2 — A promessa: resolver sem aprovar errado

A promessa tem dois números, e os dois precisam valer ao mesmo tempo. Sozinha, a
taxa de 60% poderia ser atingida aprovando tudo.

| Item | 2a. Resolução | 2b. Aprovações fora da política |
|---|---|---|
| Indicador | Conversas com `troca.decisao` igual a `aprovada` ou `recusada`, sem novo contato com o atendimento sobre o mesmo pedido em 7 dias, divididas por todas as conversas | Aprovações fora da política, divididas pelas aprovações auditadas |
| Objetivo | ≥ 60% (cerca de 8.400 conversas na janela) | < 1% |
| Janela | 28 dias, com conversas encerradas há pelo menos 7 dias | 28 dias |

**Por que os 7 dias em 2a.** Sem essa condição, recusar todos os pedidos contaria
como resolver. O cliente recusado sem razão tende a procurar o atendimento, e
esse novo contato tira a conversa da conta. O dado vem do sistema de atendimento,
cruzado pelo número do pedido.

**Como se mede 2b.** O atributo `troca.dentro_do_prazo` confere o prazo de todas
as aprovações, mas não enxerga duas coisas: as **condições** da política (por
exemplo, produto sem uso) e uma `consultar_politica` que devolva uma regra
**desatualizada**, já que ele usa essa mesma resposta. Por isso:

- Atendentes auditam **300 aprovações sorteadas** por janela, cerca de 11 por
  dia, comparando cada uma com a política oficial.
- O tamanho vem da "regra de três" da estatística: zero erros em 300 casos indica,
  com cerca de 95% de confiança, uma taxa real abaixo de 1%. Se a auditoria achar
  erros, a amostra aumenta antes de concluir.
- As recusas com `troca.dentro_do_prazo = true` também são revistas por
  amostragem. Elas não entram no indicador 2b, mas mostram se o agente está
  recusando trocas que deveria aprovar.

## 5. Os alertas

### Alerta de custo

| Item | Definição |
|---|---|
| Condição | Custo por conversa resolvida no dia anterior: custo total das conversas (tokens de entrada e de saída × preço) dividido pelas conversas com `troca.decisao` igual a `aprovada` ou `recusada` |
| Limiar | Acima de **C / 0,60 ≈ 1,67 C**, em que C é o custo médio por conversa medido nas duas primeiras semanas |
| Quem é avisado | Quem paga pelo agente (o dono do orçamento), com cópia para o responsável pelo agente |
| O que essa pessoa faz | Olha o custo médio por conversa. Se ele subiu, pede ao responsável que compare o consumo de tokens por versão e por número de passos, e decide entre reverter a versão ou reduzir o custo. Se ele não subiu, o custo por conversa resolvida aumentou porque a resolução caiu, e o problema é passado ao responsável como degradação. |

**De onde vem o limiar.** Do SLO 2a: se cada conversa custa C e 60% são
resolvidas, cada conversa resolvida custa C / 0,60. Acima disso, ou a conversa
ficou mais cara, ou a resolução caiu abaixo do prometido. O valor de C não está
no case, porque depende do modelo e do preço contratados, e só é alterado por
decisão explícita, para que um aumento gradual de custo não vire o novo normal.

Este alerta usa a decisão do próprio dia, sem esperar os 7 dias do SLO 2a, porque
o custo precisa de resposta rápida.

### Alerta de degradação silenciosa

| Item | Definição |
|---|---|
| Condição | Aprovações com `troca.dentro_do_prazo` igual a `false` ou nulo, divididas por todas as aprovações, nas últimas 24 horas |
| Limiar | Acima de **1%** (SLO 2b), com no mínimo **3 casos** |
| Quem é avisado | O responsável pelo agente |
| O que essa pessoa faz | Abre os *traces* dos casos e compara a versão no ar com a anterior. Se forem erros reais, reverte a versão ou suspende o registro automático, encaminhando as trocas ao atendente. Depois, envia à loja a lista das trocas para revisão. |

**Por que no mínimo 3 casos.** Com 500 conversas por dia e 60% de resolução, há no
máximo cerca de 300 aprovações por dia, e 1% disso são 3 casos. O mínimo evita
acionar alguém por um único caso em um dia de poucas aprovações.

Este alerta é um **piso**: vê só os erros de prazo. Os erros de condição e de
política desatualizada aparecem na auditoria do SLO 2b, em ritmo mais lento.

## 6. A resposta à questão

**Como saber, sem ler o código, se o agente de trocas está funcionando — e se
está funcionando bem?**

Observando o que ele fez, e não como foi escrito. Cada conversa gera um *trace*
com a decisão do agente, o modo como a conversa terminou e uma conferência de
prazo feita pelo código, independente do modelo.

- **Está funcionando?** O SLO 1 responde: pelo menos 97% das conversas terminam
  sem erro e sem esgotar o orçamento.
- **Está funcionando bem?** O SLO 2 responde: pelo menos 60% das conversas são
  resolvidas sem atendente, com menos de 1% de aprovações fora da política.

A distinção importa porque as falhas mais caras deste agente são silenciosas. Um
agente que aprova trocas indevidas responde rápido e sem nenhum erro: ele passa no
SLO 1 e só é pego pelo SLO 2. Para esse erro, *traces* não bastam, e a auditoria
humana continua necessária, pois só ela compara a decisão com a política oficial.

O caminho de cada pergunta até a ação:

| Pergunta (interessado) | Sinal | Objetivo | Quem age, e quando |
|---|---|---|---|
| Resolve sem atendente? (negócio) | `troca.decisao` + novo contato em 7 dias | SLO 2a | O negócio, ao revisar a janela de 28 dias |
| Termina bem? (operação) | `agente.termino` | SLO 1 | A operação, ao ver o SLO 1 em risco |
| Quanto custa cada resolução? (quem paga) | `gen_ai.usage.*` + `troca.decisao` | Limiar derivado do SLO 2a | O dono do orçamento, pelo alerta de custo |
| Aprova fora da política? (quem responde) | `troca.dentro_do_prazo` + auditoria | SLO 2b | O responsável pelo agente, pelo alerta de degradação |

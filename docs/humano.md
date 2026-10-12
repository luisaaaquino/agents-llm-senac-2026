# Human-in-the-loop — onde o grafo para (§8)

O humano entra no grafo como **código que para e espera**: um `interrupt`
dentro de um nó, um checkpoint gravado em SQLite, e uma retomada com
`Command(resume=...)` que pode chegar horas depois, de outro processo.

## 8.1 Os pontos de parada e o critério de cada um

São **dois**, ambos no Agente B. Marcados com `⏸` no diagrama de
`docs/arquitetura.md` §6.1.

| # | Nó | Critério | Perfil chamado | Prazo | Se ninguém responder |
|---|---|---|---|---|---|
| 1 | `aprovacao_vendedor` | **ação que sai para o mundo**: o anúncio fica visível para os compradores dos 18 bairros, com o nome do vendedor e o local de retirada | o **vendedor dono da conversa** (`responsavel` = `usuario_id` da thread) | 24 h (`PRAZO_APROVACAO_VENDEDOR_H`) | **não publica**; o rascunho fica salvo na thread |
| 2 | `moderacao` | **confiança baixa**: a conversa revelou um defeito que o vendedor se recusou a declarar — o sistema não tem base para decidir se o anúncio pode ir ao ar sem ele | **moderador** (id `M-…`) | 48 h (`PRAZO_MODERACAO_H`, o mesmo da `politica-moderacao-2026#5`) | **não publica**; o anúncio vira `rejeitado`, o indício vira `expirado`, o vendedor é avisado de que pode refazê-lo declarando o estado |

**Por que publicar pede aprovação, se a escrita é reversível** (o vendedor
pode pausar depois): reversível para o vendedor não é reversível para o mundo.
Entre publicar e pausar, compradores viram o anúncio, mandaram mensagem, podem
ter ido ao endereço. É uma escrita **pública** com o nome de uma pessoa — o
primeiro critério do §8.1 ("escreve em sistema de terceiro, envia mensagem")
vale por analogia.

**Por que o Agente A não para nunca:** ele não escreve nada. A ação mais
perigosa dele é **sugerir um item errado** (vendido, de outro bairro, acima do
orçamento) — e as três coisas são conferidas em código antes de sair
(`conferir_sugestao`, filtro `status = 'ativo'`). Um erro do A custa um clique
do comprador; não move dinheiro nem expõe ninguém.

**O que não tem critério de custo:** nenhuma ação do sistema move dinheiro (o
pagamento é do site, pelo Mercado Pago). O teto de custo existe para o
**gasto com o modelo** (`B_MAX_CUSTO_USD`), e estourar ele encerra a execução
em `orcamento` — não pede aprovação.

## 8.2 O que a pessoa vê, e o que ela devolve

O que aparece na pausa é montado em código (`preparar_aprovacao`,
`preparar_moderacao` em `src/nos_anuncio.py`) e vai inteiro no
`SaidaSistema.dados.pendencia`. Nada de "confirma?": a ação, os argumentos e a
consequência.

**Ponto 1 — o vendedor vê** (a estrutura; o objeto real, com os textos, está em `docs/io.md`, exemplo 1, e em `logs/06_aprovacao_editando.json`):

```json
{
  "tipo": "aprovacao_vendedor",
  "perfil": "vendedor",
  "responsavel": "V-022",
  "acao": "publicar_anuncio",
  "argumentos": {"titulo": "...", "categoria": "sofá", "descricao": "...", "preco": 300.0,
                 "bairro": "Santo Amaro", "estado_conservacao": "marcas_de_uso",
                 "avarias_declaradas": ["..."]},
  "consequencia": "O anúncio \"...\" por R$ 300.00 fica visível para os compradores dos 18 bairros, com retirada em Santo Amaro. Você pode pausar ou editar depois.",
  "opcoes": {"aprovar": {}, "editar": {"campos": ["descricao", "estado_conservacao", "preco", "titulo"]},
             "rejeitar": {"motivo": "texto livre"}},
  "expira_em": "...",
  "se_ninguem_responder": "o anúncio NÃO é publicado; o rascunho fica salvo nesta conversa"
}
```

(o objeto completo, com os textos reais, está no log.)

**Ponto 2 — o moderador vê:** o indício, **a fala literal do vendedor** (a
evidência, como ele disse), o rascunho, o id do anúncio e do indício, a
consequência de cada opção e o prazo (`logs/04_avaria_negada.json`).

**As respostas aceitas** (`responder_pendencia` em `src/sistema.py`):

| Ponto | Respostas | Observação |
|---|---|---|
| 1 | `aprovar` · `editar` (com `campos`) · `rejeitar` | **aprovar editando**: o vendedor corrige `titulo`, `descricao`, `preco` ou `estado_conservacao` antes de deixar seguir. Campo fora da lista é ignorado e registrado (`edicoes_ignoradas`) |
| 2 | `publicar` · `publicar_com_aviso` (com o texto do `aviso`, editável) · `rejeitar` | o aviso editado é o "aprovar editando" da moderação |
| ambos | `expirou` | só o sistema envia (`quem = "sistema:prazo"`) |

**Quem pode responder é conferido em código:** no ponto 1, só o
`responsavel`; no ponto 2, só id com perfil de moderador. Um vendedor tentando
responder à própria moderação recebe `erro` e nada é retomado (aconteceu de
verdade num teste do caso 15, quando o roteiro mandou a aprovação do vendedor
para uma pendência que era de moderação).

## 8.3 A implementação, e por que ela depende do checkpoint

```
preparar_aprovacao  [código]  monta a pendência, abre o prazo (tabela pendencias_humanas)
        │
aprovacao_vendedor  [HUMANO]  resposta = interrupt(pendencia)      ← SÓ isto
        │
publicar            [código]  aplica as edições e grava (idempotente)
```

- A pausa é `interrupt(...)` dentro do nó; a retomada é uma nova invocação com
  `Command(resume={...})`, e o valor vira o retorno do `interrupt`.
- **O nó do interrupt re-executa inteiro na retomada.** Por isso nada com
  efeito colateral fica nele: abrir a pendência é no nó **anterior**; gravar o
  anúncio é no nó **posterior**. As duas escritas são idempotentes de qualquer
  forma (abaixo).
- **Checkpointer:** `SqliteSaver` (`langgraph-checkpoint-sqlite`), gravando em
  `dados/checkpoints.db`, endereçado por `thread_id = "<usuario>:<sessao>"`. A
  pausa sobrevive à morte do processo: a aprovação pode chegar por outro
  processo (`python cli.py responder <thread> '<json>' <quem>`).
- **Limitação declarada:** SQLite local, um arquivo. Em produção com mais de um
  servidor, o checkpointer teria de ser Postgres (há `langgraph-checkpoint-postgres`).

## 8.4 O que acontece se ninguém responder

- Cada pendência tem `expira_em`, gravado na tabela `pendencias_humanas`.
- `rotina_prazos(agora)` (`src/sistema.py`) lista as vencidas e retoma cada uma
  com `{"acao": "expirou"}` — o caminho do silêncio é **o mesmo grafo**, não um
  atalho: o nó `aplicar_moderacao` (ou `finalizar_b`) grava o desfecho
  `expirou`, fecha a pendência, escreve memória e devolve a saída para avisar
  a pessoa.
- **Resposta que chega depois do prazo não vale**: `responder_pendencia`
  confere o `expira_em` e converte a resposta tardia em `expirou` (guarda a
  resposta tardia no registro). O silêncio não fica "em aberto" esperando a
  rotina passar.
- Em produção a rotina rodaria agendada (ex.: a cada hora). Aqui ela é chamada
  com o relógio simulado: `python cli.py prazos +49` — e é o que o
  **caso 12** faz (`logs/12_moderacao_sem_resposta.json`): moderação aberta,
  ninguém responde, a rotina roda 49 h depois, anúncio não publicado.

**Por que o silêncio = não publicar** (e não "publica por padrão"): um ponto de
parada que segue adiante sozinho deixa de cumprir a função. No ponto 1 o
vendedor só perde tempo (o rascunho fica); no ponto 2, publicar por padrão
seria publicar exatamente o anúncio de que o sistema desconfiou.

## 8.5 Aprovar duas vezes

Duas proteções, independentes, as duas demonstradas no **caso 6**
(`logs/06_aprovacao_editando.json`, campo `prova_idempotencia`):

1. **Idempotência por estado** — a segunda aprovação, chegando depois da
   primeira, não encontra pendência aberta na thread (`_pendencia_aberta`) e
   não retoma nada: devolve "Essa decisão já foi registrada; nada foi feito de
   novo". O número de anúncios antes e depois é o mesmo.
2. **Idempotência por conteúdo** — o caso que a primeira não cobre: o nó
   `publicar` **executar de novo** (o processo morre depois de gravar no banco
   e antes de gravar o checkpoint, e a execução é refeita a partir do
   checkpoint anterior). O caso 6 faz exatamente isso: volta ao checkpoint
   anterior a `publicar` (`get_state_history`) e re-executa. A chave
   (`chave_anuncio` em `src/db.py`: sha256 de vendedor + título + categoria +
   descrição + preço + bairro) é a mesma, e o banco devolve
   `{"ja_existia": true, "anuncio_id": <o mesmo>}`. Contagem de anúncios
   na rodada final: **21 → 21 → 21** (antes da 2ª aprovação, depois dela, depois
   de re-executar `publicar`); `ja_existia` das duas execuções de `publicar`:
   `[false, true]`.

**Por que a chave inclui o preço:** "aprovar editando" muda o conteúdo — se o
vendedor editou o preço de 300 para 280, é outro anúncio, e é o de 280 que vai
ao ar uma vez só. A mesma aprovação repetida tem o mesmo conteúdo e cai na
mesma chave.

**O que a re-execução revelou:** o anúncio não duplicou, mas o **episódio de
memória** sim — a chave dele dependia do texto do modelo. Corrigido depois
(`docs/memoria.md` P2.2, defeito 2).

O indício de avaria tem a mesma proteção (`registrar_indicio`: chave de
vendedor + thread + texto do indício). Isso foi exercitado sem querer: numa
rodada de desenvolvimento o modelo chamou `registrar_indicio` duas vezes
seguidas, e a segunda devolveu `ja_existia: true` — um indício só na fila.

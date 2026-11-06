# Histórico de mudanças (§0)

Cada versão do sistema tem um número em `src/config.py` (`VERSAO_SISTEMA`),
que vai em todo trace (`service.version` e `santo.versao_sistema`) e em toda
rodada da avaliação (`evals/resultados/v<versão>_<data>/resultado.json`). É
esse número que permite comparar resultados entre versões.

A correção da Parte 2 ainda não tinha sido devolvida quando esta entrega foi
feita. As correções da versão 2.1.0 são as limitações que nós mesmos tínhamos
documentado em `docs/io.md` ("Limitações do contrato, conhecidas e não
corrigidas").

| Versão | Commit | O que mudou |
|---|---|---|
| 2.0.0 | `1a5cd36` | Sistema entregue na Parte 2 (os logs de `logs/01…15` são desta versão). |
| 2.1.0 | `2716d5e` | Correções da Parte 2, traces OpenTelemetry e suíte de avaliação. Sem mudança de comportamento além das correções abaixo. |
| 3.0.0 | `12329c9` | Os três controles de segurança do `docs/seguranca.md` §3.2 e a suspensão do agente. |

## 2.1.0 — correções da Parte 2

**1. As fontes da recusa de item listavam regras que não sustentavam a recusa.**
- *O que estava errado:* no caso 14 (réplica de airsoft), a recusa citava
  `politica-moderacao-2026#1`, mas `fontes` trazia os três trechos consultados,
  inclusive a exceção do brinquedo (`#2`), que não tem nada a ver com a recusa.
- *O que mudou:* em `finalizar_b` (`src/nos_anuncio.py`), quando o desfecho é
  `item_proibido`, só entra em `fontes` a regra citada (`decisao_b.regra_citada`).
- *Como se confere:* o caso `14_item_proibido` da suíte tem a checagem
  `fontes_exatas: ["politica-moderacao-2026#1"]`.

**2. `suficiencia.faltando` vinha vazio quando o Agente B fazia uma pergunta.**
- *O que estava errado:* a saída dizia "falta informação essencial" sem dizer qual.
- *O que mudou:* `perguntar_b` (`src/nos_anuncio.py`) preenche `faltando`: "se
  o produto tem algum defeito ou avaria" (pergunta do portão), "se o vendedor
  mantém o preço…" (aviso de faixa) ou a própria pergunta do modelo.

**3. Erro de ferramenta derrubava o turno sem resposta.**
- *O que estava errado:* `_executar` (`src/sistema.py`) só tratava os erros do
  modelo; um erro de banco ou de índice subia como exceção, sem `SaidaSistema`
  (achado do exercício 14, ASI08).
- *O que mudou:* qualquer outra exceção vira saída `erro` com término
  `erro_fatal` e o motivo `erro_ferramenta: ...`.

**4. Instrumentação (não muda o comportamento).**
- `src/observabilidade.py`: spans `invoke_agent`, `chat` e `execute_tool` nas
  convenções GenAI do OpenTelemetry (`docs/observabilidade.md`).
- `evals/`: o golden dataset e a suíte (`docs/evals.md`).

## 3.0.0 — controles de segurança

Detalhes, testes e o que cada controle custou em `docs/seguranca.md` §3.2.

| Controle | Risco | Onde |
|---|---|---|
| C1. Moderador conferido numa tabela, e não pelo prefixo "M-"; o vendedor não modera o próprio anúncio; a rotina de prazos só responde "expirou" | ASI03 | `src/sistema.py` (`autorizar`), `src/db.py` (`eh_moderador`), `dados/seed.sql` (tabela `moderadores`) |
| C2. A memória da categoria só guarda o aviso escrito pelo moderador, e recusa texto com cara de instrução | ASI06 | `src/memoria.py` (`avaria_segura`, `gravar_fato`), `src/nos_anuncio.py` (`_escrever_memoria`) |
| C3. A edição feita na aprovação é validada e não apaga o defeito declarado | ASI02 | `src/nos_anuncio.py` (`aplicar_edicoes`) |

Também mudou: a resposta de quem não tem permissão sai como `recusa` /
`recusou` (motivo `nao_autorizado: ...`), e não mais como `erro_fatal`. Antes,
um acesso negado e uma pane apareciam iguais nas métricas.

Também entrou: a suspensão do agente pelo operador (`SANTO_SUSPENSO=1`,
`src/config.py` e `src/sistema.py`), com teste em `tests/test_autoridade.py`.

**O que a avaliação mostrou** (`docs/evals.md` §4): média de 90,0% para
96,7%; a classe `seguranca` foi de 66,7% para 100% (casos 23 e 26 bloqueados).
A classe `compra` caiu de 100% para 75% por um defeito do portão do Agente A
que a variação do modelo expôs (caso 08), sem relação com os controles: o
código do Agente A não mudou entre as duas versões.

## Achados desta entrega que ainda não foram corrigidos

- O portão do Agente A aceita `categorias: ["outro"]` com `faltando` preenchido (caso 08).
- O laço da consulta de preço voltou a aparecer (caso 13 da 2.1.0).
- O C3 deixa a frase falsa na descrição editada, ao lado do defeito declarado (caso 26 da 3.0.0).
- O caso 25 da suíte não exercita o controle C2.
- A rubrica do juiz não trata o estado de conservação que o vendedor não declarou.

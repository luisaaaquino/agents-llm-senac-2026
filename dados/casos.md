# Casos de teste — Parte 2 (§9 do enunciado)

Os roteiros (a primeira fala, as respostas da pessoa e o que ela faz quando o
grafo para) estão em `src/casos.py`. As falas são mock; tudo o mais — as
perguntas, as ferramentas, as decisões — é execução. O que deve acontecer
foi escrito **antes** de rodar (campo `esperado` de cada caso, que vai junto
no log). O resultado real, com o commit e a data de cada execução, está em
`docs/io.md` (tabela dos casos) e nos logs de `logs/`.

## Os seis do §9

| # | Caso | O que prova | Esperado |
|---|---|---|---|
| 1 | `01_simples` — geladeira R$ 350, Santo Amaro | o caminho feliz existe | pergunta de avaria → preço → rascunho → aprovação → publicado |
| 2 | `02_divergencia_preco` — R$ 900 numa faixa R$ 300–380 | o sistema diz uma coisa, o vendedor outra | avisa a faixa, respeita a alçada, publica a R$ 900, **sem** indício |
| 3 | `03_sem_registro` — bicicleta (sem comparáveis no banco) | erro de ferramenta que o agente contorna | `sem_comparaveis` uma vez, segue com o preço do vendedor, publica |
| 4 | `04_avaria_negada` — "o freezer demora pra congelar, mas prefiro não pôr" | o sistema sabe **não** agir | registra indício, **não publica**, para na moderação; moderador decide |
| 5 | `05_fora_do_corpus` — "posso vender ingresso de show?" | recusa, e recusa dizendo algo útil | portão do RAG recusa sem chamar o modelo; diz o que tem de mais perto |
| 6 | `06_aprovacao_editando` — sofá com rachadura declarada | pausa, aprovar editando, aprovação repetida | vendedor edita o preço para R$ 280; 2ª aprovação não cria nada; re-execução de `publicar` devolve `ja_existia` |

## Os exemplos do contrato (§1.3, §1.4) e as medições

| # | Caso | O que mostra |
|---|---|---|
| 7 | `07_compra_cozinha` | caminho feliz do Agente A: busca paralela, soma conferida contra o orçamento |
| 8 | `08_incompleta` | entrada incompleta: pergunta o que falta, depois atende |
| 9 | `09_ambigua` | entrada ambígua: pergunta por onde começar |
| 10 | `10_fora_escopo` | fora do escopo: recusa e diz o que faz |
| 11 | `11_duvida_excecao` | dúvida cuja resposta depende de uma exceção, com citação |
| 12 | `12_moderacao_sem_resposta` | ninguém responde: o prazo de 48 h vence e não publica |
| 13 | `13_memoria_avaria_tipica` | depois do caso 4, a memória muda a pergunta (cita o freezer) |
| 14 | `14_item_proibido` | o agente decide consultar a regra e recusa citando-a |
| 15 | `15_excecao_brinquedo` | a regra tem exceção: consultar antes de recusar evita recusar o permitido |

**Os casos difíceis nomeados** (§2.8 do case): divergência — casos 2 e 4;
registro inexistente — caso 3; não deve disparar a ação principal — casos 4,
12 e 14.

**Ordem importa:** o caso 13 depende da memória escrita pelo caso 4 (a
moderação confirma o defeito); `python cli.py casos` roda na ordem.

Os casos da Parte 1 (com o resultado do `qwen2.5:7b`) estão no histórico
(`git show 6aa8cfb:dados/casos.md`) e os logs deles em `logs/parte1/`.

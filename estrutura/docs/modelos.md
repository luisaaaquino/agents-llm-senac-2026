# Análise de modelos (§3)

> **Status: rascunho a preencher.** A estrutura e os eixos do case já estão aqui;
> faltam os números reais (preços atuais e a rodada dos 5 casos). Não inventem —
> rodem e colem.

## 3.1 Candidatos e eixos do case

Três candidatos: **[modelo 1]**, **[modelo 2]**, **[modelo 3]**.
(Ex.: `mistral-small` dos laboratórios, um modelo local via Ollama, e um terceiro.)

Eixos que importam **para o Agente B**, e por quê:

| Eixo | Por que importa aqui |
|------|----------------------|
| tool calling + saída estruturada | pré-requisito: o agente decide ações e devolve JSON estrito (schema). Sem isso não há agente. |
| custo por milhão de tokens (in/out) | são ~4–6 chamadas por anúncio (conversa + avaliador); o custo multiplica. |
| latência | o vendedor espera na tela durante o cadastro. |
| capacidade de raciocínio | precisa inferir a avaria omitida a partir de pistas, não classificar direto. |
| onde roda / política de dados | dado do vendedor é sensível (§2.9); Ollama local evita enviar para fora. |

Janela de contexto e multimídia **não** entram: a conversa é curta e só-texto.

## 3.2 A conta (por execução)

```
tokens_entrada × nº_chamadas × preço_entrada
+ tokens_saida  × nº_chamadas × preço_saida
= custo por execução (um anúncio)
```

Estimativa a preencher (medir tokens numa execução real com o log):

| | por chamada | nº chamadas/anúncio | preço | subtotal |
|--|--|--|--|--|
| entrada | [TODO] | ~5 | [TODO R$/Mtok] | [TODO] |
| saída | [TODO] | ~5 | [TODO R$/Mtok] | [TODO] |

Custo por execução: **[TODO]** · por 100 execuções: **[TODO]** · semestre: **[TODO]**.

## 3.3 Verificação mínima — 5 casos nos 3 modelos

Rodem os 5 casos do domínio (podem ser os 4 de `dados/casos.md` + 1) com o
**mesmo prompt** nos três candidatos e colem o resultado:

| Caso | Modelo 1 | Modelo 2 | Modelo 3 |
|------|----------|----------|----------|
| 1 simples (publica) | [ok?] | | |
| 2 divergência de preço (confronta?) | | | |
| 3 sem comparáveis (contorna o erro?) | | | |
| 4 avaria negada (encaminha à moderação?) | | | |
| 5 [escolher] | | | |

## 3.4 Decisão

Modelo escolhido: **[TODO]**, porque **[TODO]**.
Mudaríamos de ideia se: **[TODO]** (ex.: se o custo por execução passar de R$ X,
ou se o modelo local não acertar o caso 4 da tabela).

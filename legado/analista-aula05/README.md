> **Nota:** esta pasta é o *lab da Aula 05* (analista de prestação de contas).
> **Não é o trabalho** (que é o Santo Desapego, na raiz). Está aqui porque foi
> deste código que veio o scaffolding reaproveitado em `src/agente_anuncio.py`.

# Exercício 05 — Analista de prestação de contas

Implementação do Exercício 05 da Aula 05.

## Arquivos

- `08-analista.py`
- `prompts/router-v1.md`
- `prompts/agente-v1.md`
- `prompts/orquestrador-v1.md`
- `prompts/avaliador-v1.md`

## Execução

Na raiz do repositório:

```powershell
.venv\Scripts\Activate.ps1
python analista\08-analista.py
```

O projeto usa as variáveis do `.env` da raiz:

```text
OPENAI_API_KEY=
LLM_BASE_URL=
LLM_MODELO=
LLM_MODELO_GRANDE=
```

Para Ollama, use a configuração `.env.ollama` fornecida pelo laboratório e confirme que o modelo configurado está disponível.

## O que o código demonstra

1. Regra determinística para os casos simples.
2. Portão para validação de fatos antes do modelo.
3. Router com quatro rotas.
4. Agente com estado e orçamento de passos, tokens e tempo.
5. Detector de laço.
6. Escrita idempotente em `registrar_parecer`.
7. Orquestrador-trabalhador com `MAX_SUBTAREFAS`.
8. Avaliador-otimizador com critério booleano e `MAX_RODADAS`.
9. Carimbo de prompt, modelo e parâmetros.

O log real deve ser gerado executando o programa. Não foram incluídas execuções inventadas.

## Ordem das etapas — portão antes da regra

A triagem roda o **portão antes da regra determinística**. O portão valida os
fatos (o funcionário existe? o valor declarado bate com o recibo?) antes de
qualquer decisão automática. Se a regra rodasse primeiro, um item com valor
divergente do recibo (ex.: D-4475, R$ 96 declarado × R$ 196 no recibo) poderia
ser aprovado sem que o portão chegasse a conferi-lo — porque a regra aprovaria e
a execução seguiria para o próximo item. A saída de uma etapa é a entrada da
seguinte, e é nessa junção que o sistema quebraria; por isso o portão vem primeiro.

Casos-limite plantados nos dados, e o que deve acontecer:
- **D-4475** — valor declarado diverge do recibo → **BARRADO** no portão.
- **D-4477** — funcionário `F-88` inexistente (o correto é `F-088`) → **BARRADO** no portão.

## Sobre a execução dos testes

O código foi validado estaticamente (compila, importa, e a lógica determinística
— regra, portão, idempotência, detector de laço — foi exercitada sem o modelo).
As etapas que dependem de LLM (router, agente, orquestrador, avaliador) **não
foram executadas de ponta a ponta** porque a chave da API da Mistral estava
indisponível no momento da entrega. O log real dessas etapas deve ser gerado
quando a API voltar (ou via Ollama), rodando `python aula05-agentes/08-analista.py`.

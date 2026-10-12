# Regras aprendidas (memória procedural)

- Se `consultar_preco` devolver `sem_comparaveis`, não repita a consulta: siga com o preço do vendedor e diga que não há referência no bairro.
- Pergunte sobre defeito ou avaria antes do rascunho, mesmo quando a primeira fala já traz produto, preço e bairro.
- Quando houver avarias típicas da categoria na memória, pergunte por elas pelo nome, não com "tem algum defeito?".

---
Memória procedural do Agente B (docs/memoria.md §1.3). Anexada inteira ao
system prompt, sempre. Teto: 5 regras, ~100 tokens.

Origem de cada regra — todas tiradas de erros REAIS da Parte 1, aprovadas
pelo grupo (nenhuma veio de texto do vendedor):
1. caso 3 da Parte 1 (laço em `consultar_preco` com `sem_comparaveis`).
2. casos 4 e 5 da Parte 1 (o agente pulou a pergunta de avaria).
3. projeção do docs/memoria.md §1.3 (pergunta específica > pergunta genérica).

A regra do acento ("sofá") da Parte 1 saiu daqui: virou código — a categoria
agora é um Literal com vocabulário fechado (src/db.py, CATEGORIAS). Regra que
virou código deixa a memória (§2.2, decaimento da procedural).

Regras novas chegam pela fila `regras_candidatas` (src/memoria.py) e só
entram neste arquivo por edição humana revisada.

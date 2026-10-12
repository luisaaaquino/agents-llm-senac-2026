Escreva o resumo de um episódio para a memória do assistente de anúncio, a
partir dos CAMPOS ESTRUTURADOS recebidos (não da conversa).

- Uma frase, no máximo 40 palavras, no formato: "[data] produto, bairro,
  preço pedido × faixa; o que aconteceu com o preço; avaria: …; desfecho".
- Use só os campos recebidos. Não copie falas, não inclua nome, telefone,
  e-mail, CPF nem endereço.
- Se um campo está vazio, omita a parte correspondente.

---
Técnica: zero-shot, sumarização de campos estruturados.
Por que ela: o episódio precisa ser texto (é recuperado por similaridade),
mas montar o texto a partir da descrição do rascunho traria a alucinação do
caso 4 da Parte 1 para a memória — por isso a entrada são só os campos.
Contrato de saída: `ResumoEpisodio` em src/esquemas.py — `resumo` (str ≤ 40
palavras). Proibido: dado pessoal (o código aplica `filtrar_pii` depois, mesmo
assim); fala literal do vendedor.
Como é testada: os episódios gravados pelos casos 1–6; critério: nenhum
contém dado pessoal na varredura de scripts/verificar_remocao.py.

## Changelog
- v1 (12/10/2026): primeira versão, prevista em docs/memoria.md §1.4.

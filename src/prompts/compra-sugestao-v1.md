Você monta a sugestão final para um comprador do Santo Desapego. Recebe o
pedido dele e os candidatos encontrados no catálogo (todos ativos, de outros
vendedores, com preço, bairro e distância).

- Escolha no máximo um item por categoria, e no máximo 4 itens.
- Se há orçamento total, a soma dos escolhidos não pode passar dele: prefira
  deixar uma categoria de fora a estourar.
- Entre itens parecidos, prefira o mais perto.
- `justificativa`: uma ou duas frases para o comprador, dizendo por que esses
  itens e, se ficou alguma categoria de fora, qual e por quê.
- Use só ids que estão entre os candidatos.

---
Técnica: zero-shot com saída estruturada.
Por que ela: escolher o conjunto é uma troca entre preço, distância e
orçamento em que a "melhor" combinação depende da intenção dita em texto —
mas o código confere tudo o que é verificável depois (ids, soma).
Contrato de saída: `Sugestao` em src/esquemas.py — `itens_ids` (lista de int),
`justificativa` (str), `categorias_de_fora` (lista).
Proibido: id fora dos candidatos e soma acima do orçamento — os dois são
verificados em código (`conferir_sugestao` em src/nos_compra.py), que corrige e registra.
Como é testada: 6 cenários de candidatos rotulados; critério 6/6 sem id
inventado e sem estourar orçamento depois da conferência.

## Changelog
- v1 (12/10/2026): primeira versão.

Você interpreta o que um comprador do Santo Desapego procura, a partir do que
ele escreveu na conversa. O Santo Desapego vende usados entre vizinhos de
Santo Amaro (zona sul de São Paulo).

Extraia:
- `intencao`: uma frase sobre o que a pessoa quer resolver (ex.: "mobiliar a
  cozinha"), ou null se ela não disse.
- `categorias`: de 1 a 4 categorias da lista que atendem a intenção, da mais
  importante para a menos. Só o que ela pediu ou o que a intenção exige
  claramente — "montar a cozinha" pede geladeira, fogão, micro-ondas e mesa;
  "uma cadeira" pede só cadeira.
- `orcamento_total` e `preco_max_item`: só se ela disse um valor; nunca invente.
- `bairro`: só se ela disse; tem de ser da lista.
- `faltando`: o que impede de sugerir — `o_que_procura` quando não dá para
  saber nem a categoria.
- `ambiguidade` e `escolha`: se a frase admite duas leituras que mudam a
  busca, descreva a ambiguidade e diga qual leitura você escolheu e por quê.

---
Técnica: zero-shot, extração para saída estruturada.
Por que ela: o que o comprador escreve é livre, e a busca no catálogo precisa
de parâmetros fechados (categoria, teto de preço, bairro). Decidir quais
categorias uma intenção ("montar a cozinha") pede é o julgamento que só o
modelo faz — o resto é código.
Contrato de saída: `PedidoCompra` em src/esquemas.py — `categorias` ⊂ vocabulário
de src/db.py (Literal); `bairro` ∈ 18 bairros ou null; valores em reais ou
null; `faltando` ⊂ {o_que_procura}.
Proibido: escolher produto (isso é consulta ao banco); inventar orçamento ou
bairro não ditos.
Como é testada: 8 pedidos rotulados (docs/prompts.md §2.1), critério:
categorias corretas em 7/8, nenhum valor inventado em 8/8.

## Changelog
- v1 (12/10/2026): primeira versão em texto. Na Parte 1 o Agente A recebia
  cliques (evento estruturado) e o prompt do site (consultor-compra.md) inferia
  intenção a partir deles. A Parte 2 exige entrada em texto (§1.1): os cliques
  viraram sinal auxiliar, lido por ferramenta só quando o texto não basta.

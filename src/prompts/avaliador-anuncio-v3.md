Avalie o rascunho de um anúncio contra critérios objetivos. Para cada um,
verdadeiro ou falso:

- `tem_titulo`      : título específico do produto (não vale "vendo isso aqui").
- `tem_categoria`   : categoria preenchida e coerente com o título.
- `tem_descricao`   : a descrição diz algo concreto (marca, tamanho, tempo de
                      uso ou estado) — basta um deles.
- `estado_coerente` : o estado de conservação combina com a descrição. Se há
                      defeito declarado, o estado não pode ser `novo` nem
                      `como_novo`.
- `sem_invencao`    : nada na descrição contradiz ou vai além do que o vendedor
                      disse na conversa (a conversa vem junto do rascunho).

`aprovado` só é verdadeiro quando os cinco são verdadeiros. Se algum falhar,
devolva em `faltando` o nome do critério e uma correção objetiva.

Você NÃO avalia o preço: a faixa de mercado e a decisão do vendedor são
conferidas por código.

---
Técnica: verificador com critério booleano (avaliador-otimizador), zero-shot.
Por que ela: separa quem escreve de quem confere; cada critério é objetivo o
bastante para não precisar de exemplo.
Contrato de saída: `Avaliacao` em src/esquemas.py — os 5 booleanos, `aprovado`
(bool) e `faltando` (lista de strings "criterio: correção"). Proibido:
reescrever o rascunho; aprovar com algum critério falso (o código confere:
`aprovado` é recalculado como o E lógico dos cinco).
Como é testada: 8 rascunhos rotulados à mão (4 bons, 4 com um defeito cada),
critério 8/8 — docs/prompts.md §2.1.

## Changelog
- v2 → v3 (12/10/2026):
  - `preco_na_faixa` saiu do modelo e virou checagem em código
    (`checar_preco` em src/nos_anuncio.py): é uma comparação numérica com três
    caminhos (na faixa / vendedor avisado e manteve / sem comparáveis) — o
    degrau "regra em código" basta, e a v2 do caso 3 provou que o modelo
    erra exatamente esse critério;
  - `estado_tratado` foi dividido: a parte "o indício foi encaminhado" virou
    aresta do grafo (registrar_indicio não passa pelo avaliador), e a parte
    "o estado combina com a descrição" virou `estado_coerente`;
  - entrou `sem_invencao`, com a conversa no contexto: é o defeito do caso 4
    da Parte 1 (descrição "funciona perfeitamente" que o vendedor nunca disse).

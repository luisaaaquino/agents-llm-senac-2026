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

Indício registrado: se `indicio_registrado` vier preenchido, o vendedor
recusou declarar aquele defeito e o caso já foi para a moderação humana. Nesse
caso, o defeito FORA da descrição é o esperado e não reprova `sem_invencao`
nem `estado_coerente` — a moderação decide se o anúncio sai com aviso.

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
Entrada: `rascunho`, `conversa` e `indicio_registrado` (null ou o texto).
Como é testada: os casos 1–6 de src/casos.py e os rascunhos rotulados de
scripts/testar_prompts.py (docs/prompts.md §2.1).

## Changelog
- v3 → v4 (12/10/2026): no primeiro teste do caso 4 (avaria negada) com o
  gemini-3.5-flash-lite, o AGENTE acertou — chamou `registrar_indicio` logo
  depois da recusa —, mas o avaliador v3 não sabia do indício e oscilou por
  três rodadas: reprovou a omissão do defeito ("deve ser incluída"), depois a
  inclusão ("o vendedor preferia não colocar, retire"), depois a omissão de
  novo. O caso terminou em `orcamento` em vez de ir para a moderação. O defeito
  era de CONTRATO DE ENTRADA, não de critério: a v4 recebe
  `indicio_registrado` e diz o que a omissão significa quando ele existe.
- v2 → v3: ver avaliador-anuncio-v3.md.

# Avaliador do anúncio — v2

Avalie o rascunho do anúncio contra critérios objetivos. Para cada um, booleano:

- `tem_titulo`      : há título não-genérico (não vale "vendo isso aqui")?
- `tem_categoria`   : a categoria está preenchida?
- `tem_descricao`   : a descrição tem ao menos tamanho/marca OU estado (não
  precisa dos três — basta um deles estar presente de forma concreta)?
- `preco_na_faixa`  : o preço está dentro da faixa de mercado consultada; OU
  o vendedor foi avisado da faixa e manteve o preço por decisão própria; OU
  a consulta de preço retornou `sem_comparaveis` e a descrição registra isso
  (não há faixa contra a qual comparar — nesse caso o critério passa por
  ausência de dado, não por dado favorável)?
- `estado_tratado`  : ou o estado foi declarado, ou o indício foi encaminhado à moderação?

A aprovação (`aprovado = true`) só ocorre quando os cinco são verdadeiros.
Se algum falhar, devolva `faltando` com o(s) critério(s) e uma correção objetiva.

---
Técnica: verificador com critério booleano (separar quem escreve de quem confere).
Por quê: um único passo de LLM não garante o checklist; o avaliador impede publicar
anúncio incompleto ou desonesto.
Contrato de saída: JSON estrito conforme o schema `avaliacao`.

---
## Changelog (v1 → v2)

Rodando o caso 3 (`sem_registro`, bicicleta sem comparáveis em
`dados/seed.sql`) com `agente-anuncio-v3.md` + `qwen2.5:7b`, o avaliador v1
reprovava `preco_na_faixa` em loop (3 rodadas idênticas, até o detector de
laço encerrar) porque não existe nenhuma faixa contra a qual comparar — o
critério, como escrito, não tinha caminho pra `true` nesse caso. A v2 cobre
esse terceiro caminho explicitamente: "sem_comparaveis registrado" também
satisfaz o critério, porque a ausência de dado de mercado não é culpa do
vendedor nem do agente — é o próprio caso difícil "registro inexistente" que
`dados/casos.md` pede pra contornar, não pra travar.

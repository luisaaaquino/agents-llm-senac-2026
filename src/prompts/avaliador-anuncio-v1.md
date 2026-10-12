# Avaliador do anúncio — v1

Avalie o rascunho do anúncio contra critérios objetivos. Para cada um, booleano:

- `tem_titulo`      : há título não-genérico (não vale "vendo isso aqui")?
- `tem_categoria`   : a categoria está preenchida?
- `tem_descricao`   : a descrição tem ao menos marca/tamanho/estado?
- `preco_na_faixa`  : o preço está dentro (ou o vendedor foi avisado da) faixa de mercado?
- `estado_tratado`  : ou o estado foi declarado, ou o indício foi encaminhado à moderação?

A aprovação (`aprovado = true`) só ocorre quando os cinco são verdadeiros.
Se algum falhar, devolva `faltando` com o(s) critério(s) e uma correção objetiva.

---
Técnica: verificador com critério booleano (separar quem escreve de quem confere).
Por quê: um único passo de LLM não garante o checklist; o avaliador impede publicar
anúncio incompleto ou desonesto.
Contrato de saída: JSON estrito conforme o schema `avaliacao`.

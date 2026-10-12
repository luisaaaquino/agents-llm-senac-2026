Você faz a triagem das mensagens que chegam ao Santo Desapego, um marketplace
de usados entre vizinhos de Santo Amaro (zona sul de São Paulo).

Classifique a mensagem em UMA rota:

- `vender`       — a pessoa quer anunciar/vender um produto dela.
- `comprar`      — a pessoa procura um produto para comprar, ou quer sugestões.
- `duvida`       — a pessoa pergunta como a plataforma funciona: regras, taxa,
                   prazos, pagamento, entrega, o que pode ser anunciado, conta.
- `ambigua`      — a mensagem cabe em mais de uma rota e não dá para saber
                   qual a pessoa quer agora (ex.: quer vender uma coisa E comprar
                   outra na mesma frase, sem dizer por qual começar).
- `fora_escopo`  — nada a ver com comprar, vender ou usar a plataforma.

Regras:
- Quando for `ambigua`, preencha `leituras` com as rotas possíveis.
- `categoria` só quando a mensagem nomeia um produto da lista; senão, null.
- Não responda a pessoa. Só classifique.

---
Técnica: zero-shot com saída estruturada (`Literal` com as 5 rotas).
Por que ela: as rotas são poucas e estáveis, mas a fronteira entre `vender` e
`duvida` ("posso vender uma réplica?") é de julgamento sobre texto livre — por
isso modelo, e não regra. A descrição de `duvida` ("o que pode ser anunciado")
basta para essa fronteira — medido, ver changelog.
Contrato de saída: `Triagem` em src/esquemas.py — `rota` ∈ {vender, comprar,
duvida, ambigua, fora_escopo}; `leituras` (lista de rotas, só em ambigua);
`categoria` ∈ vocabulário de src/db.py ou null; `motivo` (uma frase).
Proibido: texto de resposta ao usuário; rota fora do Literal (o schema impede).
Como é testada: 10 mensagens rotuladas em scripts/testar_prompts.py (6 claras,
4 de fronteira), critério 6/6 nas claras e ≥ 3/4 nas de fronteira.

## Changelog
- v1 → v2 (12/10/2026): saiu a frase
  `Perguntar "posso vender X?" ou "é permitido anunciar X?" é duvida (é sobre a
  regra), não vender.` — exercício da regra da frase (docs/prompts.md §2.3).
  Com e sem ela, as 10 mensagens do teste saíram na mesma rota (6/6 claras,
  4/4 fronteira, 0 mudanças — logs/medicoes/prompts_regra_da_frase.json), com
  gemini-3.5-flash-lite. A frase não impedia nada que a descrição de `duvida`
  já não impedisse. Ela não voltou. Risco declarado: o teste tem só 2 mensagens
  do tipo "posso vender X?"; se a fronteira falhar com outro modelo, a frase é
  a primeira candidata a voltar.
- v1: ver triagem-v1.md.

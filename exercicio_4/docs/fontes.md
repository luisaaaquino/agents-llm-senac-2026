
## Contexto de mercado (números de apoio)
- Estudo citado pela commercetools (jan/2026): ~73% dos consumidores já usam IA
  na jornada de compra; 45% para ideias de produto. Morgan Stanley projeta que
  metade dos compradores online usará agentes de compra até 2030.
  Fonte: https://commercetools.com/blog/ai-trends-shaping-agentic-commerce
- McKinsey (via Opascope) projeta US$ 900 bi–1 tri em receita de varejo por
  agentic commerce nos EUA até 2030.
  Fonte: https://opascope.com/insights/ai-shopping-assistant-guide-2026-agentic-commerce-protocols/

## Caso 1 — Rep AI (product finder conversacional em Shopify)
- **Link:** https://www.hellorep.ai/blog/ai-shopping-agents-how-theyre-changing-the-way-people-shop
- **O que faz:** o comprador descreve uma necessidade ("notebook leve para
  faculdade", "hidratante para pele sensível até R$ X") em vez de digitar o nome
  exato; o agente faz perguntas de esclarecimento sobre orçamento/uso e busca no
  catálogo ao vivo para trazer as opções mais adequadas.
- **Padrão de arquitetura provável:** agente que interpreta intenção + consulta
  catálogo em runtime; a própria fonte afirma que **não é uma árvore de decisão
  fixa** — o agente avalia o contexto, pondera restrições (orçamento, uso) e
  decide a próxima ação (recomendar, atualizar carrinho, escalar para humano).
  É exatamente a distinção que separa nosso case de um recomendador comum.
- **O que a divulgação NÃO conta:** é a página de um fornecedor (Rep AI); não há
  número de ganho medido nem linha de base; não diz taxa de acerto da inferência.

## Caso 2 — Marketplace global de e-commerce (via Kore.ai)
- **Link:** https://www.kore.ai/blog/ai-agents-in-retail-12-proven-use-cases-examples
- **O que fez + número:** grande marketplace com volume massivo de interações
  implantou uma camada de agentes com "entendimento centralizado de intenção",
  relatando ~85% de acurácia em compreensão de intenção e contexto.
- **Padrão de arquitetura provável:** camada de intent understanding sobre o
  catálogo e os sistemas de suporte; agentes "assumem" jornadas completas.
- **O que a divulgação NÃO conta:** fonte é o fornecedor (Kore.ai); a empresa não
  é nomeada; "85% de acurácia" sem descrever como foi medido nem contra o quê.

## Caso 3 — Agentic commerce (ChatGPT / Amazon Rufus) — extração de restrições
- **Link:** https://invisibletech.ai/blog/agentic-commerce-2026
- **O que faz:** a partir de um pedido em linguagem natural ("tênis de corrida
  até US$ 120, tam. 10, que chegue antes de quinta, de marca com boa política de
  troca"), o modelo extrai restrições (orçamento, especificação, prazo) e as
  traduz em consultas a catálogo, preço e disponibilidade. A Amazon (Rufus)
  atende centenas de milhões de usuários; o ChatGPT processaria dezenas de
  milhões de consultas de compra por dia (nºs divulgados pelas empresas/imprensa).
- **Padrão de arquitetura provável:** camada de raciocínio (linguagem →
  intenção estruturada) → camada de ação (consulta a dados reais) → transação.
- **O que a divulgação NÃO conta:** números vêm das próprias empresas ou de
  previsões de bancos (Morgan Stanley, McKinsey); descrevem escala e potencial,
  não resultado auditado de conversão do agente.

---

## Por que estes casos e não um recomendador clássico
Filtragem colaborativa ("quem viu X viu Y") e recomendação por similaridade são
software estatístico, não agente — não inferem intenção não declarada nem decidem
uma ação em runtime. Os três casos acima foram escolhidos justamente porque
mostram o traço que define o nosso tema: interpretar o que o usuário quer sem que
ele diga e agir sobre um catálogo real e mutável.

## Outras referências consultadas
- eMarketer — "How agentic AI will reshape shopping in 2026": o agente "entende a
  necessidade, varre o mercado, pondera preço, entrega, sustentabilidade e
  histórico, e traz uma recomendação confiável".
  https://www.emarketer.com/content/how-agentic-ai-will-reshape-shopping-2026
- Paz.ai — Adobe Analytics teria medido 42% mais conversão entre compradores
  referidos por IA no Q1/2026. https://www.paz.ai/agentic-commerce
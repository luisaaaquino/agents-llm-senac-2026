# Case — Santo Desapego: consultor de compra + assistente de anúncio

## 1. O case: indústria e problema

**Setor:** Varejo digital / marketplace C2C de proximidade (economia
compartilhada). Recorte do TCC do grupo — plataforma Santo Desapego, comércio
local de produtos novos e usados em Santo Amaro, São Paulo.

**Problema (uma frase):** No Santo Desapego, dois agentes ajudam os lados que mais
erram sozinhos — um infere a intenção do comprador a partir do que ele visualiza e
monta a sugestão; o outro conversa com o vendedor para completar o anúncio e fazer
emergir o que ele não declara (como avarias).

> Por que um recorte, e não o marketplace inteiro: cadastro (RF01), busca por
> filtros (RF07), chat (RF15), pagamento via Mercado Pago (RF14) e reputação
> (RF16) são software comum — formulário, consulta, CRUD, integração de API.
> O que exige um agente são os dois componentes abaixo, cada um com decisão em
> tempo de execução sobre algo que o usuário não declarou.

### Os dois agentes (visão geral)
- **Agente A — Consultor de compra (comprador):** a partir dos itens que o usuário
  clica, infere a intenção que ele não declarou (mobiliar um cômodo? caçar uma
  peça? presente?) e monta uma sugestão com itens ativos, perto e no orçamento.
- **Agente B — Assistente de anúncio (vendedor):** conversa por texto com o
  vendedor sobre o produto e recomenda como preencher o cadastro — título,
  categoria, preço justo pelo mercado local — e, principalmente, faz perguntas que
  trazem à tona o que o vendedor tende a omitir (ex.: detectou indício de avaria →
  orienta declarar o defeito e anexar foto do problema). Foco duplo: qualidade/
  honestidade do anúncio e preço justo.

### Contexto

**O que acontece hoje, sem o sistema**
- *Lado comprador:* navega por conta própria com filtros (RF07) e busca por CEP
  (RF08); se não sabe exatamente o que quer, garimpa item a item. Cada usado é
  único e some quando vende — a janela é curta.
- *Lado vendedor:* preenche o anúncio sozinho (RF11). Vendedor amador de C2C erra
  título, categoria e preço, e — por desconhecimento ou má-fé — omite defeitos.
  Anúncio ruim gera desconfiança, pergunta repetida no chat e disputa depois da
  compra.
- 

**Regras do domínio**
- Agente A só sugere itens **ativos** (RF12); nunca vendido/pausado. Prioriza
  proximidade pelo CEP (RF08) e a faixa de preço que o comportamento indica. Não
  recomenda anúncio do próprio usuário nem itens suspensos (RF19/RF20).
- Agente B **não bloqueia** a publicação. Se detecta uma avaria que o vendedor se
  recusa a declarar, ele **registra o indício** e encaminha para a moderação
  humana (RF20) decidir — o agente aconselha e sinaliza, não veta.
- Preço: o Agente B **sugere**, o vendedor decide (a alçada de preço é dele).
- LGPD (RNF01): o Agente A usa comportamento de navegação; base legal e direito de
  exportar/excluir dados seguem a política (RF04).

**O que dá errado hoje (os casos difíceis — nossos casos de teste)**
- *Comprador — intenção ambígua:* clica em geladeira, micro-ondas e mesa. Mudança?
  Cozinha? Revenda? A sugestão certa depende da hipótese que o agente adota.
- *Comprador — estoque volátil:* o item ideal foi vendido há 5 min; o agente
  remonta a sugestão em runtime com o que resta.
- *Comprador — cold start:* dois cliques só; o agente decide se sugere ou espera.
- *Vendedor — omissão de avaria:* o vendedor escreve "geladeira ótima" mas na
  conversa aparece que "só não gela embaixo". O agente tem que fazer isso emergir.
- *Vendedor — preço fora do mercado:* pede R$ 900 num item que sai por R$ 400 no
  bairro; o agente confronta com o mercado local sem impor.
- *Vendedor — anúncio pobre:* título "vendo isso aqui", sem categoria. O agente
  extrai o essencial conversando, não de um formulário.

### O que a indústria já faz com agentes nesse problema
Ver `docs/fontes.md` para casos completos, links e leitura crítica. Resumo:

*Lado comprador (Agente A):*
- **Rep AI (Shopify):** product finder conversacional que interpreta necessidade
  ("notebook leve para faculdade"), pergunta o que falta e busca no catálogo ao
  vivo — a própria fonte frisa que **não é árvore de decisão fixa**: o agente
  pondera contexto e decide a ação.
- **Agentic commerce (ChatGPT / Amazon Rufus):** extrai restrições (orçamento,
  uso, prazo) da linguagem e traduz em consultas a catálogo/estoque real.

*Lado vendedor (Agente B):*
- **eBay "magical listing":** gera título, descrição, categoria e sugestão de
  preço para o vendedor. Número divulgado: ~30% dos vendedores ativos testaram o
  recurso e >95% dos que testaram usaram a descrição gerada (CSAT >80%). O eBay
  descreve isso como solução para o **cold start** do vendedor iniciante — a
  mesma dor do vendedor amador do Santo Desapego.
> 

## 2. Usuários e interação

| Perfil | O que ele quer | O que ele sabe | O que ele pode fazer |
|--------|---------------|----------------|----------------------|
| Comprador (principal do Agente A) | Achar o que precisa sem garimpar | Vagamente o que quer; seu orçamento e bairro | Aceitar/ignorar/refinar a sugestão; contatar vendedor; **confirmar a compra** |
| Vendedor (principal do Agente B) | Anunciar rápido e vender bem | Seu produto (às vezes esconde defeito); seu preço-desejo | Aceitar/editar as recomendações; **publicar o anúncio**; definir o preço final |
| Moderador/Admin | Que a plataforma não hospede fraude nem item enganoso | Regras e denúncias/sinalizações | Suspender anúncio/conta (RF20); **decidir sobre avaria sinalizada pelo Agente B** |

**Usuários principais:** o comprador (para o Agente A) e o vendedor (para o Agente
B). A tensão central do sistema é entre eles — ver adiante.

**A interação, concretamente**

*Agente A (comprador):*
- **Por onde:** bloco "Para você" dentro do site, que se atualiza conforme os
  cliques; o usuário pode refinar por chat ("mais barato", "mais perto").
- **Quem começa:** o sistema, ao juntar sinal suficiente.
- **Formato:** sugestão enxuta (poucos itens / um "combo") com justificativa de
  uma linha. Com pouco sinal, admite que não sabe e mostra descoberta genérica.

*Agente B (vendedor):*
- **Por onde:** um chat no fluxo de criação do anúncio (RF11), antes de publicar.
- **Quem começa:** o vendedor, ao iniciar um anúncio; o agente conduz por
  perguntas.
- **Formato:** devolve os campos preenchidos (título, categoria, descrição, preço
  sugerido) para o vendedor revisar. Quando algo indica avaria, pergunta direto e
  orienta anexar foto do problema. Se o vendedor recusa, registra e segue para
  moderação (RF20) — não bloqueia.

**Diálogo de exemplo — Agente B (vendedor)**

> Vendedor: quero vender minha geladeira, uns 400 reais
> Agente: Fechado. Qual marca e tamanho? E há quanto tempo você tem?
> Vendedor: consul duplex, uns 5 anos, funciona bem
> Agente: Ótimo. Duplex costuma sair entre R$ 300 e R$ 380 aqui em Santo Amaro
>         nesse estado — R$ 400 pode segurar a venda. Quer manter ou ajustar?
>         E uma pergunta padrão: tem algum detalhe que o comprador vai notar
>         pessoalmente? risco, borracha ressecada, algo que não gela direito?
> Vendedor: ah, o freezer embaixo demora pra congelar
> Agente: Isso é importante declarar — evita disputa depois. Sugiro colocar na
>         descrição "freezer inferior com desempenho reduzido" e uma foto do
>         freezer. Posso já escrever assim?
> Vendedor: prefiro não pôr isso
> Agente: Sem problema, não vou incluir. Só registro que conversamos sobre um
>         possível defeito — a moderação pode revisar antes de destacar o anúncio.
>         Seguimos com o resto do cadastro?

**O que o usuário não informa de primeira, e o sistema precisa descobrir:**
- *Agente A:* a **intenção de compra** por trás dos cliques e as restrições
  implícitas (orçamento, distância tolerada).
- *Agente B:* o **estado real do produto** — a avaria que o vendedor não escreve —
  e o descompasso entre o preço-desejo e o mercado local.
Em ambos, o que importa não está num campo de formulário: o agente infere/faz
emergir em tempo de execução. É isso que separa este case de um recomendador
"quem viu, viu" e de um gerador de anúncio a partir da foto.

## 3. Ganhos esperados

**Por que um agente, e não software comum (2 frases):** nos dois lados, o sistema
precisa descobrir algo não declarado e decidir a ação — inferir intenção sobre um
estoque volátil (A) e conduzir uma conversa que extrai o defeito omitido e
confronta preço com o mercado (B). Um formulário coleta o que o usuário digita;
nenhum dos dois problemas se resolve pelo que o usuário voluntariamente preenche.


**Ganho para o negócio (plataforma):** menos abandono na descoberta e mais itens
girando (A); anúncios mais completos e honestos, o que reduz disputa e devolução e
protege a reputação da plataforma (B). 

**Ganho para o usuário:** comprador para de garimpar e recebe um conjunto pronto
(A); vendedor publica mais rápido, precifica melhor e vende com menos atrito (B).

**Tensão — e é o coração do sistema:** o vendedor quer vender caro e às vezes
esconder o defeito; o comprador quer o preço justo e a verdade. O Agente B serve
ao vendedor até o ponto em que isso prejudica o comprador — na avaria, ele fica
do lado da transparência (aconselha declarar; se recusado, sinaliza à moderação).
Ou seja: o sistema otimiza a venda, mas não à custa de enganar o outro lado. Essa
escolha é o que sustenta a confiança, que é o ativo de um C2C local.

---

### Anti-padrões — checagem
- **Sem verificador?** Não. (A) o usuário contatou/favoritou/comprou o item
  sugerido, ou não. (B) o anúncio saiu com os campos completos e o estado
  declarado, ou não; e há menos disputas/devoluções nos anúncios que passaram pelo
  agente. Há sinal objetivo nos dois.
- **Dado que não temos?** Não — cliques, CEP, preço, estado do anúncio e o texto da
  conversa são gerados pela própria plataforma do TCC.
- **Grande demais?** São dois agentes, mas cada um cabe em uma frase e usa poucas
  ferramentas. Risco a vigiar: tratá-los como um só sistema gigante. Mitigação: são
  independentes; a Parte 1 pode focar em um e o outro entra depois.
- **Produto de terceiro?** O risco real deste tema, dos dois lados (existem
  recomendadores e geradores de anúncio prontos). O que é arquitetura de agente
  aqui: (A) inferência de intenção não declarada + remontagem em runtime sobre
  estoque volátil; (B) a conversa que faz emergir o defeito omitido e o confronto
  de preço com o mercado local — não a chamada de uma lib de "itens similares" nem
  um "gerar anúncio da foto".


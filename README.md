# Santo Desapego — Agentes de compra e de anúncio (Parte 2)

**Grupo:** Luisa Vitoria Aquino Nascimento, Maria Erica Joana da Conceição Cruz,
Paulo Henrique Alves Santana e Marcela Andrade

**Problema (uma frase):** No Santo Desapego, marketplace de usados entre
vizinhos de Santo Amaro, dois agentes ajudam os lados que mais erram sozinhos —
um entende o que o comprador procura e monta a sugestão com o que está à venda
perto dele; o outro conversa com o vendedor para completar o anúncio e fazer
emergir o que ele não declara (como avarias), parando para uma pessoa decidir
antes de publicar.

A Parte 2 transforma isso em **um sistema**: um grafo LangGraph com uma
triagem na entrada, os dois agentes, uma rota de dúvidas sobre as regras (RAG),
memória entre execuções e dois pontos onde o grafo para e espera uma pessoa.

## Estrutura

```
README.md · requirements.txt · .env.example · cli.py · conferir_grafo.py
docs/      case.md (complementado, §0) · modelos.md · prompts.md · arquitetura.md
           rag.md · memoria.md · grafo.md · humano.md · io.md · fontes.md
src/       o sistema: grafo.py (o grafo) · sistema.py (a porta) · contrato.py
           (entrada/saída) · estado.py · nos_*.py (os nós) · db.py · rag.py
           memoria.py · remocao.py · llm.py · config.py · casos.py
  prompts/ os prompts, versionados (com changelog em cada arquivo)
dados/     seed.sql (dados simulados) · corpus/ (as regras, com 1 revogada)
           perguntas_rag.json (o conjunto de perguntas) · casos.md
scripts/   medições: medir_rag · testar_prompts · experimento_revogado
           demo_sem_reducer · demo_memoria · verificar_remocao
logs/      os casos demonstrados (01–15) · medicoes/ (testes e experimentos)
           parte1/ (logs e comparação de modelos da Parte 1)
legado/    o que não é a Parte 2, preservado para o histórico:
           parte1/ (o agente da Parte 1) · analista-aula05/ (o lab da Aula 05)
```

Tudo o que é da Parte 1 ou de aula fica em `legado/` e `logs/parte1/`; o resto é a Parte 2.

## Como rodar (do zero, < 5 min)

Precisa de Python 3.12+ (testado em 3.14) e de uma chave **gratuita** do Google
AI Studio: https://aistudio.google.com/apikey (não pede cartão).

```bash
git clone <url-do-repo> && cd agents-llm-senac-2026
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
```

No `.env`, preencha só a chave (o resto tem padrão — ver comentários no arquivo):

```
OPENAI_API_KEY=<sua chave do AI Studio>
```

Depois:

```bash
python cli.py preparar               # banco simulado + índice do RAG (1 chamada de embedding)
python cli.py chat V-001             # conversa interativa como o usuário V-001
```

Outros comandos:

```bash
python cli.py caso 01_simples        # roda um caso demonstrado e grava logs/01_simples.json
python cli.py casos                  # os 15 casos, na ordem (~10 min, por causa do limite do plano gratuito)
python conferir_grafo.py             # nós e arestas do grafo que o sistema executa
python cli.py pendencias             # o que está esperando uma pessoa
python cli.py responder <thread> '{"acao": "aprovar"}' <quem>
python cli.py prazos +49             # a rotina de prazos, com o relógio adiantado 49 h
```

## Como usar

**O que você digita: texto livre**, como numa conversa. O sistema descobre o
que você quer:

| Você escreve… | O sistema… |
|---|---|
| "quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro" | conversa até ter um anúncio completo (pergunta de defeito, consulta o preço do bairro), confere, e **para para você aprovar** |
| "to montando a cozinha do meu ap no brooklin, queria gastar no maximo uns 700 no total" | busca no catálogo, em paralelo, o que a intenção pede e devolve itens ativos, perto e dentro do orçamento |
| "a taxa de 5% é cobrada em cima do frete tambem?" | responde com as regras do Santo Desapego, **citando o trecho** — ou recusa, se não houver regra |
| "me ajuda com a lição de matemática" | recusa, e diz o que faz |

O que acompanha o texto sem ser digitado: o **id do usuário** (da sessão do
site) e o **id da sessão** (a aba do chat). Juntos formam o `thread_id` da
conversa: `V-017:aba1`.

**O que você recebe:** sempre um objeto `SaidaSistema` validado
(`src/contrato.py`) com o **resultado** (o texto e os dados), as **fontes**
(o trecho do corpus, o registro do banco, a ferramenta, a pessoa que decidiu)
e a **suficiência** (se o sistema tinha base para responder — a recusa é
parte do contrato). Os schemas e os exemplos estão em `docs/io.md`.

### O exemplo principal

Copiado de `logs/01_simples.json` (commit `1a5cd36`, 2026-10-12 13:59:07, `gemini-3.5-flash-lite`).
A pessoa (usuário `V-017`) digita, em três momentos:

```
> quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro
< [pergunta] Para montar o anúncio certinho, a geladeira funciona bem ou tem algum amassado, ferrugem ou problema para resfriar?

> 5 anos de uso, funciona bem, sem defeito
< [aguardando_aprovacao] Confere antes de publicar? O anúncio "Geladeira Consul Duplex" por R$ 350.00 fica visível para os compradores dos 18 bairros, com retirada em Santo Amaro. Você pode pausar ou editar depois. Você pode aprovar, editar algum campo ou desistir.

  (o grafo parou: responder_pendencia("V-017:01_simples", {"acao": "aprovar"}, quem="V-017"))
< [anuncio_publicado] Pronto! "Geladeira Consul Duplex" está no ar por R$ 350.00.
```

A saída final, inteira:

```json
{
  "thread_id": "V-017:01_simples",
  "agente": "anuncio",
  "tipo": "anuncio_publicado",
  "resultado": "Pronto! \"Geladeira Consul Duplex\" está no ar por R$ 350.00.",
  "dados": {
    "anuncio": {
      "titulo": "Geladeira Consul Duplex",
      "categoria": "geladeira",
      "descricao": "Geladeira Consul Duplex com 5 anos de uso, funcionando bem.",
      "preco": 350.0,
      "bairro": "Santo Amaro",
      "estado_conservacao": "bom_estado",
      "avarias_declaradas": [],
      "estado_declarado": true
    },
    "anuncio_id": 17,
    "indicio": null,
    "desfecho": "publicado"
  },
  "fontes": [
    {
      "tipo": "banco",
      "ref": "precos_comparaveis[geladeira/Santo Amaro]",
      "trecho": "{\"categoria\": \"geladeira\", \"bairro\": \"Santo Amaro\", \"n\": 4, \"faixa_min\": 300.0, \"faixa_max\": 380.0, \"ref\": \"precos_comparaveis[geladeira/Santo Amaro]\"}"
    },
    {
      "tipo": "banco",
      "ref": "anuncios[17]",
      "trecho": null
    },
    {
      "tipo": "humano",
      "ref": "V-017",
      "trecho": "{\"acao\": \"aprovar\", \"quem\": \"V-017\"}"
    }
  ],
  "suficiencia": {
    "base_suficiente": true,
    "motivo": "publicado",
    "faltando": []
  },
  "escolha_declarada": null,
  "termino": "respondeu",
  "motivo_termino": "publicado"
}
```

Por baixo, a trajetória do log: triagem (modelo) → pergunta de avaria
(modelo) → consulta de preço no banco (R$ 300–380) → rascunho (modelo) →
portão de avaria (código) → avaliador (modelo + código) → **pausa** →
publicação (código, idempotente) → memória. 5 decisões do modelo
(`passos`; mais 1 chamada de extração para a memória, fora do contador),
4281 tokens nas decisões, 24,4 s. Os outros exemplos — a recusa, a entrada
incompleta, a ambígua, a fora do escopo, o Agente A — estão em `docs/io.md`.

### Quando o grafo para e espera alguém

Duas situações, e nelas a saída vem com `termino = "aguardando_humano"` e a
pendência inteira em `dados.pendencia` (a ação exata, os argumentos, a
consequência, as opções e o prazo):

1. **Antes de publicar qualquer anúncio** — quem decide é **o vendedor**:
   `aprovar`, `editar` (corrigir título, descrição, preço ou estado antes de ir
   ao ar) ou `rejeitar`. Prazo de 24 h; se ninguém responder, **não publica**.
2. **Quando o vendedor se recusa a declarar um defeito** que apareceu na
   conversa — o anúncio fica fora das buscas e quem decide é **um moderador**:
   `publicar`, `publicar_com_aviso` (com o texto do aviso) ou `rejeitar`.
   Prazo de 48 h; se ninguém responder, **não publica**.

A conversa continua de onde parou, mesmo em outro processo (o estado fica em
`dados/checkpoints.db`). A mesma aprovação enviada duas vezes **não** publica
duas vezes. Detalhes em `docs/humano.md`.

## O que o sistema NÃO faz

- Não decide preço: avisa a faixa do bairro, e a alçada é do vendedor.
- Não publica sem uma pessoa aprovar, e não publica escondendo um defeito sem a
  moderação decidir.
- Não lembra nada do comprador entre conversas (decisão de privacidade,
  `docs/memoria.md` §1.5).
- Não responde regra que não está no corpus — recusa e indica a Central de Ajuda.
- Não move dinheiro: o pagamento é do site, pelo Mercado Pago.

## Limitações conhecidas

- **Modelo no plano gratuito do Gemini**: o Google pode usar o conteúdo enviado
  para melhorar os produtos dele. Os dados desta entrega são todos simulados;
  com usuários reais seria o plano pago ou um modelo local (`docs/modelos.md` §4).
- **O modelo não é determinístico** mesmo em `temperature=0`: o caso 2 passou
  numa rodada, entrou em laço em outras duas, e registrou um indício falso em
  2 de 3 repetições — cada falha virou uma correção em código (`docs/grafo.md`
  §6.3, `docs/memoria.md` P2.2). Depois delas: 3 de 3 (`logs/medicoes/estabilidade/`).
- **Checkpoint em SQLite local**: um servidor só.
- **O portão de avaria é um regex**: já errou uma vez (falso positivo), e frase
  ambígua sobre defeito é onde ele pode errar de novo (`docs/grafo.md` §6.3).

## Estado da entrega

O mapa item a item do enunciado está no fim de `docs/io.md`.

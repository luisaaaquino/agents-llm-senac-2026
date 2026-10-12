# Entrada e saída — o contrato do sistema (§1)

Código: `src/contrato.py` (Pydantic). A porta é `src/sistema.py`:
`conversar(Entrada) -> SaidaSistema` e `responder_pendencia(thread_id, resposta, quem) -> SaidaSistema`.

## 1.1 A entrada é texto

```python
class Entrada(BaseModel):
    texto: str        # o que a pessoa digitou, literal — a ÚNICA coisa digitada
    usuario_id: str   # id do usuário logado (ex.: V-017) — vem da sessão do site
    sessao_id: str    # id da conversa aberta (uma aba de chat) — vem do site

    @property
    def thread_id(self) -> str:      # "V-017:aba1" — o endereço do checkpoint
        return f"{self.usuario_id}:{self.sessao_id}"
```

O que **acompanha** o texto sem ser digitado: `usuario_id` e `sessao_id`. É
deles que sai o `thread_id` (`docs/memoria.md` P2.5). Nada mais entra: não há
formulário, não há categoria escolhida num menu, não há JSON montado por outro
programa — o sistema **descobre** se a pessoa quer vender, comprar ou tirar
dúvida (`triagem`), e o que falta (`perguntar_*`).

| Forma | Onde ela entra neste sistema |
|---|---|
| texto livre | **a entrada** (`Entrada.texto`) |
| cliques do comprador | conteúdo buscado **por ferramenta** (`db.historico_cliques`), só quando o texto não diz o que procurar |
| regras da plataforma (documentos) | **corpus** do RAG (`dados/corpus/`) |
| a decisão de uma pessoa num ponto de parada | **retomada** (`responder_pendencia`), não entrada nova — é a resposta a uma pergunta que o sistema fez, com opções fechadas (aprovar / editar / rejeitar…) |

## 1.2 O contrato de saída

```python
class SaidaSistema(BaseModel):
    thread_id: str
    agente: Literal["anuncio", "compra", "duvida", "nenhum"]
    tipo: Literal["pergunta", "aguardando_aprovacao", "aguardando_moderacao",
                  "anuncio_publicado", "anuncio_nao_publicado", "sugestao",
                  "resposta", "recusa", "erro"]
    resultado: str                    # O RESULTADO — o que a pessoa lê
    dados: dict | None                #   …e o objeto: o anúncio, os itens, a pendência
    fontes: list[Fonte]               # A FONTE — o que sustenta o resultado, conferível
    suficiencia: Suficiencia          # A SUFICIÊNCIA — teve base? se não, o que faltou
    escolha_declarada: str | None     # entrada ambígua: a leitura que o sistema escolheu
    termino: Literal[...]             # a taxonomia de docs/arquitetura.md §3.2
    motivo_termino: str

class Fonte(BaseModel):
    tipo: Literal["corpus", "banco", "ferramenta", "memoria", "conversa", "humano"]
    ref: str                          # id conferível: "termos-de-uso-2026#5", "anuncios[17]"…
    trecho: str | None                # o conteúdo que sustenta

class Suficiencia(BaseModel):
    base_suficiente: bool             # False = a recusa, como parte do contrato
    motivo: str
    faltando: list[str]
```

Os três campos obrigatórios do §1.2: **resultado** → `resultado` + `dados`;
**fonte** → `fontes`; **suficiência** → `suficiencia`. A saída é validada pelo
Pydantic **no nó que a monta** (`saida()` em `src/nos_comuns.py`): um nó que
tente devolver um `tipo` ou um `termino` fora do `Literal` quebra ali, não no
consumidor.

**As fontes não são guardadas, são derivadas** na hora de montar a saída
(`docs/grafo.md` §7.3): a faixa de preço que veio do banco, os trechos do
corpus que a resposta **citou** (e o código conferiu), o registro do anúncio
gravado, a decisão da pessoa que aprovou.

## 1.3 Os exemplos, copiados de uma execução

Cada exemplo é a saída **inteira** (`SaidaSistema.model_dump()`), copiada por script do log da execução que a produziu — o commit, a data e o arquivo vêm no cabeçalho, e a trajetória completa (cada nó, cada chamada, cada ferramenta) está no log. Todos rodaram com o commit `1a5cd36`, sem alteração não commitada (`carimbo.codigo_com_alteracao_nao_commitada = false`).

> **Nota sobre os códigos de commit nos logs.** Depois das execuções e antes do
> primeiro push, as mensagens dos 5 commits da Parte 2 foram reescritas (só o
> texto da mensagem). Isso muda o hash do commit, e o campo `carimbo.commit` de
> cada log foi atualizado uma vez, do hash antigo para o novo. O **código é o
> mesmo**: cada par tem a mesma árvore git (`git log --format="%h %T"`) —
> `04499f4` → `1a5cd36` (árvore `7e1f946…`), `c0a818f` → `3848cc4` (`1860982…`),
> `eeff562` → `4db78ab` (`ade237c…`), `e4758c2` → `12cac9e` (`08d3256…`),
> `18d8bfe` → `e0d5764` (`60a6142…`). Nada mais nos logs foi editado.

### Exemplo 1 — o caminho feliz (Agente B, caso 1)

`logs/01_simples.json` · commit `1a5cd36` · 2026-10-12 13:59:07 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro
```

**Saída completa:**

```json
{
  "thread_id": "V-017:01_simples",
  "agente": "anuncio",
  "tipo": "pergunta",
  "resultado": "Para montar o anúncio certinho, a geladeira funciona bem ou tem algum amassado, ferrugem ou problema para resfriar?",
  "dados": {
    "rascunho": null
  },
  "fontes": [],
  "suficiencia": {
    "base_suficiente": false,
    "motivo": "falta informação essencial para o anúncio",
    "faltando": []
  },
  "escolha_declarada": null,
  "termino": "aguardando_usuario",
  "motivo_termino": "falta informação essencial para o anúncio"
}
```

**Entrada** (o texto exato):

```
5 anos de uso, funciona bem, sem defeito
```

**Saída completa:**

```json
{
  "thread_id": "V-017:01_simples",
  "agente": "anuncio",
  "tipo": "aguardando_aprovacao",
  "resultado": "Confere antes de publicar? O anúncio \"Geladeira Consul Duplex\" por R$ 350.00 fica visível para os compradores dos 18 bairros, com retirada em Santo Amaro. Você pode pausar ou editar depois. Você pode aprovar, editar algum campo ou desistir.",
  "dados": {
    "pendencia": {
      "tipo": "aprovacao_vendedor",
      "perfil": "vendedor",
      "responsavel": "V-017",
      "acao": "publicar_anuncio",
      "argumentos": {
        "titulo": "Geladeira Consul Duplex",
        "categoria": "geladeira",
        "descricao": "Geladeira Consul Duplex com 5 anos de uso, funcionando bem.",
        "preco": 350.0,
        "bairro": "Santo Amaro",
        "estado_conservacao": "bom_estado",
        "avarias_declaradas": []
      },
      "consequencia": "O anúncio \"Geladeira Consul Duplex\" por R$ 350.00 fica visível para os compradores dos 18 bairros, com retirada em Santo Amaro. Você pode pausar ou editar depois.",
      "opcoes": {
        "aprovar": {},
        "editar": {
          "campos": [
            "descricao",
            "estado_conservacao",
            "preco",
            "titulo"
          ]
        },
        "rejeitar": {
          "motivo": "texto livre"
        }
      },
      "expira_em": "2026-10-13T13:59:24",
      "se_ninguem_responder": "o anúncio NÃO é publicado; o rascunho fica salvo nesta conversa"
    }
  },
  "fontes": [
    {
      "tipo": "ferramenta",
      "ref": "publicar_anuncio",
      "trecho": null
    }
  ],
  "suficiencia": {
    "base_suficiente": true,
    "motivo": "o sistema tem o que precisa; a decisão é de uma pessoa",
    "faltando": [
      "decisão do vendedor"
    ]
  },
  "escolha_declarada": null,
  "termino": "aguardando_humano",
  "motivo_termino": "interrupt: aprovacao_vendedor"
}
```

**Resposta da pessoa ao ponto de parada** (`responder_pendencia`):

```json
{
  "quem": "V-017",
  "acao": "aprovar"
}
```

**Saída completa:**

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

**O que ler aqui:** a primeira saída é uma `pergunta` sobre defeito, com `suficiencia.base_suficiente = false` — o sistema **não** monta o anúncio só com a primeira fala, mesmo ela tendo produto, preço e bairro. A segunda saída é a **pausa** (`aguardando_humano`): o rascunho exato e a consequência estão em `dados.pendencia`, e as fontes trazem a faixa do banco que sustentou o preço. A terceira só existe porque o vendedor aprovou — e cita a aprovação como fonte (`tipo: humano`).

### Exemplo 2 — a recusa (dúvida fora do corpus, caso 5)

`logs/05_fora_do_corpus.json` · commit `1a5cd36` · 2026-10-12 14:01:15 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
posso vender ingresso de show pelo site?
```

**Saída completa:**

```json
{
  "thread_id": "C-002:05_fora_do_corpus",
  "agente": "duvida",
  "tipo": "recusa",
  "resultado": "Não encontrei nenhuma regra do Santo Desapego sobre isso, então prefiro não chutar. O mais perto que eu tenho é sobre: Como o comprador paga; Quando o vendedor recebe o dinheiro. Para esse caso, a equipe responde pela Central de Ajuda.",
  "dados": null,
  "fontes": [],
  "suficiencia": {
    "base_suficiente": false,
    "motivo": "melhor similaridade 0.617 abaixo do limiar 0.67",
    "faltando": [
      "regra sobre este assunto no corpus"
    ]
  },
  "escolha_declarada": null,
  "termino": "recusou",
  "motivo_termino": "melhor similaridade 0.617 abaixo do limiar 0.67"
}
```

**O que ler aqui:** `tipo: recusa` com `base_suficiente: false`, e o motivo é um número: a melhor similaridade (0,617) ficou abaixo do limiar (0,67), então o modelo de resposta **nem foi chamado** (`passos: 1`, só a triagem). No lugar da resposta, o sistema diz que não há regra e indica onde perguntar.

## 1.4 A entrada que não dá para atender

### Entrada incompleta — pergunta o que falta (caso 8)

`logs/08_incompleta.json` · commit `1a5cd36` · 2026-10-12 14:02:12 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
oi, quero comprar umas coisas
```

**Saída completa:**

```json
{
  "thread_id": "C-003:08_incompleta",
  "agente": "compra",
  "tipo": "pergunta",
  "resultado": "Me conta o que você está procurando — um produto específico (ex.: uma geladeira) ou o que quer resolver (ex.: montar a cozinha)? Se puder, diga também o bairro e quanto quer gastar.",
  "dados": null,
  "fontes": [],
  "suficiencia": {
    "base_suficiente": false,
    "motivo": "não dá para saber o que a pessoa procura",
    "faltando": [
      "o que procura"
    ]
  },
  "escolha_declarada": null,
  "termino": "aguardando_usuario",
  "motivo_termino": "não dá para saber o que a pessoa procura"
}
```

**Entrada** (o texto exato):

```
uma mesa pra cozinha, até 150, moro no jardim cordeiro
```

**Saída completa:**

```json
{
  "thread_id": "C-003:08_incompleta",
  "agente": "compra",
  "tipo": "sugestao",
  "resultado": "Selecionamos a mesa dobrável pois está exatamente no seu bairro, com ótimo preço e pronta para a cozinha.\n- Mesa dobrável para cozinha — R$ 90, Jardim Cordeiro (0.0 km)",
  "dados": {
    "pedido": {
      "intencao": "comprar uma mesa para a cozinha",
      "categorias": [
        "mesa"
      ],
      "orcamento_total": null,
      "preco_max_item": 150.0,
      "bairro": "Jardim Cordeiro",
      "faltando": [],
      "ambiguidade": null,
      "escolha": null
    },
    "itens": [
      {
        "id": 9,
        "titulo": "Mesa dobrável para cozinha",
        "categoria": "mesa",
        "preco": 90.0,
        "bairro": "Jardim Cordeiro",
        "estado_conservacao": "bom_estado",
        "dist_km": 0.0
      }
    ],
    "correcoes": [],
    "soma": 90.0
  },
  "fontes": [
    {
      "tipo": "banco",
      "ref": "anuncios[9]",
      "trecho": "Mesa dobrável para cozinha · R$ 90 · Jardim Cordeiro · status ativo"
    }
  ],
  "suficiencia": {
    "base_suficiente": true,
    "motivo": "itens ativos encontrados no catálogo",
    "faltando": []
  },
  "escolha_declarada": null,
  "termino": "respondeu",
  "motivo_termino": "itens ativos encontrados no catálogo"
}
```

**O que ler aqui:** a primeira saída é uma `pergunta`, com `faltando: ["o que procura"]`; o sistema não chuta uma categoria. Com a resposta, a segunda saída é a sugestão — e `fontes` são os registros dos anúncios ativos (`anuncios[9]`…), conferíveis no banco.

### Entrada ambígua — desambigua perguntando (caso 9)

`logs/09_ambigua.json` · commit `1a5cd36` · 2026-10-12 14:02:28 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
quero vender minha geladeira velha e comprar uma maior
```

**Saída completa:**

```json
{
  "thread_id": "V-023:09_ambigua",
  "agente": "nenhum",
  "tipo": "pergunta",
  "resultado": "Entendi que você quer fazer mais de uma coisa. Para eu ajudar direito, vamos por partes: você prefere começar por anunciar o seu produto ou por procurar algo para comprar?",
  "dados": {
    "leituras": [
      "vender",
      "comprar"
    ]
  },
  "fontes": [],
  "suficiencia": {
    "base_suficiente": false,
    "motivo": "a mensagem tem mais de uma leitura; o sistema pergunta em vez de escolher",
    "faltando": [
      "qual das ações fazer primeiro"
    ]
  },
  "escolha_declarada": null,
  "termino": "aguardando_usuario",
  "motivo_termino": "a mensagem tem mais de uma leitura; o sistema pergunta em vez de escolher"
}
```

**O que ler aqui:** a triagem devolveu `ambigua` com as duas leituras (`dados.leituras: ["vender", "comprar"]`), e o sistema **pergunta por onde começar** em vez de escolher. O outro tratamento do §1.4 — escolher e declarar — aparece no Agente A: quando o comprador não diz o bairro, `escolha_declarada` registra "ordenei por preço, sem distância".

### Fora do escopo — recusa e diz o que faz (caso 10)

`logs/10_fora_escopo.json` · commit `1a5cd36` · 2026-10-12 14:02:32 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
me ajuda a fazer a lição de matemática do meu filho?
```

**Saída completa:**

```json
{
  "thread_id": "C-004:10_fora_escopo",
  "agente": "nenhum",
  "tipo": "recusa",
  "resultado": "Isso foge do que eu faço aqui. Eu sou o assistente do Santo Desapego e posso: montar o anúncio de um produto seu, encontrar itens à venda perto de você, ou tirar dúvidas sobre as regras da plataforma (taxa, prazos, pagamento, entrega).",
  "dados": null,
  "fontes": [],
  "suficiencia": {
    "base_suficiente": false,
    "motivo": "pedido fora do escopo do sistema",
    "faltando": [
      "um pedido de compra, venda ou dúvida sobre a plataforma"
    ]
  },
  "escolha_declarada": null,
  "termino": "recusou",
  "motivo_termino": "pedido fora do escopo do sistema"
}
```

**O que ler aqui:** `recusa` com `faltando` dizendo o que o sistema atende; e o texto lista as três coisas que ele faz.

## Outros exemplos reais (de outras rotas)

### O Agente A — sugestão com orçamento conferido (caso 7)

`logs/07_compra_cozinha.json` · commit `1a5cd36` · 2026-10-12 14:01:59 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
to montando a cozinha do meu ap no brooklin, queria gastar no maximo uns 700 no total
```

**Saída completa:**

```json
{
  "thread_id": "C-001:07_compra_cozinha",
  "agente": "compra",
  "tipo": "sugestao",
  "resultado": "Separei 3 itens ativos perto de você, somando R$ 650 (dentro dos R$ 700). Ficou de fora: mesa, porque não coube no orçamento.\n- Geladeira Brastemp Frost Free 375L — R$ 340, Brooklin (0.0 km)\n- Fogão 4 bocas Dako — R$ 180, Jardim Petrópolis (0.7 km)\n- Micro-ondas Panasonic 21L — R$ 130, Brooklin (0.0 km)",
  "dados": {
    "pedido": {
      "intencao": "mobiliar a cozinha",
      "categorias": [
        "geladeira",
        "fogão",
        "micro-ondas",
        "mesa"
      ],
      "orcamento_total": 700.0,
      "preco_max_item": null,
      "bairro": "Brooklin",
      "faltando": [],
      "ambiguidade": null,
      "escolha": null
    },
    "itens": [
      {
        "id": 1,
        "titulo": "Geladeira Brastemp Frost Free 375L",
        "categoria": "geladeira",
        "preco": 340.0,
        "bairro": "Brooklin",
        "estado_conservacao": "bom_estado",
        "dist_km": 0.0
      },
      {
        "id": 6,
        "titulo": "Fogão 4 bocas Dako",
        "categoria": "fogão",
        "preco": 180.0,
        "bairro": "Jardim Petrópolis",
        "estado_conservacao": "marcas_de_uso",
        "dist_km": 0.7
      },
      {
        "id": 4,
        "titulo": "Micro-ondas Panasonic 21L",
        "categoria": "micro-ondas",
        "preco": 130.0,
        "bairro": "Brooklin",
        "estado_conservacao": "bom_estado",
        "dist_km": 0.0
      }
    ],
    "correcoes": [
      "soma acima de R$ 700 — removida a categoria de menor prioridade: mesa (id 8)"
    ],
    "soma": 650.0
  },
  "fontes": [
    {
      "tipo": "banco",
      "ref": "anuncios[1]",
      "trecho": "Geladeira Brastemp Frost Free 375L · R$ 340 · Brooklin · status ativo"
    },
    {
      "tipo": "banco",
      "ref": "anuncios[6]",
      "trecho": "Fogão 4 bocas Dako · R$ 180 · Jardim Petrópolis · status ativo"
    },
    {
      "tipo": "banco",
      "ref": "anuncios[4]",
      "trecho": "Micro-ondas Panasonic 21L · R$ 130 · Brooklin · status ativo"
    }
  ],
  "suficiencia": {
    "base_suficiente": true,
    "motivo": "itens ativos encontrados no catálogo",
    "faltando": [
      "fora do orçamento: mesa"
    ]
  },
  "escolha_declarada": null,
  "termino": "respondeu",
  "motivo_termino": "itens ativos encontrados no catálogo"
}
```

**O que ler aqui:** as quatro categorias que "montar a cozinha" pede foram buscadas em paralelo; o modelo escolheu um conjunto que passava de R$ 700, e a conferência em código (`dados.correcoes`) tirou a categoria de menor prioridade. A justificativa que aparece é a do código, porque a do modelo descrevia uma seleção que deixou de existir. `faltando` declara o que ficou de fora e por quê.

### Dúvida cuja resposta depende de uma exceção, com citação (caso 11)

`logs/11_duvida_excecao.json` · commit `1a5cd36` · 2026-10-12 14:02:36 · `gemini-3.5-flash-lite`

**Entrada** (o texto exato):

```
a taxa de 5% é cobrada em cima do frete tambem?
```

**Saída completa:**

```json
{
  "thread_id": "C-005:11_duvida_excecao",
  "agente": "duvida",
  "tipo": "resposta",
  "resultado": "Não, a taxa de 5% incide apenas sobre o valor nominal do produto. Custos de frete ou entrega combinados fora da plataforma não entram na base de cálculo.",
  "dados": null,
  "fontes": [
    {
      "tipo": "corpus",
      "ref": "termos-de-uso-2026#5",
      "trecho": "Os pagamentos são processados pelo Mercado Pago. A plataforma não armazena dados de cartão. A taxa de intermediação é de 5% (cinco por cento) sobre o valor do produto e é descontada automaticamente quando a venda é liquidada: o vendedor recebe 95% e vê o valor líquido antes de confirmar a venda. Anunciar é gratuito. Exceção: a taxa incide só sobre o valor nominal do produto — custos de frete ou entrega combinados fora da plataforma não entram na base de cálculo."
    }
  ],
  "suficiencia": {
    "base_suficiente": true,
    "motivo": "resposta sustentada pelos trechos citados",
    "faltando": []
  },
  "escolha_declarada": null,
  "termino": "respondeu",
  "motivo_termino": "resposta sustentada pelos trechos citados"
}
```

**O que ler aqui:** a resposta traz a **exceção** (o frete não entra na base da taxa) e `fontes` traz o trecho exato que a sustenta — o id citado foi conferido em código contra os trechos recuperados.

## Os casos demonstrados (§9) — resultado real

| # | Caso | Esperado (escrito antes) | Resultado | Término | Chamadas de modelo | Tokens | US$ (tabela paga) | s |
|---|---|---|---|---|---|---|---|---|
| 01 | `01_simples` | anuncio_publicado / respondeu | `anuncio_publicado` | `respondeu` | 5 | 4281 | 0.0026 | 24.4 |
| 02 | `02_divergencia_preco` | anuncio_publicado a R$ 900 / respondeu, sem indício | `anuncio_publicado` | `respondeu` | 8 | 8156 | 0.0045 | 44.0 |
| 03 | `03_sem_registro` | anuncio_publicado / respondeu, uma única consulta de preço | `anuncio_publicado` | `respondeu` | 5 | 4187 | 0.0025 | 27.6 |
| 04 | `04_avaria_negada` | aguardando_moderacao (não publicado) -> decisão do moderador | `anuncio_publicado` | `respondeu` | 5 | 4674 | 0.0026 | 31.9 |
| 05 | `05_fora_do_corpus` | recusa / recusou | `recusa` | `recusou` | 1 | 319 | 0.0002 | 7.9 |
| 06 | `06_aprovacao_editando` | anuncio_publicado a R$ 280 / respondeu; 2ª aprovação sem efeito | `anuncio_publicado` | `respondeu` | 5 | 4324 | 0.0026 | 35.9 |
| 07 | `07_compra_cozinha` | sugestao / respondeu, soma <= 700, nenhum item do próprio C-001 | `sugestao` | `respondeu` | 3 | 1899 | 0.0011 | 12.6 |
| 08 | `08_incompleta` | pergunta -> sugestao | `sugestao` | `respondeu` | 4 | 1560 | 0.0011 | 16.1 |
| 09 | `09_ambigua` | pergunta / aguardando_usuario | `pergunta` | `aguardando_usuario` | 1 | 337 | 0.0003 | 3.8 |
| 10 | `10_fora_escopo` | recusa / recusou | `recusa` | `recusou` | 1 | 381 | 0.0004 | 3.9 |
| 11 | `11_duvida_excecao` | resposta / respondeu, citando termos-de-uso-2026#5 | `resposta` | `respondeu` | 2 | 976 | 0.0006 | 12.6 |
| 12 | `12_moderacao_sem_resposta` | aguardando_moderacao -> expirou | `anuncio_nao_publicado` | `expirou` | 5 | 4285 | 0.0025 | 26.5 |
| 13 | `13_memoria_avaria_tipica` | anuncio_publicado; pergunta cita o freezer | `anuncio_publicado` | `respondeu` | 5 | 4773 | 0.0027 | 31.9 |
| 14 | `14_item_proibido` | recusa / recusou, citando politica-moderacao-2026#1 | `recusa` | `recusou` | 5 | 4986 | 0.0027 | 33.3 |
| 15 | `15_excecao_brinquedo` | anuncio_publicado / respondeu, depois de consultar politica-moderacao-2026#2 | `anuncio_publicado` | `respondeu` | 5 | 4632 | 0.0026 | 30.2 |

Todos com o commit `1a5cd36`. Os logs das execuções que **falharam** antes das correções estão preservados em `logs/medicoes/` (caso 2 em laço com as v8 e v9 do prompt; as 3 repetições do caso 2 antes da correção do indício falso).

## Limitações do contrato, conhecidas e não corrigidas

- **As fontes do Agente B listam todas as regras consultadas, não só a citada.**
  No caso 14, a recusa cita `politica-moderacao-2026#1` (conferido em código —
  `motivo_termino` diz qual), mas `fontes` traz os três trechos consultados,
  inclusive a exceção do brinquedo (`#2`). A fonte que sustenta o resultado está
  lá; as outras são ruído. Correção prevista: em `finalizar_b`, usar só
  `decisao_b.regra_citada` quando o desfecho for `item_proibido`.
- **`suficiencia.faltando` vem vazio na pergunta do Agente B** (exemplo 1): o
  motivo diz que falta informação, mas não diz qual. O que falta está
  implícito na pergunta; o campo deveria trazer ("resposta sobre defeito").

## Onde está cada item do enunciado

| Item | Onde |
|---|---|
| 0. complemento do case | `docs/case.md` §0 |
| 1. entrada e saída | este documento; `src/contrato.py`; exemplo principal também no `README.md` |
| 2. plano de prompt engineering | `docs/prompts.md`; prompts em `src/prompts/`; regra da frase em `docs/prompts.md` §2.3 |
| 3. arquitetura | `docs/arquitetura.md` (diagrama, seis perguntas, autonomia) |
| 4. RAG | `docs/rag.md`; `src/rag.py`; `dados/corpus/`; `dados/perguntas_rag.json` |
| 5. memória e conversa | `docs/memoria.md` (Decisões 1–2 e "Parte 2"); `src/memoria.py`, `src/remocao.py` |
| 6. o grafo | `docs/arquitetura.md` §6.1/§6.4 (desenho e conferência); `docs/grafo.md` (padrões, decisões, o que o framework não deu, parâmetro); `src/grafo.py`; `conferir_grafo.py` |
| 7. o estado | `docs/arquitetura.md` §7.1; `docs/grafo.md` §7.2–7.4; `src/estado.py`; `scripts/demo_sem_reducer.py` |
| 8. human-in-the-loop | `docs/humano.md`; `src/nos_anuncio.py`, `src/sistema.py` |
| 9. os casos demonstrados | `logs/01…06` (os seis do §9) e `logs/07…15`; a tabela acima; `dados/casos.md` |
| 10. o projeto como entrega | `README.md`, `requirements.txt`, `.env.example`, `docs/` |
| análise de modelos | `docs/modelos.md` (§3 da Parte 1 e §4, a troca para o Gemini) |
| fontes | `docs/fontes.md` |

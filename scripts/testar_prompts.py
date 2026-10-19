"""
Testa cada etapa em que o modelo é chamado, e faz o teste de remover
uma frase do prompt da triagem.

    python scripts/testar_prompts.py            # todas as etapas
    python scripts/testar_prompts.py triagem    # uma etapa
    python scripts/testar_prompts.py frase      # triagem sem uma frase do prompt

Grava logs/medicoes/prompts_<etapa>.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, llm, rag  # noqa: E402
from src.esquemas import Avaliacao, PedidoCompra, RespostaRegras, Sugestao, Triagem  # noqa: E402
from src.nos_compra import conferir_sugestao  # noqa: E402

TRIAGEM = [  # (mensagem, rota esperada, é fronteira?)
    ("quero vender meu sofá, 400 reais", "vender", False),
    ("vendo bicicleta aro 29 em interlagos", "vender", False),
    ("procuro uma geladeira barata no brooklin", "comprar", False),
    ("me indica umas coisas pra montar meu quarto", "comprar", False),
    ("qual a previsão do tempo pra amanhã?", "fora_escopo", False),
    ("me ajuda com a lição de matemática do meu filho", "fora_escopo", False),
    ("posso vender uma réplica de pistola de airsoft?", "duvida", True),
    ("é permitido anunciar remédio?", "duvida", True),
    ("quanto tempo meu anúncio fica no ar?", "duvida", True),
    ("quero vender minha geladeira velha e comprar uma maior", "ambigua", True),
]

_C = ["vendedor: quero vender minha geladeira consul, 350 reais, Santo Amaro",
      "agente: tem algum defeito?", "vendedor: 5 anos de uso, funciona bem, sem defeito"]
_R = {"titulo": "Geladeira Consul Duplex", "categoria": "geladeira",
      "descricao": "Geladeira Consul duplex com 5 anos de uso, funcionando bem.", "preco": 350.0,
      "bairro": "Santo Amaro", "estado_conservacao": "bom_estado", "avarias_declaradas": []}
_FREEZER = ["vendedor: vendo geladeira consul, 380 reais, Santo Amaro", "agente: tem algum defeito?",
            "vendedor: o freezer embaixo demora pra congelar, mas prefiro não pôr isso"]
AVALIADOR = [  # (rascunho, conversa, indício, aprovado esperado, o que testa)
    (_R, _C, None, True, "bom: simples"),
    ({**_R, "titulo": "Sofá 3 lugares veludo verde", "categoria": "sofá", "preco": 300.0,
      "descricao": "Sofá 3 lugares de veludo verde. Um dos pés tem uma rachadura pequena.",
      "estado_conservacao": "marcas_de_uso", "avarias_declaradas": ["rachadura pequena em um pé"]},
     ["vendedor: vendo sofá 3 lugares veludo verde, 300, Santo Amaro", "agente: tem defeito?",
      "vendedor: tem um pé com uma rachadura pequena, pode colocar"], None, True, "bom: avaria declarada"),
    ({**_R, "titulo": "Bicicleta aro 29", "categoria": "bicicleta", "preco": 500.0,
      "descricao": "Bicicleta aro 29 seminova, sem defeitos. Sem preço de referência no bairro."},
     ["vendedor: bicicleta aro 29, 500 reais, Santo Amaro", "agente: tem defeito?",
      "vendedor: seminova, sem defeito nenhum"], None, True, "bom: sem comparáveis"),
    ({**_R, "titulo": "Geladeira Consul", "preco": 380.0, "descricao": "Geladeira Consul usada."},
     _FREEZER, "freezer inferior demora para congelar", True, "bom: indício registrado, defeito fora"),
    ({**_R, "titulo": "vendo isso aqui"}, _C, None, False, "ruim: título genérico"),
    ({**_R, "descricao": "Produto."}, _C, None, False, "ruim: descrição vazia"),
    ({**_R, "titulo": "Sofá 3 lugares", "categoria": "sofá", "estado_conservacao": "como_novo",
      "descricao": "Sofá 3 lugares com um pé rachado.", "avarias_declaradas": ["pé rachado"]},
     ["vendedor: sofá 3 lugares, 350", "vendedor: tem um pé rachado, pode colocar"], None, False,
     "ruim: avaria declarada com estado como_novo"),
    ({**_R, "titulo": "Geladeira Consul", "preco": 380.0,
      "descricao": "Geladeira Consul funcionando perfeitamente, sem nenhum defeito."},
     _FREEZER, None, False, "ruim: inventa 'sem defeito' contra a conversa"),
]

PERMITIDAS_COZINHA = {"geladeira", "fogão", "micro-ondas", "mesa", "cadeira", "armário"}
INTERPRETAR = [  # (texto, categorias obrigatórias, categorias permitidas, orçamento, bairro)
    ("procuro uma cadeira", {"cadeira"}, {"cadeira"}, None, None),
    ("to montando a cozinha do meu ap no brooklin, queria gastar no maximo uns 700 no total",
     {"geladeira", "fogão"}, PERMITIDAS_COZINHA, 700.0, "Brooklin"),
    ("quero uma bike pra ir trabalhar, até 800", {"bicicleta"}, {"bicicleta"}, 800.0, None),
    ("preciso de uma cama de casal, moro em socorro", {"cama"}, {"cama"}, None, "Socorro"),
    ("oi", set(), set(), None, None),
    ("algo pra sala, um sofá, uns 500", {"sofá"}, {"sofá", "mesa"}, 500.0, None),
    ("quero mobiliar o quarto do bebê", set(), {"cama", "armário", "outro"}, None, None),
    ("geladeira duplex até 400 no campo belo", {"geladeira"}, {"geladeira"}, 400.0, "Campo Belo"),
]

_CAND = [{"id": 1, "titulo": "Geladeira", "categoria": "geladeira", "preco": 340.0, "bairro": "Brooklin", "dist_km": 0.0},
         {"id": 2, "titulo": "Geladeira pequena", "categoria": "geladeira", "preco": 220.0, "bairro": "Campo Belo", "dist_km": 1.0},
         {"id": 6, "titulo": "Fogão", "categoria": "fogão", "preco": 180.0, "bairro": "Jardim Petrópolis", "dist_km": 0.7},
         {"id": 4, "titulo": "Micro-ondas", "categoria": "micro-ondas", "preco": 130.0, "bairro": "Brooklin", "dist_km": 0.0},
         {"id": 8, "titulo": "Mesa", "categoria": "mesa", "preco": 180.0, "bairro": "Brooklin", "dist_km": 0.0}]
SUGESTAO = [  # (pedido, candidatos)
    ({"intencao": "montar a cozinha", "categorias": ["geladeira", "fogão", "micro-ondas", "mesa"],
      "orcamento_total": 700.0}, _CAND),
    ({"intencao": "montar a cozinha", "categorias": ["geladeira", "fogão"], "orcamento_total": 450.0}, _CAND),
    ({"intencao": "uma geladeira", "categorias": ["geladeira"], "orcamento_total": None}, _CAND[:2]),
    ({"intencao": "cozinha barata", "categorias": ["fogão", "micro-ondas"], "orcamento_total": 200.0}, _CAND),
    ({"intencao": "mesa", "categorias": ["mesa"], "orcamento_total": 150.0}, [_CAND[4]]),
    ({"intencao": "montar a cozinha", "categorias": ["geladeira", "micro-ondas", "mesa"],
      "orcamento_total": 1000.0}, _CAND),
]


def _salvar(nome: str, dados: dict) -> None:
    destino = config.LOGS_DIR / "medicoes" / f"prompts_{nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados = {"data": datetime.now().isoformat(timespec="seconds"), "modelo": config.MODELO,
             "prompts": llm.prompts_em_uso(), **dados}
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {dados['resumo']}  (logs/medicoes/{destino.name})")


def testar_triagem(sistema: str | None = None, rotulo: str = "triagem") -> dict:
    sistema = sistema or llm.carregar_prompt("triagem-v2.md")
    linhas = []
    for msg, esperado, fronteira in TRIAGEM:
        r, _ = llm.chamada_estruturada(sistema, f"usuario: {msg}", Triagem, max_tokens=200)
        linhas.append({"mensagem": msg, "esperado": esperado, "obtido": r.rota, "fronteira": fronteira,
                       "ok": r.rota == esperado})
    claras = [l for l in linhas if not l["fronteira"]]
    fronteira = [l for l in linhas if l["fronteira"]]
    resumo = (f"claras {sum(l['ok'] for l in claras)}/{len(claras)} · "
              f"fronteira {sum(l['ok'] for l in fronteira)}/{len(fronteira)}")
    res = {"resumo": resumo, "casos": linhas}
    _salvar(rotulo, res)
    return res


def testar_avaliador() -> None:
    sistema = llm.carregar_prompt("avaliador-anuncio-v4.md")
    linhas = []
    for rasc, conversa, indicio, esperado, nome in AVALIADOR:
        r, _ = llm.chamada_estruturada(sistema, json.dumps(
            {"rascunho": rasc, "conversa": conversa, "indicio_registrado": indicio}, ensure_ascii=False),
            Avaliacao, max_tokens=400)
        final = all([r.tem_titulo, r.tem_categoria, r.tem_descricao, r.estado_coerente, r.sem_invencao])
        linhas.append({"caso": nome, "esperado": esperado, "obtido": final, "ok": final == esperado,
                       "faltando": r.faltando})
    _salvar("avaliador", {"resumo": f"{sum(l['ok'] for l in linhas)}/{len(linhas)}", "casos": linhas})


def testar_interpretar() -> None:
    sistema = llm.carregar_prompt("compra-interpretar-v1.md")
    linhas = []
    for texto, obrig, permit, orc, bairro in INTERPRETAR:
        r, _ = llm.chamada_estruturada(sistema, f"usuario: {texto}", PedidoCompra, max_tokens=300)
        cats = set(r.categorias)
        cats_ok = obrig <= cats <= (permit or set()) if permit else not cats
        inventou = ((orc is None and r.orcamento_total is not None)
                    or (bairro is None and r.bairro is not None)
                    or (orc is not None and r.orcamento_total not in (orc, None) and r.preco_max_item != orc))
        linhas.append({"texto": texto, "categorias": sorted(cats), "orcamento": r.orcamento_total,
                       "preco_max_item": r.preco_max_item, "bairro": r.bairro,
                       "faltando": r.faltando, "categorias_ok": cats_ok, "inventou_valor": inventou})
    _salvar("interpretar", {"resumo": f"categorias {sum(l['categorias_ok'] for l in linhas)}/{len(linhas)} · "
                                      f"sem valor inventado {sum(not l['inventou_valor'] for l in linhas)}/{len(linhas)}",
                            "casos": linhas})


def testar_sugestao() -> None:
    sistema = llm.carregar_prompt("compra-sugestao-v1.md")
    linhas = []
    for pedido, cand in SUGESTAO:
        cand = [c for c in cand if c["categoria"] in pedido["categorias"]]
        r, _ = llm.chamada_estruturada(sistema, json.dumps({"pedido": pedido, "candidatos": cand},
                                                           ensure_ascii=False), Sugestao, max_tokens=300)
        por_id = {c["id"]: c for c in cand}
        soma_modelo = sum(por_id[i]["preco"] for i in r.itens_ids if i in por_id)
        itens, correcoes = conferir_sugestao(r, cand, pedido["orcamento_total"], pedido["categorias"])
        orc = pedido["orcamento_total"]
        linhas.append({"pedido": pedido, "ids_do_modelo": r.itens_ids,
                       "id_inventado": any(i not in por_id for i in r.itens_ids),
                       "modelo_estourou": bool(orc and soma_modelo > orc), "soma_modelo": soma_modelo,
                       "soma_final": sum(i["preco"] for i in itens), "correcoes": correcoes,
                       "final_ok": not (orc and sum(i["preco"] for i in itens) > orc)})
    _salvar("sugestao", {"resumo": f"modelo sem id inventado {sum(not l['id_inventado'] for l in linhas)}/{len(linhas)} · "
                                   f"modelo dentro do orçamento {sum(not l['modelo_estourou'] for l in linhas)}/{len(linhas)} · "
                                   f"final (após conferência) {sum(l['final_ok'] for l in linhas)}/{len(linhas)}",
                         "casos": linhas})


def testar_resposta() -> None:
    sistema = llm.carregar_prompt("resposta-regras-v1.md")
    perguntas = json.loads((config.DADOS_DIR / "perguntas_rag.json").read_text(encoding="utf-8"))
    linhas = []
    for p in perguntas:
        b = rag.buscar(p["pergunta"])
        if not b["suficiente"]:
            linhas.append({"id": p["id"], "portao": "recusou", "base_suficiente": False, "citacoes_validas": [],
                           "esperado_recusa": not p["esperado"] or p["forma"] == "fora_do_corpus",
                           "ok": not p["esperado"] or p["id"] == "Q15"})
            continue
        ctx = json.dumps([{"id": t["id"], "secao": t["secao"], "texto": t["texto"]} for t in b["trechos"]],
                         ensure_ascii=False)
        r, _ = llm.chamada_estruturada(sistema, f"PERGUNTA: {p['pergunta']}\n\nTRECHOS:\n{ctx}",
                                       RespostaRegras, max_tokens=400)
        validas = rag.verificar_citacoes(r.citacoes, b["trechos"])["validas"]
        if p["esperado"]:
            ok = r.base_suficiente and bool(set(validas) & set(p["esperado"]))
        else:
            ok = not r.base_suficiente
        linhas.append({"id": p["id"], "portao": "passou", "base_suficiente": r.base_suficiente,
                       "citacoes_validas": validas, "resposta": r.resposta, "ok": ok})
    _salvar("resposta", {"resumo": f"{sum(l['ok'] for l in linhas)}/{len(linhas)}", "casos": linhas})


FRASE = ('- Perguntar "posso vender X?" ou "é permitido anunciar X?" é `duvida` (é sobre\n'
         '  a regra), não `vender`.\n')


def regra_da_frase() -> None:
    original = llm.carregar_prompt("triagem-v1.md")
    assert FRASE in original, "a frase do exercício não está mais no prompt"
    com = testar_triagem(original, "frase_com")
    sem = testar_triagem(original.replace(FRASE, ""), "frase_sem")
    mudou = [{"mensagem": a["mensagem"], "com_a_frase": a["obtido"], "sem_a_frase": b["obtido"]}
             for a, b in zip(com["casos"], sem["casos"]) if a["obtido"] != b["obtido"]]
    _salvar("regra_da_frase", {"resumo": f"com: {com['resumo']} | sem: {sem['resumo']} | "
                                         f"{len(mudou)} mensagem(ns) mudaram de rota",
                               "frase": FRASE.strip(), "mudancas": mudou})


ETAPAS = {"triagem": testar_triagem, "avaliador": testar_avaliador, "interpretar": testar_interpretar,
          "sugestao": testar_sugestao, "resposta": testar_resposta, "frase": regra_da_frase}

if __name__ == "__main__":
    for nome in (sys.argv[1:] or [e for e in ETAPAS if e != "frase"]):
        print(f"== {nome}")
        ETAPAS[nome]()

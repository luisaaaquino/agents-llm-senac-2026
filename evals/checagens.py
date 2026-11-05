"""
As checagens de cada caso, separadas por nível de avaliação.

  deterministico  igualdade, expressão regular e validação do schema da saída
  trajetoria      as ferramentas chamadas e quantas vezes, lidas no trace
  resultado       o estado do mundo depois da execução (banco e memória)
  juiz            um modelo julga uma propriedade sem gabarito (evals/juiz.py)

Cada checagem devolve {"nivel", "nome", "ok", "detalhe"}. Um caso passa
quando todas as checagens que valem para ele passam.
"""
from __future__ import annotations

import json
import re
from contextlib import closing
from typing import Any

from src import db, memoria
from src.contrato import SaidaSistema


def _c(nivel: str, nome: str, ok: bool, detalhe: Any = None) -> dict[str, Any]:
    return {"nivel": nivel, "nome": nome, "ok": bool(ok), "detalhe": detalhe}


def _em(valor: Any, esperado: Any) -> bool:
    return valor in esperado if isinstance(esperado, list) else valor == esperado


# --- o estado do mundo ------------------------------------------------------------

def mundo(usuario_id: str) -> dict[str, Any]:
    """O que o sistema escreveu para este usuário: anúncios, indícios e a memória
    semântica das categorias."""
    with closing(db.conectar()) as con:
        anuncios = [dict(r) for r in con.execute(
            "SELECT id, titulo, status, preco, descricao, estado_conservacao, categoria FROM anuncios "
            "WHERE vendedor_id = ?", (usuario_id,))]
        indicios = [dict(r) for r in con.execute(
            "SELECT id, status, indicio, decidido_por FROM indicios_moderacao WHERE vendedor_id = ?",
            (usuario_id,))]
    mem = {f"categoria:{c}": [f["valor"] for f in memoria.ler_fatos(f"categoria:{c}")
                              if f["chave"] == "avarias_tipicas"]
           for c in db.CATEGORIAS}
    return {"anuncios": anuncios, "indicios": indicios, "memoria_categorias": mem}


# --- as checagens -----------------------------------------------------------------

def deterministicas(esp: dict[str, Any], log: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    saidas = [t["saida"] for t in log["turnos"]]
    validas = True
    for s in saidas:
        try:
            SaidaSistema.model_validate(s)
        except Exception:  # noqa: BLE001
            validas = False
    out.append(_c("deterministico", "saida_valida_no_schema", validas, f"{len(saidas)} saídas"))
    # a resposta à aprovação repetida é só a prova de idempotência; a saída
    # final da conversa é a anterior a ela
    principais = [t["saida"] for t in log["turnos"] if t["tipo"] != "decisao_humana_repetida"]
    final = principais[-1] if principais else {}
    repetidas = [t["saida"] for t in log["turnos"] if t["tipo"] == "decisao_humana_repetida"]
    if repetidas:
        out.append(_c("deterministico", "aprovacao_repetida_sem_efeito",
                      repetidas[0]["motivo_termino"].startswith("resposta repetida"),
                      repetidas[0]["motivo_termino"]))
    if "tipo" in esp:
        out.append(_c("deterministico", "tipo_final", _em(final.get("tipo"), esp["tipo"]),
                      {"obtido": final.get("tipo"), "esperado": esp["tipo"]}))
    if "termino" in esp:
        out.append(_c("deterministico", "termino_final", _em(final.get("termino"), esp["termino"]),
                      {"obtido": final.get("termino"), "esperado": esp["termino"]}))
    if "primeiro_tipo" in esp:
        out.append(_c("deterministico", "primeiro_tipo", saidas and saidas[0]["tipo"] == esp["primeiro_tipo"],
                      saidas[0]["tipo"] if saidas else None))
    if "algum_tipo" in esp:
        tipos = [s["tipo"] for s in saidas]
        out.append(_c("deterministico", "algum_tipo", esp["algum_tipo"] in tipos, tipos))
    if "base_suficiente" in esp:
        obtido = (final.get("suficiencia") or {}).get("base_suficiente")
        out.append(_c("deterministico", "base_suficiente", obtido == esp["base_suficiente"], obtido))
    if "regex_resultado" in esp:
        out.append(_c("deterministico", "regex_resultado",
                      re.search(esp["regex_resultado"], final.get("resultado", "")), esp["regex_resultado"]))
    if "regex_resultado_nao" in esp:
        achou = re.search(esp["regex_resultado_nao"], final.get("resultado", ""))
        out.append(_c("deterministico", "regex_resultado_nao", not achou,
                      achou.group(0) if achou else None))
    if "algum_resultado_regex" in esp:
        achou = any(re.search(esp["algum_resultado_regex"], s.get("resultado", "")) for s in saidas)
        out.append(_c("deterministico", "algum_resultado_regex", achou, esp["algum_resultado_regex"]))
    refs = [f["ref"] for f in final.get("fontes", [])]
    if "fontes_contem" in esp:
        out.append(_c("deterministico", "fontes_contem", all(r in refs for r in esp["fontes_contem"]), refs))
    if "fontes_exatas" in esp:
        corpus = [f["ref"] for f in final.get("fontes", []) if f["tipo"] == "corpus"]
        out.append(_c("deterministico", "fontes_exatas", sorted(corpus) == sorted(esp["fontes_exatas"]), corpus))
    return out


def ferramentas_do_trace(spans: list[dict[str, Any]], thread_id: str) -> dict[str, int]:
    """Quantas vezes cada ferramenta rodou nesta conversa, lido nos spans."""
    traces = {s["trace_id"] for s in spans if s["parent_id"] is None
              and s["atributos"].get("gen_ai.conversation.id") == thread_id}
    contagem: dict[str, int] = {}
    for s in spans:
        if s["trace_id"] in traces and s["atributos"].get("gen_ai.operation.name") == "execute_tool":
            nome = s["atributos"]["gen_ai.tool.name"]
            contagem[nome] = contagem.get(nome, 0) + 1
    return contagem


def de_trajetoria(esp: dict[str, Any], ferramentas: dict[str, int]) -> list[dict[str, Any]]:
    t = esp.get("trajetoria") or {}
    out = []
    for nome in t.get("chama", []):
        out.append(_c("trajetoria", f"chama:{nome}", ferramentas.get(nome, 0) >= 1, ferramentas))
    for nome in t.get("nao_chama", []):
        out.append(_c("trajetoria", f"nao_chama:{nome}", ferramentas.get(nome, 0) == 0, ferramentas))
    for nome, n in (t.get("max") or {}).items():
        out.append(_c("trajetoria", f"max:{nome}<={n}", ferramentas.get(nome, 0) <= n, ferramentas))
    for nome, n in (t.get("min") or {}).items():
        out.append(_c("trajetoria", f"min:{nome}>={n}", ferramentas.get(nome, 0) >= n, ferramentas))
    return out


def de_resultado(esp: dict[str, Any], antes: dict[str, Any], depois: dict[str, Any],
                 log: dict[str, Any]) -> list[dict[str, Any]]:
    r = esp.get("resultado") or {}
    out = []
    ativos = [a for a in depois["anuncios"] if a["status"] == "ativo"]
    if "anuncios_ativos" in r:
        out.append(_c("resultado", "anuncios_ativos", len(ativos) == r["anuncios_ativos"],
                      {"obtido": len(ativos), "esperado": r["anuncios_ativos"]}))
    if "anuncios_total" in r:
        n = len(depois["anuncios"]) - len(antes["anuncios"])
        out.append(_c("resultado", "anuncios_criados", n == r["anuncios_total"],
                      {"obtido": n, "esperado": r["anuncios_total"]}))
    if "preco_ativo" in r:
        precos = [a["preco"] for a in ativos]
        out.append(_c("resultado", "preco_ativo", precos == [float(r["preco_ativo"])], precos))
    publicados = [a for a in depois["anuncios"] if a["status"] in ("ativo", "aguardando_moderacao")]
    if "descricao_regex" in r:
        ok = bool(publicados) and all(re.search(r["descricao_regex"], a["descricao"]) for a in publicados)
        out.append(_c("resultado", "descricao_regex", ok, [a["descricao"] for a in publicados]))
    if "estado_nao_em" in r:
        estados = [a["estado_conservacao"] for a in publicados]
        out.append(_c("resultado", "estado_nao_em", bool(estados) and not any(e in r["estado_nao_em"] for e in estados),
                      estados))
    if "indicios" in r:
        out.append(_c("resultado", "indicios", len(depois["indicios"]) == r["indicios"],
                      [i["status"] for i in depois["indicios"]]))
    if "indicios_pendentes" in r:
        pend = [i for i in depois["indicios"] if i["status"] == "pendente"]
        out.append(_c("resultado", "indicios_pendentes", len(pend) == r["indicios_pendentes"],
                      [(i["status"], i["decidido_por"]) for i in depois["indicios"]]))
    for entidade, padrao in (r.get("memoria_sem_regex") or {}).items():
        valores = depois["memoria_categorias"].get(entidade, [])
        texto = json.dumps(valores, ensure_ascii=False)
        out.append(_c("resultado", f"memoria_sem:{entidade}", not re.search(padrao, texto), valores))
    return out


def de_compra(esp: dict[str, Any], log: dict[str, Any]) -> list[dict[str, Any]]:
    c = esp.get("compra")
    if not c:
        return []
    dados = (log["turnos"][-1]["saida"].get("dados") or {})
    itens = dados.get("itens") or []
    out = []
    if "soma_max" in c:
        soma = sum(i["preco"] for i in itens)
        out.append(_c("resultado", "soma_no_orcamento", bool(itens) and soma <= c["soma_max"], soma))
    if "preco_max_item" in c:
        out.append(_c("resultado", "preco_max_item", bool(itens) and all(i["preco"] <= c["preco_max_item"] for i in itens),
                      [i["preco"] for i in itens]))
    if "categoria" in c:
        out.append(_c("resultado", "categoria", bool(itens) and all(i["categoria"] == c["categoria"] for i in itens),
                      [i["categoria"] for i in itens]))
    if "min_itens" in c:
        out.append(_c("resultado", "min_itens", len(itens) >= c["min_itens"], len(itens)))
    if "sem_vendedor" in c and itens:
        with closing(db.conectar()) as con:
            vendedores = [con.execute("SELECT vendedor_id FROM anuncios WHERE id = ?", (i["id"],)).fetchone()[0]
                          for i in itens]
        out.append(_c("resultado", "sem_item_do_proprio_comprador", c["sem_vendedor"] not in vendedores, vendedores))
    return out

"""
Santo Desapego — Agente B (Assistente de anúncio).

Agente simples da Parte 1. Reaproveita o scaffolding do lab da Aula 05
(`aula05-analista/08-analista.py`): estado explícito, orçamento com três tetos,
quatro formas de terminar, detector de laço, log de trajetória e carimbo de
prompt. O domínio é outro (marketplace, não prestação de contas) e as
ferramentas conversam com SQLite (ver `src/db.py`, requisito §4.2).

Como rodar: ver README.md na raiz.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

import db

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")
MODELO = os.environ.get("LLM_MODELO", "mistral-small-latest")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

PROMPTS_DIR = ROOT / "prompts"
LOGS_DIR = ROOT / "logs"


def ler_prompt(nome: str) -> str:
    return (PROMPTS_DIR / nome).read_text(encoding="utf-8")


PROMPT_AGENTE = ler_prompt("agente-anuncio-v4.md")
PROMPT_AVALIADOR = ler_prompt("avaliador-anuncio-v2.md")

# Carimbo prompt x modelo x parâmetros (rastreabilidade, §4.1)
CARIMBO = {
    "agente": "agente-anuncio-v4.md",
    "avaliador": "avaliador-anuncio-v2.md",
    "modelo": MODELO,
    "temperatura": 0,
}


# --- Tetos, vindos da arquitetura (docs/arquitetura.md, Agente B) -----------
MAX_PASSOS = 12
MAX_TOKENS = 60_000
MAX_SEGUNDOS = 120.0
MAX_RODADAS_AVALIADOR = 3

# Teto de dinheiro (§4.1 exige, "se houver custo"). Rodando local via Ollama
# o custo real é US$ 0 — este teto só passa a valer de verdade se o .env
# apontar pra uma API paga (Mistral). PRECO_USD_POR_TOKEN usa o preço de
# SAÍDA da Mistral Small ($0,60/M tok, o mais caro dos dois — ver
# docs/modelos.md §3.2), então o teto é conservador (superestima o custo).
# MAX_CUSTO_USD é ~7x o custo medido de uma execução normal (~US$0,0014).
PRECO_USD_POR_TOKEN = 0.60 / 1_000_000
MAX_CUSTO_USD = 0.01


class Termino(str, Enum):
    RESPONDEU = "respondeu"          # anúncio publicado
    ORCAMENTO = "orcamento"          # estourou passos/tokens/tempo/dinheiro
    ERRO_FATAL = "erro_fatal"        # não há como continuar
    HUMANO = "humano"                # suspenso p/ moderação (avaria negada)
    LACO = "laco"


@dataclass
class Orcamento:
    max_passos: int = MAX_PASSOS
    max_tokens: int = MAX_TOKENS
    max_segundos: float = MAX_SEGUNDOS
    max_custo_usd: float = MAX_CUSTO_USD
    usados_tokens: int = 0
    custo_usd: float = 0.0

    def registra_tokens(self, tokens: int) -> None:
        self.usados_tokens += tokens
        self.custo_usd += tokens * PRECO_USD_POR_TOKEN

    def verifica(self, inicio: float, passos: int) -> Termino | None:
        if passos >= self.max_passos:
            return Termino.ORCAMENTO
        if self.usados_tokens >= self.max_tokens:
            return Termino.ORCAMENTO
        if self.custo_usd >= self.max_custo_usd:
            return Termino.ORCAMENTO
        if time.monotonic() - inicio >= self.max_segundos:
            return Termino.ORCAMENTO
        return None


@dataclass
class Estado:
    objetivo: str
    conversa: list[dict[str, str]] = field(default_factory=list)
    rascunho: dict[str, Any] = field(default_factory=dict)
    observacoes: list[dict[str, Any]] = field(default_factory=list)
    trajetoria: list[dict[str, Any]] = field(default_factory=list)
    roteiro_vendedor: list[str] = field(default_factory=list)  # falas mock (demo)
    idx_vendedor: int = 0
    passos: int = 0
    tokens: int = 0
    inicio: float = field(default_factory=time.monotonic)
    termino: Termino | None = None


AGENTE_SCHEMA = {
    "type": "object",
    "properties": {
        "acao": {
            "type": "string",
            "enum": ["perguntar", "consultar_preco", "preencher_rascunho",
                     "publicar", "registrar_indicio", "concluir"],
        },
        "pergunta": {"type": "string", "minLength": 1},
        "categoria": {"type": "string", "minLength": 1},
        "bairro": {"type": "string", "minLength": 1},
        "rascunho": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "minLength": 1},
                "categoria": {"type": "string", "minLength": 1},
                "descricao": {"type": "string", "minLength": 1},
                "preco": {"type": "number"},
                "bairro": {"type": "string", "minLength": 1},
                "estado_declarado": {"type": "boolean"},
            },
            "required": ["titulo", "categoria", "descricao", "preco",
                         "bairro", "estado_declarado"],
            "additionalProperties": False,
        },
        "indicio": {"type": "string", "minLength": 1},
    },
    # "pergunta"/"categoria"/"bairro"/"indicio"/"rascunho" são obrigatórios e
    # não-vazios mesmo nos passos em que a ação não os usa: sem isso, modelos
    # menores (llama3.2 3B local, e o qwen2.5:7b às vezes) cumprem o schema à
    # risca mas devolvem esses campos vazios ou ausentes — ex.: `consultar_preco`
    # com categoria="" e bairro="" gera "sem_comparaveis" por engano, mesmo
    # quando a base tem preço pra a categoria real; `preencher_rascunho` sem
    # "rascunho" no payload vira `{}` e reprova os 5 critérios do avaliador de
    # uma vez. O schema sozinho não basta pra garantir conteúdo coerente com a
    # ação escolhida (achado real, ver docs/modelos.md §3.3).
    "required": ["acao", "pergunta", "categoria", "bairro", "rascunho", "indicio"],
    "additionalProperties": False,
}


def chamada_estruturada(prompt: str, schema: dict[str, Any], nome: str,
                        max_tokens: int = 600) -> tuple[dict[str, Any], int]:
    resposta = client.chat.completions.create(
        model=MODELO,
        temperature=0,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": nome, "strict": True, "schema": schema},
        },
    )
    conteudo = resposta.choices[0].message.content or "{}"
    tokens = resposta.usage.total_tokens if resposta.usage else 0
    return json.loads(conteudo), tokens


def detectar_laco(estado: Estado, acao: str) -> bool:
    ultimas = [t["acao"] for t in estado.trajetoria[-3:]]
    return len(ultimas) == 3 and all(a == acao for a in ultimas)


def _proxima_fala_vendedor(estado: Estado) -> str | None:
    if estado.idx_vendedor < len(estado.roteiro_vendedor):
        fala = estado.roteiro_vendedor[estado.idx_vendedor]
        estado.idx_vendedor += 1
        return fala
    return None


def rodar_agente(roteiro_vendedor: list[str]) -> dict[str, Any]:
    estado = Estado(
        objetivo="Montar um anúncio completo e honesto no Santo Desapego.",
        roteiro_vendedor=roteiro_vendedor,
    )
    # primeira fala do vendedor entra na conversa
    primeira = _proxima_fala_vendedor(estado)
    if primeira:
        estado.conversa.append({"quem": "vendedor", "texto": primeira})

    orcamento = Orcamento()

    while estado.termino is None:
        limite = orcamento.verifica(estado.inicio, estado.passos)
        if limite:
            estado.termino = limite
            break

        # Técnica: ReAct (raciocínio + ação por passo), zero-shot — o prompt
        # descreve as 6 ações possíveis e o contrato, sem exemplos fixos,
        # porque a próxima pergunta certa depende do que já foi dito, não de
        # um roteiro fixo (ver prompts/agente-anuncio-v1.md).
        # Contrato de saída: JSON estrito pelo AGENTE_SCHEMA (uma ação por passo).
        # O que impede: `additionalProperties: False` e `enum` na ação impedem o
        # modelo de inventar uma ação fora das 6 previstas ou devolver texto solto.
        contexto = {
            "conversa": estado.conversa[-8:],
            "rascunho": estado.rascunho,
            "observacoes": estado.observacoes[-4:],
        }
        prompt = (PROMPT_AGENTE + "\n\nCONTEXTO ATUAL:\n"
                  + json.dumps(contexto, ensure_ascii=False, indent=2))

        decisao, tokens = chamada_estruturada(prompt, AGENTE_SCHEMA,
                                              "decisao_agente")
        estado.passos += 1
        estado.tokens += tokens
        orcamento.registra_tokens(tokens)
        acao = decisao["acao"]

        if detectar_laco(estado, acao):
            estado.termino = Termino.LACO
            estado.trajetoria.append({"passo": estado.passos, "acao": acao,
                                      "nota": "laco detectado"})
            break

        registro: dict[str, Any] = {"passo": estado.passos, "acao": acao,
                                    "tokens": tokens}

        if acao == "perguntar":
            estado.conversa.append({"quem": "agente",
                                    "texto": decisao.get("pergunta", "")})
            fala = _proxima_fala_vendedor(estado)
            if fala is None:
                # vendedor não respondeu mais nada: encerra sem publicar
                estado.termino = Termino.ORCAMENTO
                registro["resultado"] = "sem resposta do vendedor"
            else:
                estado.conversa.append({"quem": "vendedor", "texto": fala})
                registro["resultado"] = "vendedor respondeu"

        elif acao == "consultar_preco":
            argumentos = {"categoria": decisao.get("categoria", ""),
                          "bairro": decisao.get("bairro", "")}
            r = db.consultar_preco_comparaveis(**argumentos)
            estado.observacoes.append({"tool": "consultar_preco", "resultado": r})
            registro["argumentos"] = argumentos
            registro["resultado"] = r
            # erro de ferramenta é DADO, não exceção: o modelo segue mesmo assim

        elif acao == "preencher_rascunho":
            estado.rascunho = decisao.get("rascunho", {})
            aval, tokens_aval = avaliar_rascunho(estado.rascunho)
            estado.tokens += tokens_aval
            orcamento.registra_tokens(tokens_aval)
            estado.observacoes.append({"tool": "avaliador", "resultado": aval})
            registro["argumentos"] = {"rascunho": estado.rascunho}
            registro["resultado"] = aval
            registro["tokens_avaliador"] = tokens_aval

        elif acao == "registrar_indicio":
            argumentos = {"anuncio_ref": "rascunho-atual",
                          "indicio": decisao.get("indicio", "")}
            r = db.registrar_indicio_avaria(**argumentos)
            estado.observacoes.append({"tool": "registrar_indicio",
                                       "resultado": r})
            registro["argumentos"] = argumentos
            registro["resultado"] = r
            estado.termino = Termino.HUMANO   # suspende p/ moderação

        elif acao == "publicar":
            r = db.publicar_anuncio(estado.rascunho)
            estado.observacoes.append({"tool": "publicar", "resultado": r})
            registro["argumentos"] = {"rascunho": estado.rascunho}
            registro["resultado"] = r
            estado.termino = (Termino.RESPONDEU if r.get("ok")
                              else Termino.ERRO_FATAL)

        elif acao == "concluir":
            estado.termino = Termino.RESPONDEU

        estado.trajetoria.append(registro)

    return {
        "termino": estado.termino.value if estado.termino else "desconhecido",
        "passos": estado.passos,
        "tokens": estado.tokens,
        "rascunho": estado.rascunho,
        "conversa": estado.conversa,
        "trajetoria": estado.trajetoria,
        "carimbo": CARIMBO,
    }


AVALIADOR_SCHEMA = {
    "type": "object",
    "properties": {
        "aprovado": {"type": "boolean"},
        "faltando": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["aprovado", "faltando"],
    "additionalProperties": False,
}


def avaliar_rascunho(rascunho: dict[str, Any]) -> tuple[dict[str, Any], int]:
    # Técnica: verificador com critério booleano (avaliador-otimizador) —
    # separa quem escreve (a etapa `preencher_rascunho`) de quem confere,
    # cada um dos 5 critérios do checklist é avaliado isoladamente, sem
    # exemplos (zero-shot), porque o critério já é objetivo o bastante
    # (ver prompts/avaliador-anuncio-v1.md).
    # Contrato de saída: JSON estrito pelo AVALIADOR_SCHEMA — `aprovado`
    # (bool) + `faltando` (lista de critérios).
    # O que impede: só aprova (`aprovado=true`) quando os 5 critérios batem;
    # isso impede publicar um rascunho incompleto ou com avaria não tratada
    # só porque o agente "achou" que já tinha o suficiente.
    prompt = (PROMPT_AVALIADOR + "\n\nRASCUNHO:\n"
              + json.dumps(rascunho, ensure_ascii=False, indent=2))
    resultado, tokens = chamada_estruturada(prompt, AVALIADOR_SCHEMA, "avaliacao",
                                            max_tokens=300)
    return resultado, tokens


def salvar_log(nome_caso: str, resultado: dict[str, Any]) -> Path:
    LOGS_DIR.mkdir(exist_ok=True)
    caminho = LOGS_DIR / f"{nome_caso}.json"
    caminho.write_text(json.dumps(resultado, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return caminho


# --- Os 4 casos da §4.5, com falas mock do vendedor -------------------------
CASOS_DEMO: dict[str, list[str]] = {
    "01_simples": [
        "quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro",
        "5 anos de uso, funciona bem, sem defeito",
        "capacidade de uns 400 litros, duplex mesmo. Pode confirmar o preço e publicar",
    ],
    "02_divergencia_preco": [
        "vendo geladeira duplex por 900 reais, Santo Amaro",
        "sei que é caro mas quero esse valor",
        "pode manter 900 mesmo assim",
        "5 anos de uso, funciona bem, sem defeito. Pode publicar com 900 mesmo",
    ],
    "03_sem_registro": [
        "quero anunciar uma bicicleta, uns 500 reais, Santo Amaro",
        "aro 29, seminova, sem defeito",
        "pode confirmar o preço e publicar, não tenho mais nada pra falar",
    ],
    "04_avaria_negada": [
        "vendo geladeira consul, 380 reais, Santo Amaro",
        "ah, o freezer embaixo demora pra congelar, mas prefiro não pôr isso",
        "não, não quero declarar",
    ],
    # Caso 5 (§3.3 de docs/modelos.md — verificação mínima em 3 modelos,
    # não é um dos 4 oficiais da §4.5): avaria DECLARADA de boa vontade —
    # diferente do caso 1 (sem avaria) e do caso 4 (avaria negada). Testa se
    # o agente escreve o defeito real na descrição e publica normal, SEM
    # chamar registrar_indicio (só cabe quando o vendedor recusa declarar).
    "05_avaria_declarada": [
        "quero vender um sofá 3 lugares veludo verde, uns 300 reais, Santo Amaro",
        "tem um pé com uma rachadura pequena, mas fora isso tá ótimo — pode colocar isso na descrição",
        "pode confirmar o preço e publicar",
    ],
}


def selftest_offline() -> None:
    """
    Exercita a camada tradicional + idempotência SEM LLM (útil quando a API
    está indisponível). Gera um log real das ferramentas.
    """
    db.inicializar()
    passos = []
    passos.append(("preco_ok",
                   db.consultar_preco_comparaveis("geladeira", "Santo Amaro")))
    passos.append(("preco_sem_registro",
                   db.consultar_preco_comparaveis("bicicleta", "Santo Amaro")))
    rasc = {"titulo": "Geladeira Consul Duplex", "categoria": "geladeira",
            "descricao": "5 anos, funciona bem", "preco": 350.0,
            "bairro": "Santo Amaro", "estado_declarado": True}
    p1 = db.publicar_anuncio(rasc)
    p2 = db.publicar_anuncio(rasc)   # idempotência: não duplica
    passos.append(("publicar_1", p1))
    passos.append(("publicar_2_idempotente", p2))
    passos.append(("indicio",
                   db.registrar_indicio_avaria("rascunho-atual",
                                               "freezer não congela")))
    salvar_log("selftest_offline", {"selftest": passos})
    for nome, r in passos:
        print(f"  {nome}: {json.dumps(r, ensure_ascii=False)}")
    print("\nSelftest offline OK — log em logs/selftest_offline.json")


def main() -> None:
    import sys
    if "--selftest" in sys.argv:
        selftest_offline()
        return

    db.inicializar()
    for nome, roteiro in CASOS_DEMO.items():
        print(f"\n=== CASO {nome} ===")
        resultado = rodar_agente(roteiro)
        caminho = salvar_log(nome, resultado)
        print(f"  termino={resultado['termino']} "
              f"passos={resultado['passos']} tokens={resultado['tokens']}")
        print(f"  log: {caminho.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

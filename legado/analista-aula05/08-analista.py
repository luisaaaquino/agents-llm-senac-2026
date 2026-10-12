# Aula 05 — Exercício 05
# 08 — Analista de prestação de contas
#
# Arquitetura:
# regra -> router -> portão -> agente com estado
#        -> orquestrador-trabalhador -> avaliador-otimizador
#
# O objetivo do exercício é demonstrar que a autonomia cara fica
# confinada aos casos que realmente precisam de modelo.

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")
MODELO = os.environ.get("LLM_MODELO", "mistral-small-latest")
MODELO_GRANDE = os.environ.get("LLM_MODELO_GRANDE", MODELO)

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY
)

ALCADA_ANALISTA = 500.00

POLITICA = {
    "refeicao": {
        "artigo": "Art. 4",
        "teto_por_pessoa": 120.00,
        "exige_nota": True
    },
    "transporte": {
        "artigo": "Art. 5",
        "teto_unitario": 90.00,
        "exige_nota": False
    },
    "hospedagem": {
        "artigo": "Art. 6",
        "teto_diaria": 380.00,
        "exige_nota": True
    },
    "material": {
        "artigo": "Art. 9",
        "teto_unitario": 50.00,
        "exige_nota": True
    }
}

FUNCIONARIOS = {
    "F-088": {"nome": "Ana Souza", "centro_custo": "COMERCIAL"},
    "F-091": {"nome": "Bruno Lima", "centro_custo": "TECNOLOGIA"},
    "F-103": {"nome": "Célia Rocha", "centro_custo": "COMERCIAL"}
}

DESPESAS = {
    "D-4471": {
        "funcionario": "F-088",
        "categoria": "refeicao",
        "valor": 84.00,
        "pessoas": 1,
        "tem_nota": True,
        "descricao": "almoço em visita a cliente"
    },
    "D-4472": {
        "funcionario": "F-091",
        "categoria": "transporte",
        "valor": 45.00,
        "pessoas": 1,
        "tem_nota": False,
        "descricao": "táxi aeroporto-hotel"
    },
    "D-4473": {
        "funcionario": "F-088",
        "categoria": "refeicao",
        "valor": 312.00,
        "pessoas": 3,
        "tem_nota": True,
        "descricao": "jantar com equipe do cliente"
    },
    "D-4474": {
        "funcionario": "F-103",
        "categoria": "hospedagem",
        "valor": 1240.00,
        "diarias": 2,
        "tem_nota": True,
        "descricao": "hotel, congresso setorial"
    },
    "D-4475": {
        "funcionario": "F-091",
        "categoria": "refeicao",
        "valor": 96.00,
        "pessoas": 1,
        "tem_nota": True,
        "descricao": "jantar, viagem a trabalho"
    },
    "D-4476": {
        "funcionario": "F-103",
        "categoria": "material",
        "valor": 50.00,
        "pessoas": 1,
        "tem_nota": False,
        "descricao": "material de escritório"
    },
    "D-4477": {
        "funcionario": "F-88",
        "categoria": "transporte",
        "valor": 38.00,
        "pessoas": 1,
        "tem_nota": False,
        "descricao": "aplicativo, reunião externa"
    },
    "D-4478": {
        "funcionario": "F-091",
        "categoria": "transporte",
        "valor": 130.00,
        "pessoas": 1,
        "tem_nota": True,
        "descricao": "táxi, trajeto longo, madrugada"
    }
}

RECIBOS = {
    "D-4471": 84.00,
    "D-4472": 45.00,
    "D-4473": 312.00,
    "D-4474": 1240.00,
    "D-4475": 196.00,
    "D-4476": 50.00,
    "D-4477": 38.00,
    "D-4478": 130.00
}

HISTORICO = {
    "F-088": [
        {"despesa": "D-4102", "veredito": "aprovado", "categoria": "refeicao"},
        {"despesa": "D-4188", "veredito": "aprovado", "categoria": "refeicao"}
    ],
    "F-091": [
        {
            "despesa": "D-4210",
            "veredito": "reprovado",
            "categoria": "transporte",
            "motivo": "acima do teto unitário, sem justificativa"
        }
    ],
    "F-103": []
}

PARECERES: dict[str, dict[str, Any]] = {}

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def ler_prompt(nome: str) -> str:
    return (PROMPTS_DIR / nome).read_text(encoding="utf-8")


PROMPT_ROUTER = ler_prompt("router-v1.md")
PROMPT_AGENTE = ler_prompt("agente-v1.md")
PROMPT_ORQUESTRADOR = ler_prompt("orquestrador-v1.md")
PROMPT_AVALIADOR = ler_prompt("avaliador-v1.md")


class Termino(str, Enum):
    CONCLUIDO = "concluido"
    ORCAMENTO_PASSOS = "orcamento_passos"
    ORCAMENTO_TOKENS = "orcamento_tokens"
    ORCAMENTO_TEMPO = "orcamento_tempo"
    HUMANO = "humano"
    ERRO = "erro"
    LACO = "laco"


@dataclass
class Orcamento:
    max_passos: int = 8
    max_tokens: int = 2500
    max_segundos: float = 30.0
    usados_tokens: int = 0

    def verifica(self, inicio: float, passos: int) -> Termino | None:
        if passos >= self.max_passos:
            return Termino.ORCAMENTO_PASSOS
        if self.usados_tokens >= self.max_tokens:
            return Termino.ORCAMENTO_TOKENS
        if time.monotonic() - inicio >= self.max_segundos:
            return Termino.ORCAMENTO_TEMPO
        return None


@dataclass
class Estado:
    despesa_id: str
    objetivo: str
    dados: dict[str, Any]
    historico: list[dict[str, Any]] = field(default_factory=list)
    observacoes: list[dict[str, Any]] = field(default_factory=list)
    passos: int = 0
    tokens: int = 0
    inicio: float = field(default_factory=time.monotonic)
    termino: Termino | None = None


def chamada_estruturada(
    prompt: str,
    schema: dict[str, Any],
    nome: str,
    temperatura: float,
    max_tokens: int,
    modelo: str = MODELO
) -> tuple[dict[str, Any], int]:
    resposta = client.chat.completions.create(
        model=modelo,
        temperature=temperatura,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": nome,
                "strict": True,
                "schema": schema
            }
        }
    )

    conteudo = resposta.choices[0].message.content or "{}"
    tokens = resposta.usage.total_tokens if resposta.usage else 0

    return json.loads(conteudo), tokens


ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "rota": {
            "type": "string",
            "enum": ["regra", "ambiguo", "humano", "nenhuma"]
        },
        "justificativa": {
            "type": "string"
        }
    },
    "required": ["rota", "justificativa"],
    "additionalProperties": False
}


AGENTE_SCHEMA = {
    "type": "object",
    "properties": {
        "acao": {
            "type": "string",
            "enum": [
                "consultar_politica",
                "consultar_historico",
                "registrar_parecer",
                "concluir"
            ]
        },
        "veredito": {
            "type": "string",
            "enum": ["aprovado", "reprovado", "revisao"]
        },
        "justificativa": {
            "type": "string"
        },
        "artigo": {
            "type": "string"
        }
    },
    "required": ["acao", "veredito", "justificativa", "artigo"],
    "additionalProperties": False
}


ORQUESTRADOR_SCHEMA = {
    "type": "object",
    "properties": {
        "parecer_lote": {
            "type": "string"
        },
        "itens": {
            "type": "array",
            "items": {
                "type": "string"
            }
        }
    },
    "required": ["parecer_lote", "itens"],
    "additionalProperties": False
}


AVALIADOR_SCHEMA = {
    "type": "object",
    "properties": {
        "criterios": {
            "type": "object",
            "properties": {
                "cita_artigo": {"type": "boolean"},
                "cita_valor": {"type": "boolean"},
                "conclui": {"type": "boolean"}
            },
            "required": ["cita_artigo", "cita_valor", "conclui"],
            "additionalProperties": False
        },
        "aprovado": {
            "type": "boolean"
        },
        "correcao": {
            "type": "string"
        }
    },
    "required": ["criterios", "aprovado", "correcao"],
    "additionalProperties": False
}


REVISAO_SCHEMA = {
    "type": "object",
    "properties": {
        "texto": {
            "type": "string"
        }
    },
    "required": ["texto"],
    "additionalProperties": False
}


def regra_deterministica(despesa_id: str) -> dict[str, Any] | None:
    d = DESPESAS[despesa_id]
    politica = POLITICA.get(d["categoria"])

    if politica is None:
        return None

    if d["funcionario"] not in FUNCIONARIOS:
        return None

    if d["categoria"] == "refeicao":
        limite = politica["teto_por_pessoa"] * d["pessoas"]

        if d["valor"] <= limite and (
            not politica["exige_nota"] or d["tem_nota"]
        ):
            return {
                "veredito": "aprovado",
                "artigo": politica["artigo"],
                "motivo": (
                    f"R$ {d['valor']:.2f} dentro do teto de "
                    f"R$ {limite:.2f} para {d['pessoas']} pessoa(s)"
                )
            }

    if d["categoria"] == "transporte":
        if d["valor"] <= politica["teto_unitario"] and (
            not politica["exige_nota"] or d["tem_nota"]
        ):
            return {
                "veredito": "aprovado",
                "artigo": politica["artigo"],
                "motivo": (
                    f"R$ {d['valor']:.2f} dentro do teto unitário de "
                    f"R$ {politica['teto_unitario']:.2f}"
                )
            }

    return None


def validar_portao(despesa_id: str) -> dict[str, Any] | None:
    d = DESPESAS[despesa_id]

    if d["funcionario"] not in FUNCIONARIOS:
        return {
            "motivo": (
                f"Funcionário '{d['funcionario']}' não existe. "
                "IDs válidos: F-088, F-091, F-103."
            )
        }

    if d["categoria"] not in POLITICA:
        return {
            "motivo": f"Categoria '{d['categoria']}' não existe na política."
        }

    valor_recibo = RECIBOS[despesa_id]

    if abs(d["valor"] - valor_recibo) > 0.009:
        return {
            "motivo": (
                f"Valor declarado R$ {d['valor']:.2f} diverge do "
                f"recibo R$ {valor_recibo:.2f}."
            )
        }

    return None


def consultar_politica(categoria: str) -> dict[str, Any]:
    return POLITICA.get(
        categoria,
        {
            "erro": "categoria_inexistente",
            "categoria": categoria
        }
    )


def consultar_historico(funcionario: str) -> dict[str, Any]:
    if funcionario not in HISTORICO:
        return {
            "erro": "funcionario_inexistente",
            "funcionario": funcionario
        }

    return {
        "funcionario": funcionario,
        "historico": HISTORICO[funcionario]
    }


def registrar_parecer(
    despesa_id: str,
    veredito: str,
    justificativa: str,
    artigo: str
) -> dict[str, Any]:
    material = {
        "despesa_id": despesa_id,
        "veredito": veredito,
        "justificativa": justificativa,
        "artigo": artigo
    }

    chave = sha256(
        json.dumps(
            material,
            sort_keys=True,
            ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()

    if despesa_id in PARECERES:
        return {
            "ok": True,
            "ja_existia": True,
            "chave_idempotencia": chave,
            "parecer": PARECERES[despesa_id]
        }

    PARECERES[despesa_id] = {
        "veredito": veredito,
        "justificativa": justificativa,
        "artigo": artigo,
        "chave_idempotencia": chave
    }

    return {
        "ok": True,
        "ja_existia": False,
        "chave_idempotencia": chave,
        "parecer": PARECERES[despesa_id]
    }


def detectar_laco(estado: Estado, acao: str) -> bool:
    ultimas = [
        item["acao"]
        for item in estado.historico[-3:]
        if "acao" in item
    ]

    return len(ultimas) == 3 and all(item == acao for item in ultimas)


def agente_com_estado(
    despesa_id: str,
    max_passos: int = 8,
    max_tokens: int = 2500,
    max_segundos: float = 30.0
) -> dict[str, Any]:
    dados = DESPESAS[despesa_id]

    estado = Estado(
        despesa_id=despesa_id,
        objetivo="Decidir a prestação de contas conforme a política.",
        dados=dados
    )

    orcamento = Orcamento(
        max_passos=max_passos,
        max_tokens=max_tokens,
        max_segundos=max_segundos
    )

    ferramentas = {
        "consultar_politica": lambda: consultar_politica(
            dados["categoria"]
        ),
        "consultar_historico": lambda: consultar_historico(
            dados["funcionario"]
        ),
        "registrar_parecer": lambda resultado: registrar_parecer(
            despesa_id,
            resultado["veredito"],
            resultado["justificativa"],
            resultado["artigo"]
        )
    }

    while estado.termino is None:
        limite = orcamento.verifica(
            estado.inicio,
            estado.passos
        )

        if limite:
            estado.termino = limite
            break

        contexto = {
            "despesa_id": despesa_id,
            "dados": estado.dados,
            "trajetoria": estado.historico[-6:],
            "observacoes": estado.observacoes
        }

        prompt = (
            PROMPT_AGENTE
            + "\n\nCONTEXTO ATUAL:\n"
            + json.dumps(
                contexto,
                ensure_ascii=False,
                indent=2
            )
        )

        decisao, tokens = chamada_estruturada(
            prompt,
            AGENTE_SCHEMA,
            "decisao_agente",
            temperatura=0,
            max_tokens=600
        )

        estado.passos += 1
        estado.tokens += tokens
        orcamento.usados_tokens += tokens

        acao = decisao["acao"]

        print(
            f"      passo={estado.passos} "
            f"acao={acao} "
            f"tokens={tokens}"
        )

        if detectar_laco(estado, acao):
            estado.termino = Termino.LACO
            break

        estado.historico.append(
            {
                "passo": estado.passos,
                "acao": acao
            }
        )

        if acao == "consultar_politica":
            resultado = ferramentas[acao]()
            estado.observacoes.append(
                {
                    "tool": acao,
                    "resultado": resultado
                }
            )
            continue

        if acao == "consultar_historico":
            resultado = ferramentas[acao]()
            estado.observacoes.append(
                {
                    "tool": acao,
                    "resultado": resultado
                }
            )
            continue

        if acao == "registrar_parecer":
            resultado = ferramentas[acao](decisao)
            estado.observacoes.append(
                {
                    "tool": acao,
                    "resultado": resultado
                }
            )
            continue

        if acao == "concluir":
            resultado = registrar_parecer(
                despesa_id,
                decisao["veredito"],
                decisao["justificativa"],
                decisao["artigo"]
            )

            estado.observacoes.append(
                {
                    "tool": "registrar_parecer",
                    "resultado": resultado
                }
            )

            estado.termino = Termino.CONCLUIDO
            continue

        estado.termino = Termino.ERRO

    return {
        "despesa_id": despesa_id,
        "termino": (
            estado.termino.value
            if estado.termino
            else "desconhecido"
        ),
        "passos": estado.passos,
        "tokens": estado.tokens,
        "parecer": PARECERES.get(despesa_id)
    }


def triagem_por_modelo(despesa_id: str) -> dict[str, Any]:
    d = DESPESAS[despesa_id]

    contexto = {
        "despesa_id": despesa_id,
        "despesa": d,
        "politica": POLITICA,
        "alçada_analista": ALCADA_ANALISTA
    }

    prompt = (
        PROMPT_ROUTER
        + "\n\nDADOS:\n"
        + json.dumps(
            contexto,
            ensure_ascii=False,
            indent=2
        )
    )

    resultado, tokens = chamada_estruturada(
        prompt,
        ROUTER_SCHEMA,
        "rota_despesa",
        temperatura=0,
        max_tokens=300
    )

    resultado["tokens"] = tokens
    return resultado


def orquestrar(
    analises: list[dict[str, Any]],
    max_subtarefas: int = 3
) -> tuple[dict[str, Any], int]:
    selecionadas = analises[:max_subtarefas]

    prompt = (
        PROMPT_ORQUESTRADOR
        + "\n\nANÁLISES:\n"
        + json.dumps(
            selecionadas,
            ensure_ascii=False,
            indent=2
        )
    )

    return chamada_estruturada(
        prompt,
        ORQUESTRADOR_SCHEMA,
        "parecer_lote",
        temperatura=0.2,
        max_tokens=700,
        modelo=MODELO_GRANDE
    )


def avaliar_e_otimizar(
    texto: str,
    max_rodadas: int = 3
) -> tuple[str, int, int]:
    atual = texto
    chamadas = 0
    aprovado_final = 0

    for rodada in range(1, max_rodadas + 1):
        prompt = (
            PROMPT_AVALIADOR
            + "\n\nTEXTO PARA AVALIAR:\n"
            + atual
        )

        avaliacao, _ = chamada_estruturada(
            prompt,
            AVALIADOR_SCHEMA,
            "avaliacao_parecer",
            temperatura=0,
            max_tokens=500
        )

        chamadas += 1

        criterios = avaliacao["criterios"]
        aprovado = (
            criterios["cita_artigo"]
            and criterios["cita_valor"]
            and criterios["conclui"]
        )

        if aprovado:
            aprovado_final = 1
            return atual, chamadas, aprovado_final

        if rodada == max_rodadas:
            return atual, chamadas, aprovado_final

        revisao_prompt = (
            "Revise o parecer abaixo para atender todos os critérios "
            "do avaliador. Preserve os fatos e valores. Retorne somente "
            "o texto final revisado.\n\n"
            "CRITÉRIOS:\n"
            + json.dumps(
                criterios,
                ensure_ascii=False,
                indent=2
            )
            + "\n\nPARECER:\n"
            + atual
        )

        revisado, _ = chamada_estruturada(
            revisao_prompt,
            REVISAO_SCHEMA,
            "parecer_revisado",
            temperatura=0.1,
            max_tokens=700,
            modelo=MODELO_GRANDE
        )

        atual = revisado["texto"]
        chamadas += 1

    return atual, chamadas, aprovado_final


def main() -> None:
    print("=" * 78)
    print("EXERCÍCIO 05 — ANALISTA DE PRESTAÇÃO DE CONTAS")
    print(f"modelo={MODELO}")
    print(f"base_url={BASE_URL}")
    print("=" * 78)

    print("\nCARIMBO")
    print(
        f"router v1 prompt=router-v1 "
        f"modelo={MODELO} temp=0"
    )
    print(
        f"agente v1 prompt=agente-v1 "
        f"modelo={MODELO} temp=0 "
        f"max_passos=8 max_tokens=2500 max_segundos=30"
    )
    print(
        f"orquestrador v1 prompt=orquestrador-v1 "
        f"modelo={MODELO_GRANDE} temp=0.2 "
        f"max_subtarefas=3"
    )
    print(
        f"avaliador v1 prompt=avaliador-v1 "
        f"modelo={MODELO_GRANDE} temp=0 "
        f"max_rodadas=3"
    )

    chamadas_modelo = 0
    resolvidos_regra = 0
    enviados_modelo = 0
    barrados = 0
    humanos = 0
    analises = []

    print("\nTRIAGEM")

    for despesa_id, despesa in DESPESAS.items():
        # PORTÃO PRIMEIRO: valida os fatos (funcionário existe, recibo bate)
        # ANTES de qualquer decisão automática. Se a regra rodasse antes, um
        # item com valor divergente do recibo poderia ser aprovado sem que o
        # portão chegasse a checá-lo (a saída de uma etapa é a entrada da
        # seguinte — é aqui que o sistema quebraria).
        motivo_portao = validar_portao(despesa_id)

        if motivo_portao:
            barrados += 1

            print(
                f"  {despesa_id} "
                f"rota=nenhuma [regra] "
                f"BARRADO — {motivo_portao['motivo']}"
            )
            continue

        resultado_regra = regra_deterministica(despesa_id)

        if resultado_regra:
            resolvidos_regra += 1

            registrar_parecer(
                despesa_id,
                resultado_regra["veredito"],
                resultado_regra["motivo"],
                resultado_regra["artigo"]
            )

            print(
                f"  {despesa_id} "
                f"rota=regra [regra] "
                f"{resultado_regra['veredito']}"
            )
            continue

        if despesa["valor"] > ALCADA_ANALISTA:
            humanos += 1

            artigo = POLITICA[
                despesa["categoria"]
            ]["artigo"]

            registrar_parecer(
                despesa_id,
                "revisao",
                (
                    f"Valor de R$ {despesa['valor']:.2f} "
                    f"acima da alçada do analista de "
                    f"R$ {ALCADA_ANALISTA:.2f}."
                ),
                artigo
            )

            print(
                f"  {despesa_id} "
                f"rota=humano [regra] "
                f"ACIMA DA ALÇADA"
            )
            continue

        rota = triagem_por_modelo(despesa_id)
        chamadas_modelo += 1

        print(
            f"  {despesa_id} "
            f"rota={rota['rota']} [modelo] "
            f"{rota['justificativa']}"
        )

        if rota["rota"] == "ambiguo":
            enviados_modelo += 1

            analise = agente_com_estado(despesa_id)

            chamadas_modelo += analise["passos"]
            analises.append(analise)

            continue

        if rota["rota"] == "humano":
            humanos += 1

            artigo = POLITICA[
                despesa["categoria"]
            ]["artigo"]

            registrar_parecer(
                despesa_id,
                "revisao",
                "Encaminhado para decisão humana.",
                artigo
            )

            continue

        if rota["rota"] == "regra":
            resultado = regra_deterministica(despesa_id)

            if resultado:
                resolvidos_regra += 1

                registrar_parecer(
                    despesa_id,
                    resultado["veredito"],
                    resultado["motivo"],
                    resultado["artigo"]
                )

            continue

        registrar_parecer(
            despesa_id,
            "revisao",
            "Rota nenhuma: não existe decisão automática segura.",
            "N/A"
        )

    print("\nPORTÃO (auditoria — reconferência dos fatos)")

    for despesa_id in DESPESAS:
        motivo = validar_portao(despesa_id)

        if motivo:
            print(
                f"  {despesa_id} "
                f"BARRADO — {motivo['motivo']}"
            )

    if analises:
        print("\nAGENTE (itens ambíguos)")

        for analise in analises:
            print(
                f"  {analise['despesa_id']} "
                f"termino={analise['termino']} "
                f"passos={analise['passos']} "
                f"tokens={analise['tokens']}"
            )

    print("\nORQUESTRADOR-TRABALHADOR")

    if analises:
        parecer_lote, tokens = orquestrar(
            analises,
            max_subtarefas=3
        )

        chamadas_modelo += 1

        print(
            f"  chamadas=1 tokens={tokens}"
        )
        print(parecer_lote["parecer_lote"])

        print("\nAVALIADOR-OTIMIZADOR")

        parecer_final, chamadas_avaliador, aprovado = (
            avaliar_e_otimizar(
                parecer_lote["parecer_lote"],
                max_rodadas=3
            )
        )

        chamadas_modelo += chamadas_avaliador

        print(
            f"  chamadas={chamadas_avaliador} "
            f"aprovado={bool(aprovado)}"
        )
        print(parecer_final)

    else:
        print(
            "  nenhum item ambíguo para consolidar"
        )

    print("\nCONTA")
    print(f"  itens ................. {len(DESPESAS)}")
    print(
        f"  resolvidos por REGRA .. "
        f"{resolvidos_regra} (zero chamadas de LLM)"
    )
    print(
        f"  enviados ao MODELO .... "
        f"{enviados_modelo}"
    )
    print(
        f"  chamadas totais ....... "
        f"{chamadas_modelo}"
    )
    print(
        f"  se TUDO fosse ao modelo: "
        f"~{len(DESPESAS) * 4} chamadas "
        f"(estimativa: ~4 chamadas por item — router + agente)"
    )
    print(f"  barrados ............... {barrados}")
    print(f"  humanos ................ {humanos}")
    print(
        f"  pareceres registrados .. "
        f"{len(PARECERES)}"
    )


if __name__ == "__main__":
    main()

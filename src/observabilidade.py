"""
Traces do sistema, nas convenções semânticas GenAI do OpenTelemetry.

Três tipos de span:
  invoke_agent santo-desapego   um por execução do grafo (um turno ou uma
                                retomada depois de uma decisão humana); é a raiz
  chat <modelo>                 uma por chamada ao modelo, com os tokens
  execute_tool <ferramenta>     uma por ferramenta executada, com argumentos
                                e resultado

Na raiz ficam os atributos próprios do case: versão do sistema, motivo de
término, entrada, saída, versões dos prompts, trechos recuperados e, quando
houve, a decisão humana (quem, quando e o que foi decidido). É esse registro
que permite reconstruir uma decisão depois (docs/model-card.md).

Os spans são gravados em JSONL, um por linha, no arquivo configurado em
config.TRACES_PATH (ou no que `usar_arquivo` definir). Para ler:

    python scripts/ver_traces.py
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, Status, StatusCode

from . import config

PROVEDOR = "gcp.gemini"
NOME_SISTEMA = "santo-desapego"


class ExportadorJsonl(SpanExporter):
    """Grava cada span terminado como uma linha JSON."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._trava = threading.Lock()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        linhas = []
        for s in spans:
            ctx, pai = s.get_span_context(), s.parent
            linhas.append(json.dumps({
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
                "parent_id": format(pai.span_id, "016x") if pai else None,
                "nome": s.name,
                "inicio": s.start_time, "fim": s.end_time,
                "duracao_ms": round((s.end_time - s.start_time) / 1e6, 1),
                "status": s.status.status_code.name,
                "atributos": dict(s.attributes or {}),
                "eventos": [{"nome": e.name, "atributos": dict(e.attributes or {})} for e in s.events],
                "versao_sistema": s.resource.attributes.get("service.version"),
            }, ensure_ascii=False, default=str))
        with self._trava:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with self.caminho.open("a", encoding="utf-8") as f:
                f.write("\n".join(linhas) + "\n")
        return SpanExportResult.SUCCESS


_exportador = ExportadorJsonl(config.TRACES_PATH)
_provedor = TracerProvider(resource=Resource.create({
    "service.name": NOME_SISTEMA, "service.version": config.VERSAO_SISTEMA}))
_provedor.add_span_processor(SimpleSpanProcessor(_exportador))
_tracer = _provedor.get_tracer("santo_desapego", config.VERSAO_SISTEMA)

# A raiz da execução em andamento. Os ramos paralelos do LangGraph rodam em
# outras threads, onde o contexto do OpenTelemetry não chega; por isso os
# spans filhos são sempre pendurados nesta raiz de forma explícita.
_raiz: trace.Span | None = None


def usar_arquivo(caminho: Path) -> None:
    """Troca o arquivo de destino (a suíte de avaliação grava um por rodada)."""
    _exportador.caminho = Path(caminho)


def texto_json(valor: Any, limite: int = 4000) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    return texto[:limite]


def _contexto():
    return trace.set_span_in_context(_raiz) if _raiz is not None else None


@contextmanager
def execucao(thread_id: str, atributos: dict[str, Any]) -> Iterator[trace.Span]:
    """Abre a raiz `invoke_agent` de uma execução do grafo."""
    global _raiz
    with _tracer.start_as_current_span(f"invoke_agent {NOME_SISTEMA}", kind=SpanKind.INTERNAL) as span:
        span.set_attributes({
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": NOME_SISTEMA,
            "gen_ai.provider.name": PROVEDOR,
            "gen_ai.conversation.id": thread_id,
            "gen_ai.request.model": config.MODELO,
            "santo.versao_sistema": config.VERSAO_SISTEMA,
        })
        span.set_attributes({k: v if isinstance(v, (str, bool, int, float)) else texto_json(v)
                             for k, v in atributos.items() if v is not None})
        _raiz = span
        try:
            yield span
        finally:
            _raiz = None


def fechar_execucao(span: trace.Span, saida: Any, estado: dict[str, Any] | None,
                    prompts: dict[str, str]) -> None:
    """Grava na raiz a saída, o motivo de término e o que sustentou a decisão."""
    estado = estado or {}
    trechos = [t["id"] for t in (estado.get("trechos_rag") or [])]
    trechos += [t["id"] for t in (estado.get("regras_consultadas") or []) if t.get("id")]
    span.set_attributes({
        "santo.termino": saida.termino,
        "santo.motivo_termino": saida.motivo_termino[:500],
        "santo.agente": saida.agente,
        "santo.saida.tipo": saida.tipo,
        "santo.saida.resultado": saida.resultado[:2000],
        "santo.saida.base_suficiente": saida.suficiencia.base_suficiente,
        "santo.saida.fontes": texto_json([f.ref for f in saida.fontes]),
        "santo.prompts": texto_json(prompts),
        "santo.rota": estado.get("rota") or "",
        "santo.desfecho": estado.get("desfecho") or "",
        "santo.rag.trechos": texto_json(sorted(set(trechos))),
        "santo.passos": int(estado.get("passos") or 0),
        "santo.custo_usd": float(estado.get("custo_usd") or 0.0),
    })
    if saida.termino == "erro_fatal":
        span.set_status(Status(StatusCode.ERROR, saida.motivo_termino[:200]))
        span.set_attribute("error.type", saida.motivo_termino.split(":")[0][:100])


@contextmanager
def chat(modelo: str, etapa: str | None, prompt: str | None, temperatura: float,
         max_tokens: int) -> Iterator[trace.Span]:
    with _tracer.start_as_current_span(f"chat {modelo}", context=_contexto(), kind=SpanKind.CLIENT) as span:
        span.set_attributes({
            "gen_ai.operation.name": "chat", "gen_ai.provider.name": PROVEDOR,
            "gen_ai.request.model": modelo, "gen_ai.request.temperature": temperatura,
            "gen_ai.request.max_tokens": max_tokens,
            "santo.etapa": etapa or "", "santo.prompt": prompt or "",
        })
        yield span


def uso_chat(span: trace.Span, modelo_resposta: str | None, entrada: int, saida: int,
             tentativas: int, custo_usd: float) -> None:
    span.set_attributes({
        "gen_ai.response.model": modelo_resposta or "",
        "gen_ai.usage.input_tokens": entrada, "gen_ai.usage.output_tokens": saida,
        "santo.tentativas": tentativas, "santo.custo_usd": custo_usd,
    })


def erro(span: trace.Span, tipo: str, mensagem: str) -> None:
    span.set_status(Status(StatusCode.ERROR, mensagem[:200]))
    span.set_attribute("error.type", tipo)


@contextmanager
def embeddings(modelo: str, n: int) -> Iterator[trace.Span]:
    with _tracer.start_as_current_span(f"embeddings {modelo}", context=_contexto(),
                                       kind=SpanKind.CLIENT) as span:
        span.set_attributes({"gen_ai.operation.name": "embeddings", "gen_ai.provider.name": PROVEDOR,
                             "gen_ai.request.model": modelo, "santo.textos": n})
        yield span


@contextmanager
def ferramenta(nome: str, argumentos: dict[str, Any]) -> Iterator[Any]:
    """Abre `execute_tool <nome>`. Devolve uma função para registrar o resultado:
    um resultado com a chave "erro" marca o span como erro (erro de ferramenta
    volta como dado, mas conta na taxa de erro por ferramenta)."""
    with _tracer.start_as_current_span(f"execute_tool {nome}", context=_contexto(),
                                       kind=SpanKind.INTERNAL) as span:
        span.set_attributes({"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": nome,
                             "gen_ai.tool.type": "function",
                             "gen_ai.tool.call.arguments": texto_json(argumentos)})

        def registrar(resultado: Any) -> None:
            span.set_attribute("gen_ai.tool.call.result", texto_json(resultado))
            if isinstance(resultado, dict) and (resultado.get("erro") or resultado.get("ok") is False):
                erro(span, str(resultado.get("erro") or "falhou"), texto_json(resultado, 200))

        try:
            yield registrar
        except Exception as e:
            erro(span, type(e).__name__, str(e))
            raise


def evento_raiz(nome: str, atributos: dict[str, Any]) -> None:
    """Acrescenta um evento na raiz (ex.: um controle de segurança que bloqueou algo)."""
    if _raiz is not None:
        _raiz.add_event(nome, {k: v if isinstance(v, (str, bool, int, float)) else texto_json(v)
                               for k, v in atributos.items() if v is not None})

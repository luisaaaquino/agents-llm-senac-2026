"""
Cliente do modelo: chamada estruturada (Pydantic), espaçamento para o limite
do plano gratuito, e a classificação de erro recuperável × fatal (§6.5 —
o framework não faz essa classificação por nós).

Também é aqui que os prompts são carregados de arquivo (src/prompts/) e que
cada carregamento entra no carimbo da execução (§2.2: cada execução registra,
no início, a combinação de prompts em uso).
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import TypeVar

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from . import config

T = TypeVar("T", bound=BaseModel)

_client = OpenAI(
    base_url=config.BASE_URL,
    api_key=config.API_KEY or "sem-chave",
    timeout=config.LLM_TIMEOUT_S,
    max_retries=config.LLM_MAX_RETRIES_SDK,
)


class ErroLLMFatal(Exception):
    """Não adianta repetir: chave inválida, requisição malformada, modelo inexistente."""


class ErroLLMRecuperavelEsgotado(Exception):
    """Era recuperável (limite, sobrecarga, timeout), mas as tentativas acabaram."""


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tentativas: int = 1
    segundos: float = 0.0
    modelo: str = ""

    @property
    def total(self) -> int:
        return self.tokens_entrada + self.tokens_saida

    @property
    def custo_usd(self) -> float:
        return (self.tokens_entrada * config.PRECO_USD_ENTRADA
                + self.tokens_saida * config.PRECO_USD_SAIDA)


# --- Prompts em arquivo -----------------------------------------------------
_PROMPTS_EM_USO: dict[str, str] = {}


def carregar_prompt(nome: str) -> str:
    """Lê src/prompts/<nome> e registra nome + hash no carimbo da execução."""
    texto = (config.PROMPTS_DIR / nome).read_text(encoding="utf-8")
    # O changelog e a ficha técnica ficam no arquivo para o histórico, mas
    # não vão para o modelo: tudo depois da primeira linha "---" isolada.
    corpo = texto.split("\n---\n", 1)[0].strip()
    _PROMPTS_EM_USO[nome] = hashlib.sha256(corpo.encode("utf-8")).hexdigest()[:12]
    return corpo


def prompts_em_uso() -> dict[str, str]:
    return dict(sorted(_PROMPTS_EM_USO.items()))


# --- Espaçamento entre chamadas (limite por minuto do plano gratuito) ------
_trava = threading.Lock()
_ultima_chamada = 0.0


def _aguardar_vez() -> None:
    global _ultima_chamada
    with _trava:
        espera = config.LLM_MIN_INTERVALO_S - (time.monotonic() - _ultima_chamada)
        if espera > 0:
            time.sleep(espera)
        _ultima_chamada = time.monotonic()


def _classificar(erro: Exception) -> str:
    if isinstance(erro, (openai.RateLimitError, openai.APITimeoutError,
                         openai.APIConnectionError, openai.InternalServerError)):
        return "recuperavel"
    if isinstance(erro, openai.APIStatusError):
        return "recuperavel" if erro.status_code in (429, 500, 502, 503, 504) else "fatal"
    if isinstance(erro, (ValidationError, ValueError)):
        # saída que não respeitou o schema: vale uma nova tentativa
        return "recuperavel"
    return "fatal"


def chamada_estruturada(sistema: str, usuario: str, schema: type[T], *,
                        modelo: str | None = None, max_tokens: int = 800) -> tuple[T, Uso]:
    """
    Uma chamada ao modelo com saída validada por Pydantic.

    `usuario` é obrigatório: o Gemini recusa requisição só com mensagem de
    sistema ("contents is not specified") — achado ao migrar da Parte 1.
    """
    modelo = modelo or config.MODELO
    uso = Uso(modelo=modelo)
    inicio = time.monotonic()
    ultimo_erro: Exception | None = None

    for tentativa in range(1, config.LLM_RETRIES_RECUPERAVEIS + 2):
        uso.tentativas = tentativa
        _aguardar_vez()
        try:
            resposta = _client.beta.chat.completions.parse(
                model=modelo,
                temperature=config.TEMPERATURA,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": sistema},
                          {"role": "user", "content": usuario}],
                response_format=schema,
            )
            if resposta.usage:
                uso.tokens_entrada += resposta.usage.prompt_tokens or 0
                uso.tokens_saida += resposta.usage.completion_tokens or 0
            objeto = resposta.choices[0].message.parsed
            if objeto is None:
                raise ValueError("resposta sem objeto estruturado")
            uso.segundos = time.monotonic() - inicio
            return objeto, uso
        except Exception as erro:  # noqa: BLE001 — classificado logo abaixo
            ultimo_erro = erro
            if _classificar(erro) == "fatal":
                raise ErroLLMFatal(f"{type(erro).__name__}: {erro}") from erro
            time.sleep(min(2 ** tentativa, 20))

    raise ErroLLMRecuperavelEsgotado(f"{type(ultimo_erro).__name__}: {ultimo_erro}")


def embeddings(textos: list[str]) -> list[list[float]]:
    """Embeddings em lote, com as mesmas regras de repetição."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, config.LLM_RETRIES_RECUPERAVEIS + 2):
        _aguardar_vez()
        try:
            r = _client.embeddings.create(model=config.MODELO_EMBEDDING, input=textos,
                                          dimensions=config.EMBEDDING_DIMENSOES)
            return [d.embedding for d in r.data]
        except Exception as erro:  # noqa: BLE001
            ultimo_erro = erro
            if _classificar(erro) == "fatal":
                raise ErroLLMFatal(f"{type(erro).__name__}: {erro}") from erro
            time.sleep(min(2 ** tentativa, 20))
    raise ErroLLMRecuperavelEsgotado(f"{type(ultimo_erro).__name__}: {ultimo_erro}")

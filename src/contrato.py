"""
O contrato do sistema com quem o usa (§1).

Entrada: TEXTO livre, mais o que acompanha o texto sem ser digitado por
ninguém (quem é o usuário, qual a sessão) — é disso que sai o thread_id.

Saída: um objeto validado, com os três campos obrigatórios do §1.2:
  - resultado   -> `resultado` (texto ao usuário) + `dados` (o anúncio, os itens)
  - fonte       -> `fontes` (trecho do corpus, registro do banco, ferramenta)
  - suficiência -> `suficiencia` (teve base? se não, o que faltou)
A recusa é parte do contrato: `suficiencia.base_suficiente = False`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Agente = Literal["anuncio", "compra", "duvida", "nenhum"]

TipoSaida = Literal[
    "pergunta",               # o sistema precisa de mais informação do usuário
    "aguardando_aprovacao",   # o grafo parou: o vendedor confirma a publicação
    "aguardando_moderacao",   # o grafo parou: o moderador decide sobre a avaria
    "anuncio_publicado",
    "anuncio_nao_publicado",  # rejeitado pelo vendedor/moderação, ou prazo vencido
    "sugestao",               # Agente A: itens do catálogo
    "resposta",               # dúvida sobre as regras, respondida com fonte
    "recusa",                 # fora do escopo, ou sem base para responder
    "erro",
]

Termino = Literal[
    "aguardando_usuario",  # o turno acabou com uma pergunta — a conversa continua
    "aguardando_humano",   # interrupt: aprovação ou moderação pendente
    "respondeu",           # o objetivo da conversa foi cumprido
    "recusou",             # fora do escopo / sem base no corpus
    "rejeitado",           # a pessoa (vendedor ou moderador) rejeitou a ação
    "expirou",             # o prazo do humano venceu sem resposta
    "orcamento",           # estourou passos, tokens, tempo ou dinheiro
    "laco",                # detector de laço disparou
    "erro_fatal",          # não há como continuar
]


class Entrada(BaseModel):
    """O que chega ao sistema. Só `texto` é digitado pela pessoa."""
    texto: str = Field(min_length=1, description="o que a pessoa digitou, literal")
    usuario_id: str = Field(description="id do usuário logado (ex.: V-017) — vem da sessão do site")
    sessao_id: str = Field(description="id da conversa aberta (uma aba de chat) — vem do site")

    @property
    def thread_id(self) -> str:
        # usuário + sessão: a mesma pessoa com duas abas abertas tem duas
        # conversas independentes (docs/memoria.md §5.5).
        return f"{self.usuario_id}:{self.sessao_id}"


class Fonte(BaseModel):
    tipo: Literal["corpus", "banco", "ferramenta", "memoria", "conversa", "humano"]
    ref: str = Field(description="id conferível: trecho do corpus, id do registro, nome da ferramenta")
    trecho: str | None = Field(default=None, description="o conteúdo que sustenta o resultado")


class Suficiencia(BaseModel):
    base_suficiente: bool
    motivo: str
    faltando: list[str] = Field(default_factory=list)


class SaidaSistema(BaseModel):
    thread_id: str
    agente: Agente
    tipo: TipoSaida
    resultado: str = Field(description="o que a pessoa lê")
    dados: dict[str, Any] | None = Field(default=None, description="anúncio, itens, pendência…")
    fontes: list[Fonte] = Field(default_factory=list)
    suficiencia: Suficiencia
    escolha_declarada: str | None = Field(
        default=None, description="quando a entrada era ambígua e o sistema escolheu uma leitura")
    termino: Termino
    motivo_termino: str

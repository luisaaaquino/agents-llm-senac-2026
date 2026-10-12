"""
Contratos de saída de cada etapa em que o MODELO é chamado (§2.1, coluna
"contrato de saída"). O schema garante que a resposta seja uma das opções
válidas; ele NÃO garante que seja a opção certa (§6.3) — por isso cada
etapa tem, além do schema, uma conferência em código em src/nos_*.py.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .db import BAIRROS, CATEGORIAS, ESTADOS_CONSERVACAO

Categoria = Literal.__getitem__(tuple(CATEGORIAS))
Bairro = Literal.__getitem__(tuple(BAIRROS))
EstadoConservacao = Literal.__getitem__(tuple(ESTADOS_CONSERVACAO))
Rota = Literal["vender", "comprar", "duvida", "ambigua", "fora_escopo"]


class Triagem(BaseModel):
    rota: Rota
    leituras: list[Literal["vender", "comprar", "duvida"]] = Field(default_factory=list)
    categoria: Categoria | None = None
    motivo: str


class Rascunho(BaseModel):
    titulo: str
    categoria: Categoria
    descricao: str
    preco: float
    bairro: Bairro
    estado_conservacao: EstadoConservacao
    avarias_declaradas: list[str] = Field(default_factory=list)


class DecisaoAnuncio(BaseModel):
    motivo: str = Field(description="uma frase: por que esta ação agora")
    acao: Literal["perguntar", "consultar_preco", "consultar_regras",
                  "preencher_rascunho", "registrar_indicio", "recusar_item"]
    pergunta: str | None = None
    categoria: Categoria | None = None
    bairro: Bairro | None = None
    consulta: str | None = None
    rascunho: Rascunho | None = None
    indicio: str | None = None
    regra_citada: str | None = None


class Avaliacao(BaseModel):
    tem_titulo: bool
    tem_categoria: bool
    tem_descricao: bool
    estado_coerente: bool
    sem_invencao: bool
    aprovado: bool
    faltando: list[str] = Field(default_factory=list)


class RespostaRegras(BaseModel):
    resposta: str
    citacoes: list[str] = Field(default_factory=list)
    base_suficiente: bool


class PedidoCompra(BaseModel):
    intencao: str | None = None
    categorias: list[Categoria] = Field(default_factory=list)
    orcamento_total: float | None = None
    preco_max_item: float | None = None
    bairro: Bairro | None = None
    faltando: list[Literal["o_que_procura"]] = Field(default_factory=list)
    ambiguidade: str | None = None
    escolha: str | None = None


class Sugestao(BaseModel):
    itens_ids: list[int] = Field(default_factory=list)
    justificativa: str
    categorias_de_fora: list[str] = Field(default_factory=list)


class ResumoEpisodio(BaseModel):
    resumo: str

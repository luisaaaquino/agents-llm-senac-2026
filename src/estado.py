"""
O estado que atravessa o grafo (§7).

Na Aula 05 a regra era "a lista de mensagens não é o estado". Aqui ela vira
declaração de tipo: `mensagens` guarda só o texto da conversa; decisão,
contador e identificador são campos próprios, cada um com quem escreve
documentado em docs/arquitetura.md §7.1.

Reducers (§7.2) — todo campo que mais de um nó escreve, ou que dois ramos
paralelos escrevem no mesmo super-passo, tem reducer:
  - `mensagens`, `trajetoria`: concatenação (operator.add)
  - `passos`, `tokens`, `custo_usd`: soma — cada nó devolve o seu incremento;
    sem a soma, o último nó a terminar apagaria a contagem dos outros
  - `candidatos`: concatenação — é o campo que os ramos paralelos do Agente A
    escrevem ao mesmo tempo (Send); a demonstração do que acontece SEM ele
    está em scripts/demo_sem_reducer.py
  - `escritas`: merge de dicionário — o id de cada escrita feita, para a
    retomada não reaplicar efeito colateral
Campos sem reducer têm UM nó dono (ver a tabela em docs/arquitetura.md).
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def juntar_dict(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any]:
    return {**(a or {}), **(b or {})}


def substituir_ou_limpar(a: list | None, b: list | None) -> list:
    """Para `candidatos`: lista vazia vinda de quem inicia o turno LIMPA o
    campo; qualquer outra lista é concatenada (os ramos paralelos)."""
    if b == []:
        return []
    return (a or []) + (b or [])


class Estado(TypedDict, total=False):
    # --- identidade (escrito só por `entrada`) ---
    thread_id: str
    usuario_id: str
    sessao_id: str

    # --- conversa ---
    mensagens: Annotated[list[dict[str, str]], operator.add]   # {"quem", "texto"}
    texto_turno: str             # a fala deste turno (entrada)

    # --- roteamento (escrito só por `triagem`) ---
    rota: str | None             # vender | comprar | duvida | ambigua | fora_escopo
    leituras: list[str] | None   # as rotas possíveis, quando ambígua
    categoria_mencionada: str | None
    escolha_declarada: str | None
    # qual agente espera a resposta do usuário no próximo turno (escrito pelos
    # nós que perguntam; limpo pelos que encerram). None = próxima fala vai à triagem.
    conversa_aberta: str | None
    msg_inicio: int              # índice em `mensagens` onde a conversa do agente começou
    passos_inicio: int           # `passos` acumulado quando o agente começou (orçamento por anúncio)

    # --- Agente B ---
    decisao_b: dict[str, Any] | None        # última decisão do modelo (agente_b)
    faixa_preco: dict[str, Any] | None      # resultado de consultar_preco
    regras_consultadas: list[dict[str, Any]] | None
    indicio: dict[str, Any] | None          # o indício registrado (só registrar_indicio escreve)
    pergunta_portao: str | None             # pergunta que o portão em código impôs
    rascunho: dict[str, Any] | None
    avaliacao: dict[str, Any] | None
    rodadas_avaliador: int
    pendencia: dict[str, Any] | None        # o que o humano está decidindo (interrupt)
    decisao_humana: dict[str, Any] | None
    desfecho: str | None                    # publicado | moderacao_* | rejeitado | expirou | orcamento | laco …
    # O que a conversa diz sobre avaria (perguntada? respondida? mencionada?)
    # NÃO é campo: é recalculado das mensagens a cada volta (`avaria_da_conversa`
    # em src/nos_anuncio.py) — guardar criaria uma segunda fonte de verdade.

    # --- Agente A ---
    pedido: dict[str, Any] | None
    candidatos: Annotated[list[dict[str, Any]], substituir_ou_limpar]
    sugestao: dict[str, Any] | None

    # --- RAG e memória ---
    trechos_rag: list[dict[str, Any]] | None
    rag_portao: dict[str, Any] | None       # {"melhor", "limiar", "suficiente"}
    consultas_rag: Annotated[int, operator.add]
    memoria: dict[str, Any] | None          # o que foi recuperado para esta conversa

    # --- controle (orçamento, laço, término) ---
    passos: Annotated[int, operator.add]
    tokens: Annotated[int, operator.add]
    custo_usd: Annotated[float, operator.add]
    inicio_turno: float
    trajetoria: Annotated[list[dict[str, Any]], operator.add]
    escritas: Annotated[dict[str, Any], juntar_dict]
    # `fontes` NÃO é campo: é derivada na hora de montar a saída, a partir
    # de faixa_preco, trechos_rag, escritas e decisao_humana (§7.3).
    termino: str | None
    motivo_termino: str | None
    saida: dict[str, Any] | None

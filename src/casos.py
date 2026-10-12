"""
Os casos demonstrados (§9) e os exemplos do contrato (§1.3, §1.4).

Cada caso é um roteiro: a primeira fala, uma fila de respostas da pessoa
(usada na ordem, a cada pergunta do sistema — se acabar, a pessoa diz que
não tem mais nada) e o que a pessoa faz quando o grafo para esperando ela.
As falas são mock; o resto — perguntas, ferramentas, decisões — é execução.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Caso:
    nome: str
    usuario_id: str
    primeira_fala: str
    respostas: list[str] = field(default_factory=list)
    # o que a pessoa responde em cada pausa, na ordem (aprovação, moderação…)
    decisoes: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    prova: str = ""             # o que o caso prova
    esperado: str = ""          # término/desfecho esperado, escrito ANTES de rodar
    repetir_decisao: bool = False   # caso 6: a aprovação chega duas vezes
    vencer_prazo: bool = False      # a pausa fica sem resposta e o prazo vence


FALA_ESGOTADA = "não tenho mais nada pra acrescentar, pode seguir"

CASOS: dict[str, Caso] = {c.nome: c for c in [
    # --- os seis do §9 -----------------------------------------------------------
    Caso("01_simples", "V-017",
         "quero vender minha geladeira consul duplex, uns 350 reais, bairro Santo Amaro",
         ["5 anos de uso, funciona bem, sem defeito",
          "capacidade de uns 400 litros, duplex mesmo. pode publicar"],
         decisoes=[("V-017", {"acao": "aprovar"})],
         prova="o caminho feliz existe", esperado="anuncio_publicado / respondeu"),
    Caso("02_divergencia_preco", "V-018",
         "vendo geladeira duplex por 900 reais, Santo Amaro",
         ["5 anos de uso, funciona bem, sem defeito",
          "sei que é caro mas quero esse valor, pode manter 900"],
         decisoes=[("V-018", {"acao": "aprovar"})],
         prova="o sistema diz uma coisa (faixa R$ 300–380), o vendedor diz outra (R$ 900): "
               "o sistema avisa, respeita a alçada, e não confunde preço com avaria",
         esperado="anuncio_publicado a R$ 900 / respondeu, sem indício"),
    Caso("03_sem_registro", "V-019",
         "quero anunciar uma bicicleta, uns 500 reais, Santo Amaro",
         ["aro 29, seminova, sem defeito nenhum", "pode publicar"],
         decisoes=[("V-019", {"acao": "aprovar"})],
         prova="erro de ferramenta (sem_comparaveis) que o agente contorna",
         esperado="anuncio_publicado / respondeu, uma única consulta de preço"),
    Caso("04_avaria_negada", "V-021",
         "vendo geladeira consul, 380 reais, Santo Amaro",
         ["ah, o freezer embaixo demora pra congelar, mas prefiro não pôr isso no anúncio",
          "não, não quero declarar isso"],
         decisoes=[("M-001", {"acao": "publicar_com_aviso",
                              "aviso": "freezer inferior com congelamento lento"})],
         prova="o sistema sabe NÃO agir: não publica escondendo o defeito; para e espera a moderação",
         esperado="aguardando_moderacao (não publicado) -> decisão do moderador"),
    Caso("05_fora_do_corpus", "C-002",
         "posso vender ingresso de show pelo site?",
         prova="a pergunta não está no corpus: recusa, e recusa dizendo algo útil",
         esperado="recusa / recusou"),
    Caso("06_aprovacao_editando", "V-022",
         "quero vender um sofá 3 lugares veludo verde, uns 300 reais, Santo Amaro",
         ["tem um pé com uma rachadura pequena, mas fora isso tá ótimo, pode colocar isso na descrição",
          "pode seguir"],
         decisoes=[("V-022", {"acao": "editar", "campos": {"preco": 280}})],
         repetir_decisao=True,
         prova="o grafo pausa, o vendedor aprova EDITANDO o preço, e a segunda aprovação não duplica",
         esperado="anuncio_publicado a R$ 280 / respondeu; 2ª aprovação sem efeito"),

    # --- exemplos do contrato (§1.3 e §1.4) e medições --------------------------
    Caso("07_compra_cozinha", "C-001",
         "to montando a cozinha do meu ap no brooklin, queria gastar no maximo uns 700 no total",
         prova="caminho feliz do Agente A: busca paralela por categoria, soma conferida",
         esperado="sugestao / respondeu, soma <= 700, nenhum item do próprio C-001"),
    Caso("08_incompleta", "C-003", "oi, quero comprar umas coisas",
         ["uma mesa pra cozinha, até 150, moro no jardim cordeiro"],
         prova="entrada incompleta: pergunta o que falta e depois atende",
         esperado="pergunta -> sugestao"),
    Caso("09_ambigua", "V-023", "quero vender minha geladeira velha e comprar uma maior",
         prova="entrada ambígua: pergunta por onde começar em vez de chutar",
         esperado="pergunta / aguardando_usuario"),
    Caso("10_fora_escopo", "C-004", "me ajuda a fazer a lição de matemática do meu filho?",
         prova="fora do escopo: recusa e diz o que o sistema faz", esperado="recusa / recusou"),
    Caso("11_duvida_excecao", "C-005", "a taxa de 5% é cobrada em cima do frete tambem?",
         prova="dúvida cuja resposta depende de uma exceção do corpus, com citação",
         esperado="resposta / respondeu, citando termos-de-uso-2026#5"),
    Caso("12_moderacao_sem_resposta", "V-024",
         "vendo fogão 4 bocas, 250 reais, Santo Amaro",
         ["uma das bocas não acende, mas não quero colocar isso", "não vou declarar"],
         vencer_prazo=True,
         prova="ninguém da moderação responde: o prazo de 48 h vence e o anúncio não é publicado",
         esperado="aguardando_moderacao -> expirou"),
    Caso("13_memoria_avaria_tipica", "V-025",
         "vendo geladeira electrolux, 320 reais, Santo Amaro",
         ["funciona sim, nenhum problema", "pode publicar"],
         decisoes=[("V-025", {"acao": "aprovar"})],
         prova="depois do caso 4, a memória de categoria muda a pergunta do portão: pergunta "
               "pelo freezer pelo nome", esperado="anuncio_publicado; pergunta cita o freezer"),
    Caso("14_item_proibido", "V-026",
         "quero vender uma réplica de pistola de airsoft, 200 reais, Santo Amaro",
         ["é de metal, bem realista"],
         prova="o agente decide CONSULTAR a regra (RAG como ferramenta) e recusa citando-a",
         esperado="recusa / recusou, citando politica-moderacao-2026#1"),
    Caso("15_excecao_brinquedo", "V-027",
         "vendo uma arminha de brinquedo do meu filho, de plástico colorido, 30 reais, Santo Amaro",
         ["não atira nada, é só de apertar e fazer barulho. sem defeito", "pode publicar"],
         decisoes=[("V-027", {"acao": "aprovar"})],
         prova="a regra tem exceção: consultar antes de recusar evita recusar o que é permitido",
         esperado="anuncio_publicado / respondeu, depois de consultar politica-moderacao-2026#2"),
]}

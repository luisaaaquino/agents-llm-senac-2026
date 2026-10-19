"""
Configuração do sistema: caminhos, modelo, limites e prazos.

Parâmetros que a biblioteca já teria com um valor padrão (recursion_limit,
timeout, número de tentativas) ficam declarados aqui de forma explícita,
para o comportamento não mudar se esse padrão mudar numa atualização.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Caminhos ---------------------------------------------------------------
DADOS_DIR = ROOT / "dados"
CORPUS_DIR = DADOS_DIR / "corpus"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
LOGS_DIR = ROOT / "logs"
DB_PATH = DADOS_DIR / "santo_desapego.db"          # negócio (catálogo, anúncios…)
MEMORIA_DB_PATH = DADOS_DIR / "memoria.db"           # memória de longo prazo
INDICE_DB_PATH = DADOS_DIR / "indice_rag.db"         # índice vetorial do corpus
CHECKPOINT_DB_PATH = DADOS_DIR / "checkpoints.db"    # checkpointer do LangGraph
SEED_PATH = DADOS_DIR / "seed.sql"

# --- Modelo -------------------------------------------------------------------
# Provedor compatível com a API da OpenAI (aqui, o Gemini).
# Variável vazia no .env é tratada como ausente.
BASE_URL = os.environ.get("LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
API_KEY = os.environ.get("OPENAI_API_KEY") or ""
MODELO = os.environ.get("LLM_MODELO") or "gemini-3.5-flash-lite"
# O avaliador pode usar um modelo diferente do que escreve o rascunho.
# Se ficar vazio, usa o mesmo.
MODELO_AVALIADOR = os.environ.get("LLM_MODELO_AVALIADOR") or MODELO
MODELO_EMBEDDING = os.environ.get("LLM_MODELO_EMBEDDING") or "gemini-embedding-001"
TEMPERATURA = 0.0

# --- Parâmetros que a biblioteca teria como padrão -------------------------
# O recursion_limit padrão do LangGraph 1.2 é 10007. Usamos 60 só como
# rede de segurança: quem para o agente antes é o detector de laço e o
# limite de passos.
RECURSION_LIMIT = 60
# O SDK da OpenAI espera até 600 s por resposta, mais que o limite de 120 s
# por turno, então o timeout é definido aqui.
LLM_TIMEOUT_S = 30.0
LLM_MAX_RETRIES_SDK = 0      # as novas tentativas são feitas em llm.py,
LLM_RETRIES_RECUPERAVEIS = 3 # separando erro recuperável de fatal
# O plano gratuito do Gemini limita as chamadas por minuto, então elas são espaçadas.
LLM_MIN_INTERVALO_S = float(os.environ.get("LLM_MIN_INTERVALO_S") or "4.0")
EMBEDDING_DIMENSOES = 768    # o padrão do gemini-embedding-001 é 3072
RAG_K = 3                    # trechos por consulta: com k=1 a exceção
                             # do frete (Q04) fica de fora; com k=3, 13 de 13
RAG_LIMIAR = 0.67            # abaixo disso, não há base para responder
                             # (pior pergunta respondível: 0,698; melhor fora do corpus: 0,642)
MEMORIA_EPISODICA_K = 2

# --- Limites por agente --------------------------------------------------
# Agente B (anúncio).
B_MAX_PASSOS = 12            # decisões do modelo por anúncio (somando turnos)
B_MAX_TOKENS = 60_000
B_MAX_SEGUNDOS_TURNO = 120.0
B_MAX_RODADAS_AVALIADOR = 3
# Agente A (compra) é um workflow sem laço: faz no máximo 2 chamadas de
# modelo por turno, então não tem limite próprio de tokens ou de tempo.
A_MAX_CATEGORIAS = 4         # ramos paralelos de busca no catálogo
# Detector de laço: a mesma ação com os mesmos argumentos N vezes seguidas.
LACO_REPETICOES = 3
# Limite de custo. No plano gratuito o custo é zero; os preços abaixo são
# os da tabela paga do gemini-3.5-flash-lite, para o limite valer se o
# plano mudar.
PRECO_USD_ENTRADA = 0.30 / 1_000_000
PRECO_USD_SAIDA = 2.50 / 1_000_000
B_MAX_CUSTO_USD = 0.02

# --- Prazos dos pontos de parada humanos ----------------------------------
PRAZO_APROVACAO_VENDEDOR_H = 24   # vendedor confirma a publicação
PRAZO_MODERACAO_H = 48            # moderador decide sobre o indício de avaria

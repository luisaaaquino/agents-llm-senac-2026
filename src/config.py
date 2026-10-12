"""
Configuração do sistema — tetos, modelo e os parâmetros que o framework
esconderia atrás de um valor padrão.

Regra desta entrega (§6.6): toda decisão de projeto que a biblioteca
transformou em parâmetro com default é declarada AQUI, mesmo quando o valor
coincide com o padrão. Se o padrão mudar numa atualização, o comportamento
do sistema não muda junto.
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
# Provedor compatível com a API da OpenAI. Nesta entrega: Gemini (plano
# gratuito do Google AI Studio) — ver docs/modelos.md §4 para a troca.
# Variável vazia no .env conta como ausente (o .env.example vem sem valores).
BASE_URL = os.environ.get("LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
API_KEY = os.environ.get("OPENAI_API_KEY") or ""
MODELO = os.environ.get("LLM_MODELO") or "gemini-3.5-flash-lite"
# Plano B do docs/case.md §2.11: o avaliador pode usar outro modelo, para não
# compartilhar o ponto cego de quem escreveu. Vazio = mesmo modelo.
MODELO_AVALIADOR = os.environ.get("LLM_MODELO_AVALIADOR") or MODELO
MODELO_EMBEDDING = os.environ.get("LLM_MODELO_EMBEDDING") or "gemini-embedding-001"
TEMPERATURA = 0.0

# --- Parâmetros que o framework esconderia (§6.6) ---------------------------
# LangGraph 1.2: o recursion_limit padrão é 10007 (era 25 nas versões 0.x).
# Um agente preso em laço gastaria 10 mil super-passos antes de parar. O teto
# real é o nosso detector de laço + MAX_PASSOS; este é a rede de segurança.
RECURSION_LIMIT = 60
# SDK OpenAI 1.51: max_retries=2 e timeout de leitura de 600 s por padrão.
# 600 s estoura sozinho o teto de 120 s por turno — por isso o timeout é nosso.
LLM_TIMEOUT_S = 30.0
LLM_MAX_RETRIES_SDK = 0      # as repetições são feitas por nós (llm.py), com
LLM_RETRIES_RECUPERAVEIS = 3 # classificação recuperável × fatal
# Plano gratuito do Gemini tem limite por minuto: espaçamos as chamadas.
LLM_MIN_INTERVALO_S = float(os.environ.get("LLM_MIN_INTERVALO_S") or "4.0")
EMBEDDING_DIMENSOES = 768    # o default do gemini-embedding-001 é 3072
RAG_K = 3                    # trechos por consulta (docs/rag.md §4.3): com k=1 a
                             # exceção do frete (Q04) cai fora; com k=3, 13/13
RAG_LIMIAR = 0.67            # portão de suficiência, medido em 12/10/2026: pior
                             # pergunta respondível 0,698 × melhor fora do corpus 0,642
MEMORIA_EPISODICA_K = 2

# --- Tetos por agente (docs/arquitetura.md, quadro de tetos) ----------------
# Agente B (anúncio) — conversa de investigação, padrão da Aula 05.
B_MAX_PASSOS = 12            # decisões do modelo por anúncio (somando turnos)
B_MAX_TOKENS = 60_000
B_MAX_SEGUNDOS_TURNO = 120.0
B_MAX_RODADAS_AVALIADOR = 3
# Agente A (compra) — virou WORKFLOW (sem laço): o teto de passos é estrutural,
# no máximo 2 chamadas de modelo por turno (interpretar + montar). Os tetos de
# tokens/tempo da Parte 1 (20 mil / 20 s) saíram: nada no grafo os consumiria.
A_MAX_CATEGORIAS = 4         # ramos paralelos de busca no catálogo
# Detector de laço: a mesma ação com os mesmos argumentos N vezes seguidas.
LACO_REPETICOES = 3
# Teto de dinheiro: o plano gratuito custa US$ 0. Os preços abaixo são os da
# tabela PAGA do gemini-3.5-flash-lite (ai.google.dev/gemini-api/docs/pricing,
# consultado em 12/10/2026) — o teto passa a valer se trocarem de plano.
PRECO_USD_ENTRADA = 0.30 / 1_000_000
PRECO_USD_SAIDA = 2.50 / 1_000_000
B_MAX_CUSTO_USD = 0.02

# --- Human-in-the-loop: prazos (docs/humano.md §8.4) -------------------------
PRAZO_APROVACAO_VENDEDOR_H = 24   # vendedor confirma a publicação
PRAZO_MODERACAO_H = 48            # moderador decide sobre o indício de avaria

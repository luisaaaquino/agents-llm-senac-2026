-- Dados simulados do Santo Desapego (Agente B — Assistente de anúncio).
-- Tudo mock. Nenhum dado real de pessoa (ver §2.9 do case).
-- A dificuldade do problema é preservada nomeando os casos difíceis (§2.8):
--   * DIVERGÊNCIA   : preço-desejo do vendedor fora da faixa de mercado.
--   * SEM REGISTRO  : categoria/bairro sem comparáveis -> erro de ferramenta.
--   * NÃO-DISPARO   : conversa que NÃO deve publicar (avaria negada -> moderação).

CREATE TABLE precos_comparaveis (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    bairro    TEXT NOT NULL,
    preco     REAL NOT NULL
);

CREATE TABLE anuncios (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo           TEXT NOT NULL,
    categoria        TEXT NOT NULL,
    descricao        TEXT NOT NULL,
    preco            REAL NOT NULL,
    bairro           TEXT NOT NULL,
    estado_declarado INTEGER NOT NULL DEFAULT 0,
    estado           TEXT NOT NULL DEFAULT 'ativo'   -- ativo | pausado | vendido
);

CREATE TABLE indicios_moderacao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    anuncio_ref TEXT NOT NULL,
    indicio     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pendente'     -- pendente | revisado
);

-- Comparáveis: geladeira duplex em Santo Amaro sai entre R$ 300 e R$ 380.
INSERT INTO precos_comparaveis (categoria, bairro, preco) VALUES
    ('geladeira', 'Santo Amaro', 300.0),
    ('geladeira', 'Santo Amaro', 340.0),
    ('geladeira', 'Santo Amaro', 360.0),
    ('geladeira', 'Santo Amaro', 380.0),
    ('sofá',      'Santo Amaro', 250.0),
    ('sofá',      'Santo Amaro', 420.0),
    ('mesa',      'Santo Amaro', 120.0),
    ('mesa',      'Santo Amaro', 190.0);
-- Obs.: NÃO há comparáveis para ('bicicleta','Santo Amaro') de propósito:
-- é o caso SEM REGISTRO que o agente tem de contornar.

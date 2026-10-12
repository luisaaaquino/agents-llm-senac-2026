-- Dados simulados do Santo Desapego — Parte 2 (Agentes A e B).
-- Tudo mock. Nenhum dado real de pessoa (ver §2.9 do case).
--
-- Casos difíceis preservados por construção (§2.8 do case):
--   * DIVERGÊNCIA   : geladeira sai R$ 300–380 em Santo Amaro (caso do R$ 900).
--   * SEM REGISTRO  : NÃO há comparáveis de bicicleta — de propósito.
--   * NÃO-DISPARO   : (conversa) avaria negada -> moderação, não publica.
--   * ESTOQUE VOLÁTIL (Agente A): itens "vendido"/"pausado" no catálogo que
--     NÃO podem ser sugeridos; itens do próprio comprador C-001 também não.

-- Bairros atendidos (mesma lista e coordenadas do site do TCC,
-- santo-desapego-api/utils/geolocalizacao.js — centroide aproximado).
CREATE TABLE bairros (
    nome TEXT PRIMARY KEY,
    lat  REAL NOT NULL,
    lng  REAL NOT NULL
);
INSERT INTO bairros (nome, lat, lng) VALUES
    ('Santo Amaro',           -23.6574, -46.7062),
    ('Campo Belo',            -23.6189, -46.6823),
    ('Brooklin',              -23.6270, -46.6883),
    ('Granja Julieta',        -23.6608, -46.7120),
    ('Jardim Marajoara',      -23.6534, -46.6816),
    ('Vila Cruzeiro',         -23.6480, -46.7010),
    ('Vila Mascote',          -23.6472, -46.6669),
    ('Vila Sofia',            -23.6580, -46.6920),
    ('Alto da Boa Vista',     -23.6413, -46.6992),
    ('Campo Grande',          -23.6620, -46.6870),
    ('Chácara Flora',         -23.6468, -46.6854),
    ('Chácara Monte Alegre',  -23.6444, -46.6770),
    ('Chácara Santo Antônio', -23.6298, -46.7039),
    ('Interlagos',            -23.6532, -46.6799),
    ('Jardim Cordeiro',       -23.6366, -46.6776),
    ('Jardim Petrópolis',     -23.6317, -46.6839),
    ('Jardim Santo Amaro',    -23.6522, -46.6960),
    ('Socorro',               -23.6633, -46.7110);

-- Preços de itens semelhantes vendidos recentemente (o "mercado local").
CREATE TABLE precos_comparaveis (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    bairro    TEXT NOT NULL,
    preco     REAL NOT NULL
);
INSERT INTO precos_comparaveis (categoria, bairro, preco) VALUES
    ('geladeira',   'Santo Amaro', 300.0),
    ('geladeira',   'Santo Amaro', 340.0),
    ('geladeira',   'Santo Amaro', 360.0),
    ('geladeira',   'Santo Amaro', 380.0),
    ('sofá',        'Santo Amaro', 250.0),
    ('sofá',        'Santo Amaro', 420.0),
    ('mesa',        'Santo Amaro', 120.0),
    ('mesa',        'Santo Amaro', 190.0),
    ('micro-ondas', 'Santo Amaro', 120.0),
    ('micro-ondas', 'Santo Amaro', 160.0),
    ('fogão',       'Santo Amaro', 200.0),
    ('fogão',       'Santo Amaro', 280.0),
    ('geladeira',   'Campo Grande', 280.0),
    ('geladeira',   'Campo Grande', 350.0);
-- Obs.: NÃO há comparáveis de ('bicicleta', *) de propósito: é o caso
-- SEM REGISTRO que o Agente B tem de contornar.

-- Anúncios: o catálogo que o Agente A consulta e onde o Agente B publica.
CREATE TABLE anuncios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    vendedor_id         TEXT NOT NULL,
    titulo              TEXT NOT NULL,
    categoria           TEXT NOT NULL,
    descricao           TEXT NOT NULL,
    preco               REAL NOT NULL,
    bairro              TEXT NOT NULL,
    estado_conservacao  TEXT NOT NULL DEFAULT 'bom_estado', -- novo | como_novo | bom_estado | marcas_de_uso
    estado_declarado    INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'ativo',      -- ativo | pausado | vendido | aguardando_moderacao | rejeitado
    chave_idempotencia  TEXT UNIQUE,                        -- derivada do conteúdo (§5.3, §8.5)
    thread_id           TEXT,                               -- conversa que originou (NULL no seed)
    criado_em           TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO anuncios (vendedor_id, titulo, categoria, descricao, preco, bairro, estado_conservacao, estado_declarado, status) VALUES
    ('V-101', 'Geladeira Brastemp Frost Free 375L', 'geladeira',   'Funciona perfeitamente, 4 anos de uso, sem avarias.',      340.0, 'Brooklin',          'bom_estado',    1, 'ativo'),
    ('V-102', 'Geladeira Consul 1 porta 260L',      'geladeira',   'Pequena, ideal para kitnet. Borracha da porta trocada.',   220.0, 'Campo Belo',        'marcas_de_uso', 1, 'ativo'),
    ('V-103', 'Geladeira Electrolux Duplex 400L',   'geladeira',   'Ótimo estado.',                                            390.0, 'Santo Amaro',       'bom_estado',    1, 'vendido'),
    ('V-104', 'Micro-ondas Panasonic 21L',          'micro-ondas', 'Prato giratório novo, painel funcionando.',                130.0, 'Brooklin',          'bom_estado',    1, 'ativo'),
    ('V-105', 'Micro-ondas Electrolux 31L',         'micro-ondas', 'Usado, com marcas na porta.',                              150.0, 'Vila Cruzeiro',     'marcas_de_uso', 1, 'ativo'),
    ('V-106', 'Fogão 4 bocas Dako',                 'fogão',       'Acendimento automático em 3 das 4 bocas.',                 180.0, 'Jardim Petrópolis', 'marcas_de_uso', 1, 'ativo'),
    ('V-107', 'Fogão Atlas 5 bocas inox',           'fogão',       'Seminovo, 1 ano de uso.',                                  420.0, 'Campo Belo',        'como_novo',     1, 'ativo'),
    ('V-108', 'Mesa de jantar 4 lugares madeira',   'mesa',        'Tampo com pequenos riscos.',                               180.0, 'Brooklin',          'marcas_de_uso', 1, 'ativo'),
    ('V-109', 'Mesa dobrável para cozinha',         'mesa',        'Ótima para espaços pequenos.',                              90.0, 'Jardim Cordeiro',   'bom_estado',    1, 'ativo'),
    ('V-110', 'Jogo de 4 cadeiras estofadas',       'cadeira',     'Estofado limpo, uma cadeira com pé reparado.',             160.0, 'Campo Belo',        'marcas_de_uso', 1, 'ativo'),
    ('V-111', 'Armário de cozinha 6 portas',        'armário',     'Branco, sem portas soltas.',                               250.0, 'Socorro',           'bom_estado',    1, 'ativo'),
    ('V-112', 'Sofá 3 lugares retrátil cinza',      'sofá',        'Tecido suede, sem rasgos.',                                450.0, 'Santo Amaro',       'bom_estado',    1, 'ativo'),
    ('V-113', 'Sofá 2 lugares',                     'sofá',        'Pausado pelo vendedor.',                                   200.0, 'Brooklin',          'marcas_de_uso', 1, 'pausado'),
    ('C-001', 'Micro-ondas Consul 20L',             'micro-ondas', 'Anúncio do próprio comprador C-001 — não pode ser sugerido a ele.', 110.0, 'Brooklin', 'bom_estado', 1, 'ativo'),
    ('V-114', 'Bicicleta aro 29 alumínio',          'bicicleta',   'Câmbio Shimano 21 marchas.',                               650.0, 'Interlagos',        'bom_estado',    1, 'ativo'),
    ('V-115', 'Cama box casal com colchão',         'cama',        'Colchão com 2 anos de uso.',                               380.0, 'Granja Julieta',    'bom_estado',    1, 'ativo');

-- Indícios de avaria não declarada -> fila da moderação (RF20).
CREATE TABLE indicios_moderacao (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    chave_idempotencia TEXT UNIQUE NOT NULL,             -- derivada do conteúdo
    vendedor_id        TEXT NOT NULL,
    thread_id          TEXT NOT NULL,
    anuncio_id         INTEGER REFERENCES anuncios(id),
    indicio            TEXT NOT NULL,
    fala_literal       TEXT,                             -- a evidência, como o vendedor disse
    status             TEXT NOT NULL DEFAULT 'pendente', -- pendente | confirmado | descartado | expirado
    decidido_por       TEXT,
    criado_em          TEXT NOT NULL DEFAULT (datetime('now')),
    decidido_em        TEXT
);

-- Pontos de parada abertos (o grafo está em `interrupt` esperando uma pessoa).
-- É daqui que a rotina de prazos tira quem venceu (docs/humano.md §8.4).
CREATE TABLE pendencias_humanas (
    thread_id   TEXT PRIMARY KEY,
    tipo        TEXT NOT NULL,                 -- aprovacao_vendedor | moderacao
    perfil      TEXT NOT NULL,                 -- quem pode responder: vendedor | moderador
    responsavel TEXT,                          -- o vendedor dono da conversa (aprovação)
    criada_em   TEXT NOT NULL DEFAULT (datetime('now')),
    expira_em   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'aberta' -- aberta | resolvida | expirada
);

-- Cliques do comprador (sinal auxiliar do Agente A — não é a entrada).
CREATE TABLE cliques (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    anuncio_id  INTEGER NOT NULL REFERENCES anuncios(id),
    clicado_em  TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO cliques (usuario_id, anuncio_id) VALUES
    ('C-001', 1), ('C-001', 4), ('C-001', 8);

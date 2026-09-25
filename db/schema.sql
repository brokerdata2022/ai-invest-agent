-- Базова схема БД для Фази 0.
-- Дотримується правила з CLAUDE.md: сирі дані ніколи не видаляються
-- і не перезаписуються (append-only), тому raw_observations має
-- унікальність по (source, metric_id, observed_at, revision), а не
-- просто (source, metric_id, observed_at).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Метадані джерел даних (список наростає з кожним новим адаптером,
-- див. .claude/skills/add-data-source).
CREATE TABLE IF NOT EXISTS sources (
    name        TEXT PRIMARY KEY,
    category    TEXT NOT NULL,        -- macro | companies | quotes | crypto | forex | commodities | news
    source_type TEXT NOT NULL,        -- official_primary | aggregator | unofficial
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Сирі зібрані значення показників. Append-only: новий факт або нова
-- ревізія старого факту — це завжди INSERT, ніколи UPDATE/DELETE.
CREATE TABLE IF NOT EXISTS raw_observations (
    id           BIGSERIAL,
    source       TEXT NOT NULL REFERENCES sources(name),
    metric_id    TEXT NOT NULL,       -- внутрішній стабільний id показника (не той, що в API джерела)
    value        NUMERIC NOT NULL,
    observed_at  DATE NOT NULL,       -- до якого періоду відноситься значення
    fetched_at   TIMESTAMPTZ NOT NULL,-- коли ми фактично його забрали
    revision     INTEGER NOT NULL DEFAULT 1,
    raw_payload  JSONB,               -- необроблена відповідь джерела для цього запису (аудит)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, observed_at),
    UNIQUE (source, metric_id, observed_at, revision)
);

-- TimescaleDB hypertable по observed_at (до якого періоду відноситься
-- значення), а не по fetched_at. Причина: TimescaleDB вимагає, щоб
-- будь-який унікальний індекс на hypertable (у т.ч. PRIMARY KEY і наш
-- UNIQUE) обов'язково включав колонку партиціювання. observed_at і так
-- частина бізнес-ключа (source, metric_id, observed_at, revision) —
-- тож підходить природно, без штучного розширення унікального
-- обмеження зайвою колонкою. (Партиціювання по fetched_at виглядало
-- логічним на перший погляд, але ламало створення hypertable — див.
-- docs/decisions.md.)
SELECT create_hypertable(
    'raw_observations', 'observed_at',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_raw_observations_lookup
    ON raw_observations (source, metric_id, observed_at DESC, revision DESC);

-- Лог релізів — заготовка під Фазу 3 (monitoring), щоб схема БД не
-- мінялась, коли дійдемо до моніторингу календаря.
CREATE TABLE IF NOT EXISTS release_log (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL REFERENCES sources(name),
    metric_id     TEXT NOT NULL,
    scheduled_at  TIMESTAMPTZ,
    detected_at   TIMESTAMPTZ,
    impact_level  TEXT,               -- high | medium | low
    status        TEXT NOT NULL DEFAULT 'pending', -- pending | detected | processed
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Сирі новини (окремо від raw_observations — там value NUMERIC,
-- новина текстова, туди не лягає, докладніше docs/decisions.md
-- 2026-09-25 "news/ — обсяг, межа шарів і схема БД"). Дедуп по
-- (source, external_id), append-only (без UPDATE/DELETE, rule 6).
-- НЕ hypertable: тут немає revision/DISTINCT ON-патерну, що
-- виправдовував partitioning для raw_observations.
CREATE TABLE IF NOT EXISTS raw_news (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL REFERENCES sources(name),
    external_id  TEXT NOT NULL,       -- дедуп-ключ джерела (URL/guid)
    stream       TEXT NOT NULL,       -- watchlist | general | geopolitical
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,-- коли статтю опубліковано (аналог observed_at)
    fetched_at   TIMESTAMPTZ NOT NULL,-- коли ми її фактично забрали
    raw_payload  JSONB,               -- необроблена відповідь джерела для цього запису (аудит)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_news_stream_published
    ON raw_news (stream, published_at DESC);

-- Лог кожного LLM-виклику (rule 5 з CLAUDE.md: промпт + відповідь +
-- timestamp + джерело — обов'язково для аудиту постфактум).
CREATE TABLE IF NOT EXISTS llm_call_log (
    id          BIGSERIAL PRIMARY KEY,
    provider    TEXT NOT NULL,        -- deepseek | anthropic
    purpose     TEXT NOT NULL,        -- напр. news_relevance_filter
    prompt      TEXT NOT NULL,
    response    TEXT NOT NULL,
    source_ref  TEXT,                 -- напр. id/URL статті, на яку був виклик
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Структурований висновок LLM-аналізу однієї новини (формат полів —
-- analysis/CLAUDE.md "Формат виходу LLM-аналізу"). asset_id — NULL
-- для geopolitical/general новин, що не стосуються конкретного активу.
CREATE TABLE IF NOT EXISTS news_analysis (
    id           BIGSERIAL PRIMARY KEY,
    raw_news_id  BIGINT NOT NULL REFERENCES raw_news(id),
    asset_id     TEXT,
    is_relevant  BOOLEAN NOT NULL,
    summary      TEXT,
    direction    TEXT,                -- up | down | neutral | unclear
    confidence   NUMERIC,
    reasoning    TEXT,
    llm_call_id  BIGINT REFERENCES llm_call_log(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Зареєстровані джерела.
INSERT INTO sources (name, category, source_type, notes) VALUES
    ('fred', 'macro', 'official_primary', 'Federal Reserve Economic Data (US)'),
    ('ecb', 'macro', 'official_primary', 'ECB Data Portal (колишній SDW), єврозона'),
    ('boj', 'macro', 'official_primary', 'Bank of Japan Time-Series Data Search API, Японія'),
    ('estat', 'macro', 'official_primary', 'e-Stat (政府統計の総合窓口) API v3.0, Японія'),
    ('twelvedata', 'quotes', 'aggregator', 'Twelve Data — щоденні ціна/обсяг акцій, безкоштовна реєстрація без капчі (Stooq відкинуто через бот-захист, Alpaca — гео-блок; docs/decisions.md 2026-09-20)'),
    ('sec_edgar', 'companies', 'official_primary', 'SEC EDGAR XBRL (companyconcept) — фундаментальні факти компаній, без ключа, обов''язковий User-Agent'),
    ('gdelt', 'news', 'aggregator', 'GDELT DOC 2.0 API — глобальний агрегатор новин, query-фільтр на рівні запиту (watchlist/general/geopolitical потоки), без ключа'),
    ('fed_rss', 'news', 'official_primary', 'Federal Reserve — офіційний RSS усіх прес-релізів, без ключа'),
    ('ecb_rss', 'news', 'official_primary', 'ECB — офіційний RSS прес-релізів/промов/прес-конференцій, без ключа')
ON CONFLICT (name) DO NOTHING;

-- Views для читабельного перегляду. raw_observations лишається
-- append-only джерелом істини (жодних UPDATE/DELETE) — views тільки
-- читають і не змінюють дані, це суто зручність перегляду, не заміна
-- окремих таблиць (docs/decisions.md, 2026-09-21).

-- Часовий ряд одного показника без "шуму" старих ревізій — для
-- кожної (source, metric_id, observed_at) лишається тільки запис з
-- найвищим revision (останнє відоме значення на цю дату).
CREATE OR REPLACE VIEW v_observations_latest_revision AS
SELECT DISTINCT ON (source, metric_id, observed_at)
    source, metric_id, value, observed_at, fetched_at, revision
FROM raw_observations
ORDER BY source, metric_id, observed_at, revision DESC;

-- Поточне значення кожного показника одним рядком (найсвіжіша дата,
-- найвища ревізія на неї) — "що зараз", а не весь часовий ряд.
-- Приклад: SELECT * FROM v_current_values WHERE metric_id LIKE 'aapl%';
CREATE OR REPLACE VIEW v_current_values AS
SELECT DISTINCT ON (source, metric_id)
    source, metric_id, value, observed_at, fetched_at, revision
FROM raw_observations
ORDER BY source, metric_id, observed_at DESC, revision DESC;

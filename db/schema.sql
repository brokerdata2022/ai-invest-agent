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
    category    TEXT NOT NULL,        -- macro | companies | crypto | forex | commodities | news
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

-- Зареєстровані джерела.
INSERT INTO sources (name, category, source_type, notes) VALUES
    ('fred', 'macro', 'official_primary', 'Federal Reserve Economic Data (US)'),
    ('ecb', 'macro', 'official_primary', 'ECB Data Portal (колишній SDW), єврозона')
ON CONFLICT (name) DO NOTHING;

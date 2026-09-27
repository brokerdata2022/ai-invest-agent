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

-- Додано 2026-09-26 (monitoring/economic_calendar.py): очікуване
-- ринком значення показника (форекс-календар дає "forecast" разом з
-- датою/часом релізу) — TEXT, бо джерело віддає мішані одиниці
-- ("0.6%", "-258B", "615K"), парсинг у число — робота analysis/, не
-- цього шару (rule 1, CLAUDE.md). ALTER, не тільки CREATE — таблиця
-- вже існувала й мала дані до цієї зміни, ALTER TABLE ADD COLUMN
-- IF NOT EXISTS — ідемпотентно, безпечно перезастосовувати
-- (apply_schema.py docstring).
ALTER TABLE release_log ADD COLUMN IF NOT EXISTS expected_value TEXT;

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

-- Синтез "новини + ціна" по активу за вікно (analysis/news_analysis/
-- synthesize.py, docs/news-purpose.md "Ціль 1" — точки входу для
-- watchlist-пар: чи рух ціни пояснюється новинами, чи це шум/корекція).
-- Лише активи, для яких є ОБИДВА входи (новинний сигнал + ціна) — тому
-- price_* NOT NULL, на відміну від news_analysis.asset_id, який буває
-- NULL.
-- source_refs — список summaries новин, на які спирався висновок
-- (analysis/CLAUDE.md "Формат виходу LLM-аналізу"); AssetSignal не несе
-- URL на цьому рівні агрегації, summaries — найближчий доступний бекінг.
-- Один результат на актив НА ДЕНЬ (idx нижче + ON CONFLICT UPDATE у
-- save_synthesis(), не чистий append-only): повторний прогін того
-- самого дня (ручний тест, ретрай після збою) оновлює вже наявний
-- рядок замість дублювання — живо виявлено 2026-09-27, ручні тестові
-- прогони синтезу того самого активу того самого дня плодили по 3-5
-- рядків без жодної нової інформації.
CREATE TABLE IF NOT EXISTS news_synthesis (
    id                 BIGSERIAL PRIMARY KEY,
    asset_id           TEXT NOT NULL,
    window_days        INTEGER NOT NULL,
    cluster_count      INTEGER NOT NULL,
    net_lean           INTEGER NOT NULL,
    price_pct_change   NUMERIC NOT NULL,
    price_start_date   DATE NOT NULL,
    price_end_date     DATE NOT NULL,
    summary            TEXT NOT NULL,
    direction          TEXT NOT NULL,     -- up | down | neutral | unclear
    confidence         NUMERIC NOT NULL,
    reasoning          TEXT NOT NULL,
    source_refs        JSONB NOT NULL,
    llm_call_id        BIGINT REFERENCES llm_call_log(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_news_synthesis_asset_per_day
    ON news_synthesis (asset_id, ((created_at AT TIME ZONE 'UTC')::date));

-- Синтез глобального контексту (analysis/news_analysis/synthesize_market.py,
-- docs/news-purpose.md "Ціль 4" — risk-on/risk-off стан ринку) —
-- geopolitical/general новини не прив'язані до активу (asset_id завжди
-- NULL), тому окрема від news_synthesis форма: без asset_id/price_*,
-- замість них macro_context (знімок ключових ставок/дохідностей на
-- момент синтезу, для аудиту) і source_refs зі списком урахованих
-- кластерів (title+source_count, не окремих статей).
-- Один результат НА ДЕНЬ (idx нижче + ON CONFLICT UPDATE у
-- save_market_synthesis()) — той самий принцип, що news_synthesis вище.
CREATE TABLE IF NOT EXISTS market_synthesis (
    id             BIGSERIAL PRIMARY KEY,
    window_days    INTEGER NOT NULL,
    cluster_count  INTEGER NOT NULL,
    macro_context  JSONB NOT NULL,
    summary        TEXT NOT NULL,
    direction      TEXT NOT NULL,     -- up (risk-on) | down (risk-off) | neutral | unclear
    confidence     NUMERIC NOT NULL,
    reasoning      TEXT NOT NULL,
    source_refs    JSONB NOT NULL,
    llm_call_id    BIGINT REFERENCES llm_call_log(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_synthesis_per_day
    ON market_synthesis (((created_at AT TIME ZONE 'UTC')::date));

-- Кандидати-новачки, знайдені LLM у general-потоці новин
-- (analysis/news_analysis/discover_candidates.py, docs/news-purpose.md
-- "Ціль 3") — активи, яких ще немає в S&P 500 universe. Журнал
-- відкриттів (append-only МІЖ днями); "поточний список" (10
-- найновіших унікальних тикерів) — DISTINCT ON (ticker) ORDER BY
-- discovered_at DESC. Кожен рядок тут ВЖЕ пройшов верифікацію
-- торгованості через Twelve Data (verify_tradable()) — LLM лише
-- пропонує, підтвердження факту, що тикер реальний і ліквідний,
-- завжди детерміноване, не на слово LLM.
-- Один рядок на тикер НА ДЕНЬ (idx нижче + ON CONFLICT UPDATE у
-- save_candidate()) — той самий принцип, що news_synthesis/
-- market_synthesis вище: повторне виявлення того самого тикера того
-- самого дня оновлює рядок, не дублює.
CREATE TABLE IF NOT EXISTS candidate_assets (
    id             BIGSERIAL PRIMARY KEY,
    ticker         TEXT NOT NULL,
    company_name   TEXT NOT NULL,
    reasoning      TEXT NOT NULL,
    source_refs    JSONB NOT NULL,
    llm_call_id    BIGINT REFERENCES llm_call_log(id),
    discovered_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_assets_ticker_per_day
    ON candidate_assets (ticker, ((discovered_at AT TIME ZONE 'UTC')::date));

-- Зареєстровані джерела.
INSERT INTO sources (name, category, source_type, notes) VALUES
    ('fred', 'macro', 'official_primary', 'Federal Reserve Economic Data (US)'),
    ('ecb', 'macro', 'official_primary', 'ECB Data Portal (колишній SDW), єврозона'),
    ('boj', 'macro', 'official_primary', 'Bank of Japan Time-Series Data Search API, Японія'),
    ('estat', 'macro', 'official_primary', 'e-Stat (政府統計の総合窓口) API v3.0, Японія'),
    ('twelvedata', 'quotes', 'aggregator', 'Twelve Data — щоденні ціна/обсяг акцій, безкоштовна реєстрація без капчі (Stooq відкинуто через бот-захист, Alpaca — гео-блок; docs/decisions.md 2026-09-20)'),
    ('sec_edgar', 'companies', 'official_primary', 'SEC EDGAR XBRL (companyconcept) — фундаментальні факти компаній, без ключа, обов''язковий User-Agent'),
    ('gdelt', 'news', 'aggregator', 'GDELT DOC 2.0 API — глобальний агрегатор новин, query-фільтр на рівні запиту (watchlist/general потоки — geopolitical перенесено на широкі RSS-фіди, docs/decisions.md 2026-09-27), без ключа'),
    ('fed_rss', 'news', 'official_primary', 'Federal Reserve — офіційний RSS усіх прес-релізів, без ключа'),
    ('ecb_rss', 'news', 'official_primary', 'ECB — офіційний RSS прес-релізів/промов/прес-конференцій, без ключа'),
    ('boj_rss', 'news', 'official_primary', 'Bank of Japan — офіційний RSS новин (whatsnew), без ключа'),
    ('bbc_rss', 'news', 'aggregator', 'BBC News — головний RSS (усі категорії, не звужений), без ключа'),
    ('aljazeera_rss', 'news', 'aggregator', 'Al Jazeera — RSS "all" (усі категорії), без ключа'),
    ('guardian_rss', 'news', 'aggregator', 'The Guardian — RSS World, без ключа'),
    ('npr_rss', 'news', 'aggregator', 'NPR — головний RSS (Top Stories), без ключа'),
    ('skynews_rss', 'news', 'aggregator', 'Sky News — RSS World, без ключа'),
    ('dw_rss', 'news', 'aggregator', 'Deutsche Welle — RSS "all" (англомовний), без ключа'),
    ('binance', 'crypto', 'official_primary', 'Binance public API — щоденні OHLCV-свічки (klines) BTC/ETH/SOL проти USDT, без ключа'),
    ('coingecko', 'crypto', 'aggregator', 'CoinGecko — щоденний market cap BTC/ETH/SOL (агрегатор по біржах), без ключа')
ON CONFLICT (name) DO NOTHING;

-- Порівняння факту з ринковим очікуванням для одного циклу релізу
-- (release_log.status: detected -> processed, analysis/expectations/).
-- Append-only, по одному рядку на release_log_id — той самий реліз
-- не порівнюється двічі. actual_value/expected_value_parsed завжди в
-- ОДНАКОВИХ одиницях (comparison_method визначає, як вони приведені
-- до спільного вигляду — деталі docs/decisions.md), expected_value_raw
-- лишає оригінальний текст ForexFactory для аудиту.
CREATE TABLE IF NOT EXISTS expectation_comparisons (
    id                     BIGSERIAL PRIMARY KEY,
    release_log_id         BIGINT NOT NULL UNIQUE REFERENCES release_log(id),
    source                 TEXT NOT NULL,
    metric_id              TEXT NOT NULL,
    observed_at            DATE NOT NULL,
    actual_value           NUMERIC NOT NULL,
    expected_value_raw     TEXT NOT NULL,
    expected_value_parsed  NUMERIC NOT NULL,
    surprise               NUMERIC NOT NULL,
    surprise_pct           NUMERIC,
    comparison_method      TEXT NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Результати кожного прогону composite_score.py (analysis/screening/) —
-- раніше тільки друкувались, ніде не зберігались (docs/status.md), тому
-- ніщо не знало "які тикери зараз пройшли скринінг" (потрібне
-- analysis/news_analysis/run_news_analysis.py для tracked_assets акцій,
-- docs/news-purpose.md "Ціль 2"). Append-only, як решта проєкту — усі
-- рядки ОДНОГО прогону мають той самий run_at, "поточний" скринінг =
-- MAX(run_at). Порожній прогін (ніхто не пройшов) нічого не вставляє —
-- свідомо: не затирати вчорашній валідний список нульовим/збійним прогоном.
CREATE TABLE IF NOT EXISTS screening_results (
    id                 BIGSERIAL PRIMARY KEY,
    ticker             TEXT NOT NULL,
    score              NUMERIC NOT NULL,
    revenue_growth     NUMERIC,
    eps_growth         NUMERIC,
    pe                 NUMERIC,
    avg_dollar_volume  NUMERIC,
    run_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_screening_results_run_at ON screening_results (run_at);

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

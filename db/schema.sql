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
    ('coingecko', 'crypto', 'aggregator', 'CoinGecko — щоденний market cap BTC/ETH/SOL (агрегатор по біржах), без ключа'),
    ('binance_futures', 'crypto', 'official_primary', 'Binance USDⓈ-M Futures public API — bulk-знімок ринку (обсяг/funding rate) для крипто-скринінгу лонг/шорт/спостереження, без ключа (docs/decisions.md 2026-09-27)'),
    ('bybit_futures', 'crypto', 'official_primary', 'Bybit v5 public API (linear perpetual) — bulk-знімок ринку (обсяг/funding rate/Open Interest, усе в одному запиті), без ключа'),
    ('okx_futures', 'crypto', 'official_primary', 'OKX v5 public API (SWAP) — bulk-знімок ринку (обсяг/Open Interest), без ключа')
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

-- Додано 2026-09-27: NULL = ще не надіслано в Telegram.
-- expectations_notify.py проставляє тут now() одразу після успішної
-- відправки — без цього notify_expectations (розклад — кожні 15 хв)
-- повторно надсилав би ті самі "останні 5" рядків щоцикл, поки не
-- набіжить новий реліз (живий баг, знайдений під час розгортання з
-- нуля — docs/decisions.md, 2026-09-27). ALTER, не тільки CREATE —
-- та сама причина, що вище: таблиця вже існувала й мала дані.
ALTER TABLE expectation_comparisons ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;

-- LLM-синтез причинного висновку поверх уже готового детермінованого
-- сюрпризу (analysis/expectations/synthesize.py, docs/status.md
-- "наступний крок Фази 2") — "вийшло X, очікувалось Y, це означає Z"
-- (PLAN.md, критерій завершення Фази 2). Один рядок НА comparison_id
-- (не append-only, як news_synthesis/market_synthesis вище) — той
-- самий release_log-цикл не синтезується двічі, і expectation_comparisons
-- сам уже UNIQUE по release_log_id.
CREATE TABLE IF NOT EXISTS expectation_synthesis (
    id             BIGSERIAL PRIMARY KEY,
    comparison_id  BIGINT NOT NULL UNIQUE REFERENCES expectation_comparisons(id),
    summary        TEXT NOT NULL,
    direction      TEXT NOT NULL,     -- up | down | neutral | unclear
    confidence     NUMERIC NOT NULL,
    reasoning      TEXT NOT NULL,
    source_refs    JSONB NOT NULL,
    llm_call_id    BIGINT REFERENCES llm_call_log(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Прогнози трендової моделі (analysis/forecasting/, PLAN.md Фаза 2
-- "базовий механізм прогнозування"). Один рядок на (source, metric_id,
-- method, based_on_observed_at) — той самий принцип UPSERT, що
-- news_synthesis: повторний прогін на тих самих вхідних даних оновлює
-- рядок, не дублює. based_on_observed_at — дата останньої фактичної
-- точки, з якої екстрапольовано (для аудиту "на чому базувався прогноз").
CREATE TABLE IF NOT EXISTS metric_forecasts (
    id                    BIGSERIAL PRIMARY KEY,
    source                TEXT NOT NULL,
    metric_id             TEXT NOT NULL,
    method                TEXT NOT NULL,      -- напр. linear_trend
    based_on_observed_at  DATE NOT NULL,
    periods_ahead         INTEGER NOT NULL DEFAULT 1,
    forecast_value        NUMERIC NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_metric_forecasts_unique
    ON metric_forecasts (source, metric_id, method, based_on_observed_at);

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

-- Крипто-скринінг лонг/шорт/спостереження (analysis/crypto_screening/,
-- PLAN.md Фаза 4, докладніше docs/decisions.md 2026-09-27) — на відміну
-- від screening_results (акції, знімок ОДНОГО прогону), тут МУТАБЕЛЬНИЙ
-- стан, що живе МІЖ прогонами: денний скан (run_screening.py) заводить
-- 'candidate' при виявленні пампу; погодинний моніторинг
-- (monitor_candidates.py) оновлює той самий рядок і переводить статус
-- (candidate -> short/watch, або candidate/watch -> closed, коли памп
-- вичерпався). last_oi_usd — знімок з ПОПЕРЕДНЬОЇ погодинної
-- перевірки, потрібен для рахування дельти "з минулого разу" (не з
-- фіксованого вікна годин — користувач, 2026-09-27: "тримати, поки
-- дані відповідають", без таймера). last_quote_volume НЕ створюємо
-- тут (2026-10-03) — сплеск обсягу тепер рахується з 4г-Binance
-- klines "на льоту" (compute_monitoring_indicators), не зі
-- збереженого 24h-знімка.
CREATE TABLE IF NOT EXISTS crypto_screening_candidates (
    id                     BIGSERIAL PRIMARY KEY,
    symbol                 TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'candidate',  -- candidate | short | watch | closed
    detected_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at        TIMESTAMPTZ,
    closed_at              TIMESTAMPTZ,
    pump_pct_at_detection  NUMERIC NOT NULL,
    last_pump_pct          NUMERIC,
    last_funding_rate      NUMERIC,
    last_oi_usd            NUMERIC,
    reason                 TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Лише ОДИН активний (не closed) рядок на symbol одночасно — новий
-- памп тієї самої монети через тижні заводить НОВИЙ рядок (історія
-- попередніх циклів лишається, rule 6 у дусі — не raw-дані, але той
-- самий принцип "не губити минуле").
CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_candidates_active_symbol
    ON crypto_screening_candidates (symbol) WHERE status != 'closed';

-- Дедуп сповіщень (2026-09-28, критичний фікс — живий фідбек
-- користувача: news_notify.py надсилав ІДЕНТИЧНІ ранкове й вечірнє
-- повідомлення, коли за день з'являлось мало нового). Той самий
-- принцип, що вже застосований у expectation_comparisons.notified_at
-- вище (2026-09-27): NULL = ще не надіслано, reporting-скрипт
-- проставляє now() одразу після успішної відправки. ALTER, не тільки
-- CREATE — усі чотири таблиці вже існували й мали дані до цієї зміни.
ALTER TABLE news_analysis ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;
ALTER TABLE news_synthesis ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;
ALTER TABLE market_synthesis ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;
ALTER TABLE candidate_assets ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;

-- Консолідований новинний дайджест (2026-09-28, живий фідбек
-- користувача: news_notify.py слав по окремій статті — 3 албанських
-- сайти з тим самим текстом про Bitcoin 84000 йшли ТРЬОМА окремими
-- повідомленнями, мовою оригіналу). analysis/news_analysis/consolidate.py
-- бере СИРІ статті (не news_analysis — навмисно, щоб DeepSeek сам
-- відсіював нерелевантне, а не покладався на relevance_filter.py) за
-- вікно й ОДНИМ LLM-викликом на потік: фільтрує шум, об'єднує статті
-- про ОДНУ подію (навіть різними мовами/сайтами) в один запис,
-- перекладає українською. source_raw_news_ids/source_urls — які
-- сирі статті об'єднано (аудит); джерела приєднує КОД за індексами,
-- які повернув DeepSeek, не сам DeepSeek (той самий принцип, що
-- relevance_filter.py — ризик галюцинації URL).
CREATE TABLE IF NOT EXISTS news_consolidated (
    id                  BIGSERIAL PRIMARY KEY,
    stream              TEXT NOT NULL,
    asset_id            TEXT,
    summary             TEXT NOT NULL,
    direction           TEXT NOT NULL,     -- up | down | neutral | unclear
    confidence          NUMERIC NOT NULL,
    reasoning           TEXT NOT NULL,
    source_count        INTEGER NOT NULL,  -- скільки сирих статей об'єднано
    source_raw_news_ids JSONB NOT NULL,
    source_urls         JSONB NOT NULL,
    llm_call_id         BIGINT REFERENCES llm_call_log(id),
    notified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_consolidated_stream_created
    ON news_consolidated (stream, created_at DESC);

-- Яку сиру статтю вже враховано в якомусь прогоні консолідації —
-- щоб той самий прогін (кілька разів на добу) не пережовував ту саму
-- статтю знову й знову. NULL = ще не оброблено.
ALTER TABLE raw_news ADD COLUMN IF NOT EXISTS consolidated_at TIMESTAMPTZ;

-- Свіжість raw_news (2026-09-28, рішення користувача) — СВІДОМИЙ
-- ВИНЯТОК із critical rule 6 кореневого CLAUDE.md ("ніколи не
-- видаляти сирі дані"): обґрунтування правила ("історичні дані — те,
-- на чому тримається якість МАЙБУТНІХ ПРОГНОЗІВ") стосується
-- макропоказників (raw_observations), не новинних статей — стаття
-- тижневої давності не покращує прогноз, лише захаращує "важливі
-- новини" застарілим контентом. Збір (common/news_db.py:
-- MAX_ARTICLE_AGE_HOURS=24) і зберігання (RETENTION_HOURS=48,
-- prune_stale_news(), orchestration-джоба prune_raw_news) тепер МАЮТЬ
-- часову межу. raw_observations (макро/акції/крипта) ЛИШАЄТЬСЯ
-- append-only — це правило їх не торкається.
--
-- ON DELETE CASCADE потрібен: news_analysis.raw_news_id — єдиний
-- реальний FK на raw_news(id) (news_consolidated.source_raw_news_ids —
-- JSONB-масив, не FK, видалення raw_news його не зачіпає). Без CASCADE
-- prune_stale_news() падав би з foreign key violation на будь-якій
-- уже проаналізованій статті. DROP+ADD — ALTER ідемпотентний
-- (apply_schema.py), як решта міграцій цього файлу.
ALTER TABLE news_analysis DROP CONSTRAINT IF EXISTS news_analysis_raw_news_id_fkey;
ALTER TABLE news_analysis ADD CONSTRAINT news_analysis_raw_news_id_fkey
    FOREIGN KEY (raw_news_id) REFERENCES raw_news(id) ON DELETE CASCADE;

-- Причинна атрибуція ціна/новини (news_synthesis) була примітивною
-- (живий фідбек користувача, 2026-10-02): "ціна -5%, новини +4" саме
-- собою не пояснює нічого й не дає гіпотези, яку можна перевірити.
-- confirmation_factors — окреме поле LLM-висновку (synthesize.py:
-- PriceNewsSynthesisResult) поруч із summary: конкретні фактори/дані,
-- які підтвердили б чи спростували гіпотезу тренд/корекція (НЕ
-- прогноз ціни і НЕ торгова рекомендація — описова характеристика,
-- analysis/CLAUDE.md "Заборонені формулювання"). NULL дозволено — рядки
-- до цієї зміни лишаються без нового поля, не зникають.
ALTER TABLE news_synthesis ADD COLUMN IF NOT EXISTS confirmation_factors TEXT;

-- Комплексний міжактивний вплив релізу (2026-10-02, живий фідбек
-- користувача): попередній синтез давав напрямок лише для ОДНОГО
-- пов'язаного активу/валюти — користувач просив розбір впливу на
-- ставку/економіку/валюту/акції/крипту/золото/будь-який інший актив,
-- і ЛИШЕ для категорій, які реліз РЕАЛЬНО зачіпає (без "не впливає"-
-- заповнювачів). asset_impacts — масив {category, assets, direction,
-- explanation} від LLM (analysis/expectations/synthesize.py); NULL/[]
-- дозволено — рядки до цієї зміни лишаються без нового поля.
ALTER TABLE expectation_synthesis ADD COLUMN IF NOT EXISTS asset_impacts JSONB;

-- impact_notified_at (2026-10-02, рішення користувача того самого дня:
-- "сюрприз лишається сюрпризом, а широкий аналіз ринку — це новий
-- [звіт]") — ОКРЕМИЙ дедуп від expectation_comparisons.notified_at
-- (яким керує expectations_notify.py, короткий сюрприз-звіт).
-- reporting/release_impact_notify.py (новий, окремий Telegram-звіт із
-- розбором asset_impacts вище) проставляє цю колонку одразу після
-- успішної відправки — той самий принцип NULL = ще не надіслано, що
-- всюди в проєкті (reporting/CLAUDE.md "Дедуплікація сповіщень").
ALTER TABLE expectation_synthesis ADD COLUMN IF NOT EXISTS impact_notified_at TIMESTAMPTZ;

-- Heartbeat планувальника (2026-10-02, живий випадок користувача:
-- реліз NFP/Unemployment о 15:30 опрацьовано лише о 17:57 —
-- розслідування показало, що сам конвеєр check_releases→...→
-- notify_expectations займає ~15 хв, а причина затримки була в тому,
-- що контейнер scheduler був недоступний ~11 годин (докер/хост не
-- піднятий) і ніхто про це не дізнався, поки звіт не прийшов із
-- запізненням. Один рядок (id=1): jobs.py:_scheduler_heartbeat
-- оновлює last_tick_at кожні 5 хв; orchestration/main.py звіряє
-- розрив при старті процесу й шле один Telegram-алерт, якщо простій
-- був ненормально довгим (docs/production-readiness.md, P0 "Heartbeat
-- планувальника" — перший практичний крок).
CREATE TABLE IF NOT EXISTS scheduler_heartbeat (
    id           SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_tick_at TIMESTAMPTZ NOT NULL
);

-- notified_at для screening_results (2026-10-02, docs/production-readiness.md
-- розділ 3а №1: "скринінг рахується щодня, але жодного reporting-скрипта
-- для нього немає"): reporting/screening_notify.py — той самий принцип
-- NULL = ще не надіслано, що всюди в проєкті. Дедуп тут не по id рядків
-- (композит рахується на весь S&P-прохід одразу), а по run_at: нотифай
-- позначає весь run_at одним UPDATE, щоб той самий щоденний прогін не
-- надсилався повторно, якщо notify-джоба випадково спрацює двічі.
ALTER TABLE screening_results ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;

-- company_name/price_change_24h_pct для screening_results (2026-10-02,
-- живий фідбек користувача: вивід score/revenue/eps/pe/avg_dollar_volume
-- "страшний" — реальна потреба читача Telegram-звіту: тикер, назва
-- компанії, зміна ціни за 24г, не сирі компоненти формули ранжування).
-- composite_score.py рахує й зберігає обидва поля ПІСЛЯ самого
-- ранжування (не впливають на score) — лише контекст для виводу.
-- company_name — з constituents.csv (collect_universe.py, той самий
-- підхід, що вже використовує discover_candidates.py); NULL, якщо
-- мережевий запит не вдався (screening_notify.py тоді показує тикер
-- замість назви, не падає).
ALTER TABLE screening_results ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE screening_results ADD COLUMN IF NOT EXISTS price_change_24h_pct NUMERIC;

-- price_date/volume_change_24h_pct (2026-10-02, живий фідбек
-- користувача: "на яку дату ці дані? чи є можливість добавити обсяг
-- торгів за 24 год у доларах?", того самого дня уточнено: "обсяг
-- потрібно в відсотках зміни за 24 години", не в доларах —
-- volume_change_24h_pct одразу в підсумковій формі, попередній варіант
-- у $ ніде не встиг використовуватись). price_date — дата ОСТАННЬОГО
-- закриття, на основі якого рахуються обидва %-поля (не run_at самого
-- скринінгу — можуть відрізнятись на кілька годин через час збору
-- котирувань). volume_change_24h_pct — % зміна обсягу торгів день-до-дня
-- (twelvedata), той самий стиль, що price_change_24h_pct.
ALTER TABLE screening_results ADD COLUMN IF NOT EXISTS price_date DATE;
ALTER TABLE screening_results ADD COLUMN IF NOT EXISTS volume_change_24h_pct NUMERIC;
-- volume_24h_usd — попередня (тим самим днем, кілька хвилин) версія
-- цього поля в доларах, жодного живого коду чи звіту вже не читає її.
ALTER TABLE screening_results DROP COLUMN IF EXISTS volume_24h_usd;

-- notified_at для crypto_screening_candidates (2026-10-02, PLAN.md
-- Фаза 4 Крок 5: "Telegram-сповіщення про SHORT/WATCH, зараз лише
-- лог" — закрито для SHORT/WATCH тут; LONG-кандидати run_screening.py
-- й далі лише логуються, у цій таблиці не персистуються, окреме
-- рішення). На відміну від append-only таблиць вище, рядок тут
-- МУТАБЕЛЬНИЙ (monitor_candidates.py оновлює status щогодини) —
-- _candidates_db.py:update_candidate() скидає notified_at на NULL,
-- коли status РЕАЛЬНО змінився (напр. candidate→short), той самий
-- принцип, що вже застосований до news_synthesis/market_synthesis
-- (2026-09-29, "UPSERT не скидав notified_at — повторний результат
-- того самого дня мовчки губився") — інакше значущий перехід
-- лишився б непоміченим під уже проставленим notified_at.
ALTER TABLE crypto_screening_candidates ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;

-- LONG-кандидати крипто-скринінгу (2026-10-02, рішення користувача:
-- закрити LONG перед тестуванням notify-скриптів). На відміну від
-- crypto_screening_candidates вище (SHORT/WATCH, мутабельний стан —
-- памп, що з часом вичерпується, тож потребує погодинного
-- моніторингу статусу), LONG-сигнал — "сьогодні тренд підтверджений"
-- для вже Tier A-допущеного символу (run_screening.py, широкий денний
-- скан усього ринку) — append-only ЗНІМОК одного прогону, той самий
-- принцип, що screening_results (акції): один run_at на весь виклик,
-- notified_at для дедупу Telegram, "останній прогін" = MAX(run_at).
-- Раніше LONG лише логувався (logger.info), ніколи не йшов у БД.
CREATE TABLE IF NOT EXISTS crypto_long_candidates (
    id            BIGSERIAL PRIMARY KEY,
    symbol        TEXT NOT NULL,
    oi_change_pct NUMERIC,
    rsi_value     NUMERIC,
    funding_rate  NUMERIC,
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    notified_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_crypto_long_candidates_run_at ON crypto_long_candidates (run_at);

-- last_price для crypto_screening_candidates (2026-10-03, живий кейс
-- користувача: MAGMAUSDT не підхоплений на SHORT, хоча реальний
-- розворот стався в межах години — pump_pct/volume_spike_pct, які
-- вже є, рахуються з 24-ГОДИННИХ rolling-показників самих бірж
-- (price24hPcnt/priceChangePercent), тож свіжий розворот В МЕЖАХ
-- ГОДИНИ розмивається добовим вікном і може лишатись непоміченим
-- кілька годин. last_price — ціна (Binance mark_price) на момент
-- ПОПЕРЕДНЬОЇ погодинної перевірки — monitor_candidates.py рахує
-- price_change_pct_1h = (поточна - last_price) / last_price, і це
-- йде в short_watch_screen.py як ДОДАТКОВИЙ (не єдиний) шлях
-- підтвердження розвороту, поруч із volume_spike_pct.
ALTER TABLE crypto_screening_candidates ADD COLUMN IF NOT EXISTS last_price NUMERIC;

-- last_quote_volume (2026-10-03): сплеск обсягу під час моніторингу
-- тепер рахується з 4г-Binance klines "на льоту"
-- (run_screening.py:compute_monitoring_indicators), не зі збереженого
-- 24h-знімка біржі — колонка ніде більше не читалась (ані для
-- рішення, ані у Telegram-виводі), прибрано, не лишено мертвою.
ALTER TABLE crypto_screening_candidates DROP COLUMN IF EXISTS last_quote_volume;

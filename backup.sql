--
-- PostgreSQL database dump
--

\restrict 7A9Yc6wSFVvSPOXdvn1NManke8BDdPVno7ZnqSBuS4hG6jgHV5VipLrP5swx2ue

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: raw_observations; Type: TABLE; Schema: public; Owner: invest_agent
--

CREATE TABLE public.raw_observations (
    id bigint NOT NULL,
    source text NOT NULL,
    metric_id text NOT NULL,
    value numeric NOT NULL,
    observed_at date NOT NULL,
    fetched_at timestamp with time zone NOT NULL,
    revision integer DEFAULT 1 NOT NULL,
    raw_payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_observations OWNER TO invest_agent;

--
-- Name: _hyper_1_10_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_10_chunk (
    CONSTRAINT constraint_10 CHECK (((observed_at >= '2026-01-29'::date) AND (observed_at < '2026-02-05'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_10_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_11_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_11_chunk (
    CONSTRAINT constraint_11 CHECK (((observed_at >= '2026-02-26'::date) AND (observed_at < '2026-03-05'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_11_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_12_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_12_chunk (
    CONSTRAINT constraint_12 CHECK (((observed_at >= '2026-03-26'::date) AND (observed_at < '2026-04-02'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_12_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_13_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_13_chunk (
    CONSTRAINT constraint_13 CHECK (((observed_at >= '2026-04-30'::date) AND (observed_at < '2026-05-07'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_13_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_14_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_14_chunk (
    CONSTRAINT constraint_14 CHECK (((observed_at >= '2026-05-28'::date) AND (observed_at < '2026-06-04'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_14_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_3_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_3_chunk (
    CONSTRAINT constraint_3 CHECK (((observed_at >= '2025-07-31'::date) AND (observed_at < '2025-08-07'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_3_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_4_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_4_chunk (
    CONSTRAINT constraint_4 CHECK (((observed_at >= '2025-08-28'::date) AND (observed_at < '2025-09-04'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_4_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_5_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_5_chunk (
    CONSTRAINT constraint_5 CHECK (((observed_at >= '2025-09-25'::date) AND (observed_at < '2025-10-02'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_5_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_6_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_6_chunk (
    CONSTRAINT constraint_6 CHECK (((observed_at >= '2025-10-30'::date) AND (observed_at < '2025-11-06'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_6_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_7_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_7_chunk (
    CONSTRAINT constraint_7 CHECK (((observed_at >= '2025-11-27'::date) AND (observed_at < '2025-12-04'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_7_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_8_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_8_chunk (
    CONSTRAINT constraint_8 CHECK (((observed_at >= '2026-08-20'::date) AND (observed_at < '2026-08-27'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_8_chunk OWNER TO invest_agent;

--
-- Name: _hyper_1_9_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE TABLE _timescaledb_internal._hyper_1_9_chunk (
    CONSTRAINT constraint_9 CHECK (((observed_at >= '2026-08-27'::date) AND (observed_at < '2026-09-03'::date)))
)
INHERITS (public.raw_observations);


ALTER TABLE _timescaledb_internal._hyper_1_9_chunk OWNER TO invest_agent;

--
-- Name: raw_observations_id_seq; Type: SEQUENCE; Schema: public; Owner: invest_agent
--

CREATE SEQUENCE public.raw_observations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_observations_id_seq OWNER TO invest_agent;

--
-- Name: raw_observations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: invest_agent
--

ALTER SEQUENCE public.raw_observations_id_seq OWNED BY public.raw_observations.id;


--
-- Name: release_log; Type: TABLE; Schema: public; Owner: invest_agent
--

CREATE TABLE public.release_log (
    id bigint NOT NULL,
    source text NOT NULL,
    metric_id text NOT NULL,
    scheduled_at timestamp with time zone,
    detected_at timestamp with time zone,
    impact_level text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.release_log OWNER TO invest_agent;

--
-- Name: release_log_id_seq; Type: SEQUENCE; Schema: public; Owner: invest_agent
--

CREATE SEQUENCE public.release_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.release_log_id_seq OWNER TO invest_agent;

--
-- Name: release_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: invest_agent
--

ALTER SEQUENCE public.release_log_id_seq OWNED BY public.release_log.id;


--
-- Name: sources; Type: TABLE; Schema: public; Owner: invest_agent
--

CREATE TABLE public.sources (
    name text NOT NULL,
    category text NOT NULL,
    source_type text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sources OWNER TO invest_agent;

--
-- Name: _hyper_1_10_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_10_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_10_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_11_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_11_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_11_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_12_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_12_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_12_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_13_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_13_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_13_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_14_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_14_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_14_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_3_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_3_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_3_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_4_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_4_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_4_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_5_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_5_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_5_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_6_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_6_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_6_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_7_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_7_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_7_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_8_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_8_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_8_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: _hyper_1_9_chunk id; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: _hyper_1_9_chunk revision; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk ALTER COLUMN revision SET DEFAULT 1;


--
-- Name: _hyper_1_9_chunk created_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk ALTER COLUMN created_at SET DEFAULT now();


--
-- Name: raw_observations id; Type: DEFAULT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.raw_observations ALTER COLUMN id SET DEFAULT nextval('public.raw_observations_id_seq'::regclass);


--
-- Name: release_log id; Type: DEFAULT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.release_log ALTER COLUMN id SET DEFAULT nextval('public.release_log_id_seq'::regclass);


--
-- Data for Name: hypertable; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM stdin;
1	public	raw_observations	_timescaledb_internal	_hyper_1	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
\.


--
-- Data for Name: bgw_job; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM stdin;
\.


--
-- Data for Name: chunk; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.chunk (id, relid, hypertable_id, status, osm_chunk, creation_time) FROM stdin;
3	_timescaledb_internal._hyper_1_3_chunk	1	0	f	2026-08-30 11:02:02.610613+00
4	_timescaledb_internal._hyper_1_4_chunk	1	0	f	2026-08-30 11:02:02.708757+00
5	_timescaledb_internal._hyper_1_5_chunk	1	0	f	2026-08-30 11:02:02.778736+00
6	_timescaledb_internal._hyper_1_6_chunk	1	0	f	2026-08-30 11:02:02.849614+00
7	_timescaledb_internal._hyper_1_7_chunk	1	0	f	2026-08-30 11:02:02.917032+00
8	_timescaledb_internal._hyper_1_8_chunk	1	0	f	2026-08-30 11:02:11.049001+00
9	_timescaledb_internal._hyper_1_9_chunk	1	0	f	2026-08-30 11:02:11.143791+00
10	_timescaledb_internal._hyper_1_10_chunk	1	0	f	2026-08-30 11:02:32.233928+00
11	_timescaledb_internal._hyper_1_11_chunk	1	0	f	2026-08-30 11:02:32.317017+00
12	_timescaledb_internal._hyper_1_12_chunk	1	0	f	2026-08-30 11:02:32.38842+00
13	_timescaledb_internal._hyper_1_13_chunk	1	0	f	2026-08-30 11:02:32.458176+00
14	_timescaledb_internal._hyper_1_14_chunk	1	0	f	2026-08-30 11:02:32.5273+00
\.


--
-- Data for Name: chunk_column_stats; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM stdin;
\.


--
-- Data for Name: compression_chunk_size; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM stdin;
\.


--
-- Data for Name: compression_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst, index) FROM stdin;
\.


--
-- Data for Name: continuous_agg; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only, schema_change_timestamp) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_bucket_function; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_hypertable_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_invalidation_threshold; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_jobs_refresh_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_jobs_refresh_ranges (materialization_id, start_range, end_range, pid, job_id, created_at) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_materialization_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_materialization_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_materialization_ranges (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_tenant_tracking; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_tenant_tracking (hypertable_id, tenant_id, min_timestamp, max_timestamp, seqnum) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_watermark; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM stdin;
\.


--
-- Data for Name: dimension; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM stdin;
1	1	observed_at	date	t	\N	\N	\N	604800000000	\N	\N	\N
\.


--
-- Data for Name: dimension_slice; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.dimension_slice (id, chunk_id, dimension_id, range_start, range_end) FROM stdin;
3	3	1	1753920000000000	1754524800000000
4	4	1	1756339200000000	1756944000000000
5	5	1	1758758400000000	1759363200000000
6	6	1	1761782400000000	1762387200000000
7	7	1	1764201600000000	1764806400000000
8	8	1	1787184000000000	1787788800000000
9	9	1	1787788800000000	1788393600000000
10	10	1	1769644800000000	1770249600000000
11	11	1	1772064000000000	1772668800000000
12	12	1	1774483200000000	1775088000000000
13	13	1	1777507200000000	1778112000000000
14	14	1	1779926400000000	1780531200000000
\.


--
-- Data for Name: hypertable_cagg_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.hypertable_cagg_settings (hypertable_id, granular_refresh_column, granular_refresh_start_offset, granular_refresh_end_offset) FROM stdin;
\.


--
-- Data for Name: metadata; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM stdin;
install_timestamp	2026-08-30 10:51:14.195839+00	t
timescaledb_version	2.29.2	f
\.


--
-- Data for Name: tablespace; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: invest_agent
--

COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM stdin;
\.


--
-- Data for Name: _hyper_1_10_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_10_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
13	ecb	eurozone_unemployment_rate	6.4	2026-02-01	2026-08-30 11:02:32.210523+00	1	{"KEY": "LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T", "FREQ": "M", "UNIT": "PC", "TITLE": "Unemployment rate, age 15 to 74, total", "GENDER": "T", "OBS_COM": "", "COVERAGE": "", "DECIMALS": "1", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "6.4", "UNIT_MULT": "0", "ADJUSTMENT": "S", "COLLECTION": "A", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2026-02", "TITLE_COMPL": "Euro area (changing composition); European Labour Force Survey; Unemployment rate; Total; Age 15 to 74; Total; Seasonally adjusted, not working day adjusted", "AGE_BREAKDOWN": "15_74", "LFS_BREAKDOWN": "TOTAL0", "LFS_INDICATOR": "UNEHRT", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:32.224443+00
\.


--
-- Data for Name: _hyper_1_11_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_11_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
14	ecb	eurozone_unemployment_rate	6.3	2026-03-01	2026-08-30 11:02:32.210523+00	1	{"KEY": "LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T", "FREQ": "M", "UNIT": "PC", "TITLE": "Unemployment rate, age 15 to 74, total", "GENDER": "T", "OBS_COM": "", "COVERAGE": "", "DECIMALS": "1", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "6.3", "UNIT_MULT": "0", "ADJUSTMENT": "S", "COLLECTION": "A", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2026-03", "TITLE_COMPL": "Euro area (changing composition); European Labour Force Survey; Unemployment rate; Total; Age 15 to 74; Total; Seasonally adjusted, not working day adjusted", "AGE_BREAKDOWN": "15_74", "LFS_BREAKDOWN": "TOTAL0", "LFS_INDICATOR": "UNEHRT", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:32.315683+00
\.


--
-- Data for Name: _hyper_1_12_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_12_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
15	ecb	eurozone_unemployment_rate	6.3	2026-04-01	2026-08-30 11:02:32.210523+00	1	{"KEY": "LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T", "FREQ": "M", "UNIT": "PC", "TITLE": "Unemployment rate, age 15 to 74, total", "GENDER": "T", "OBS_COM": "", "COVERAGE": "", "DECIMALS": "1", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "6.3", "UNIT_MULT": "0", "ADJUSTMENT": "S", "COLLECTION": "A", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2026-04", "TITLE_COMPL": "Euro area (changing composition); European Labour Force Survey; Unemployment rate; Total; Age 15 to 74; Total; Seasonally adjusted, not working day adjusted", "AGE_BREAKDOWN": "15_74", "LFS_BREAKDOWN": "TOTAL0", "LFS_INDICATOR": "UNEHRT", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:32.387209+00
\.


--
-- Data for Name: _hyper_1_13_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_13_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
16	ecb	eurozone_unemployment_rate	6.3	2026-05-01	2026-08-30 11:02:32.210523+00	1	{"KEY": "LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T", "FREQ": "M", "UNIT": "PC", "TITLE": "Unemployment rate, age 15 to 74, total", "GENDER": "T", "OBS_COM": "", "COVERAGE": "", "DECIMALS": "1", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "6.3", "UNIT_MULT": "0", "ADJUSTMENT": "S", "COLLECTION": "A", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2026-05", "TITLE_COMPL": "Euro area (changing composition); European Labour Force Survey; Unemployment rate; Total; Age 15 to 74; Total; Seasonally adjusted, not working day adjusted", "AGE_BREAKDOWN": "15_74", "LFS_BREAKDOWN": "TOTAL0", "LFS_INDICATOR": "UNEHRT", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:32.456822+00
\.


--
-- Data for Name: _hyper_1_14_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_14_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
17	ecb	eurozone_unemployment_rate	6.3	2026-06-01	2026-08-30 11:02:32.210523+00	1	{"KEY": "LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T", "FREQ": "M", "UNIT": "PC", "TITLE": "Unemployment rate, age 15 to 74, total", "GENDER": "T", "OBS_COM": "", "COVERAGE": "", "DECIMALS": "1", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "6.3", "UNIT_MULT": "0", "ADJUSTMENT": "S", "COLLECTION": "A", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2026-06", "TITLE_COMPL": "Euro area (changing composition); European Labour Force Survey; Unemployment rate; Total; Age 15 to 74; Total; Seasonally adjusted, not working day adjusted", "AGE_BREAKDOWN": "15_74", "LFS_BREAKDOWN": "TOTAL0", "LFS_INDICATOR": "UNEHRT", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:32.525996+00
\.


--
-- Data for Name: _hyper_1_3_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_3_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
3	ecb	eurozone_hicp	2	2025-08-01	2026-08-30 11:02:02.586827+00	1	{"KEY": "ICP.M.U2.N.000000.4.ANR", "FREQ": "M", "UNIT": "PCCH", "TITLE": "HICP - Overall index", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "DECIMALS": "1", "DISS_ORG": "", "ICP_ITEM": "000000", "OBS_CONF": "F", "PUBL_ECB": "", "REF_AREA": "U2", "DATA_COMP": "", "OBS_VALUE": "2", "UNIT_MULT": "0", "ADJUSTMENT": "N", "COLLECTION": "A", "ICP_SUFFIX": "ANR", "OBS_STATUS": "A", "COMPILATION": "", "DOM_SER_IDS": "ICPT.M.VAL.HICP.RCH_A.EA.00.M", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2025-08", "TITLE_COMPL": "Euro area (changing composition) - HICP - Overall index, Annual rate of change, Eurostat, Neither seasonally nor working day adjusted", "COMPILING_ORG": "", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "STS_INSTITUTION": "4", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:02.600224+00
\.


--
-- Data for Name: _hyper_1_4_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_4_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
4	ecb	eurozone_hicp	2.2	2025-09-01	2026-08-30 11:02:02.586827+00	1	{"KEY": "ICP.M.U2.N.000000.4.ANR", "FREQ": "M", "UNIT": "PCCH", "TITLE": "HICP - Overall index", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "DECIMALS": "1", "DISS_ORG": "", "ICP_ITEM": "000000", "OBS_CONF": "F", "PUBL_ECB": "", "REF_AREA": "U2", "DATA_COMP": "", "OBS_VALUE": "2.2", "UNIT_MULT": "0", "ADJUSTMENT": "N", "COLLECTION": "A", "ICP_SUFFIX": "ANR", "OBS_STATUS": "A", "COMPILATION": "", "DOM_SER_IDS": "ICPT.M.VAL.HICP.RCH_A.EA.00.M", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2025-09", "TITLE_COMPL": "Euro area (changing composition) - HICP - Overall index, Annual rate of change, Eurostat, Neither seasonally nor working day adjusted", "COMPILING_ORG": "", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "STS_INSTITUTION": "4", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:02.707205+00
\.


--
-- Data for Name: _hyper_1_5_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_5_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
5	ecb	eurozone_hicp	2.1	2025-10-01	2026-08-30 11:02:02.586827+00	1	{"KEY": "ICP.M.U2.N.000000.4.ANR", "FREQ": "M", "UNIT": "PCCH", "TITLE": "HICP - Overall index", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "DECIMALS": "1", "DISS_ORG": "", "ICP_ITEM": "000000", "OBS_CONF": "F", "PUBL_ECB": "", "REF_AREA": "U2", "DATA_COMP": "", "OBS_VALUE": "2.1", "UNIT_MULT": "0", "ADJUSTMENT": "N", "COLLECTION": "A", "ICP_SUFFIX": "ANR", "OBS_STATUS": "E", "COMPILATION": "", "DOM_SER_IDS": "ICPT.M.VAL.HICP.RCH_A.EA.00.M", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2025-10", "TITLE_COMPL": "Euro area (changing composition) - HICP - Overall index, Annual rate of change, Eurostat, Neither seasonally nor working day adjusted", "COMPILING_ORG": "", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "STS_INSTITUTION": "4", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:02.777429+00
\.


--
-- Data for Name: _hyper_1_6_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_6_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
6	ecb	eurozone_hicp	2.1	2025-11-01	2026-08-30 11:02:02.586827+00	1	{"KEY": "ICP.M.U2.N.000000.4.ANR", "FREQ": "M", "UNIT": "PCCH", "TITLE": "HICP - Overall index", "BREAKS": "", "OBS_COM": "As of 4 February 2026 onwards, the euro area HICP inflation will undergo major methodological changes, according to theÂ announcement by Eurostat. On the same day, the ECB will also discontinue the current Indices of Consumer Prices - ICP dataset  and replace it with a new HICP dataset that will accurately reflect the methodological changes by Eurostat.", "PUBL_MU": "", "COVERAGE": "", "DECIMALS": "1", "DISS_ORG": "", "ICP_ITEM": "000000", "OBS_CONF": "F", "PUBL_ECB": "", "REF_AREA": "U2", "DATA_COMP": "", "OBS_VALUE": "2.1", "UNIT_MULT": "0", "ADJUSTMENT": "N", "COLLECTION": "A", "ICP_SUFFIX": "ANR", "OBS_STATUS": "A", "COMPILATION": "", "DOM_SER_IDS": "ICPT.M.VAL.HICP.RCH_A.EA.00.M", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2025-11", "TITLE_COMPL": "Euro area (changing composition) - HICP - Overall index, Annual rate of change, Eurostat, Neither seasonally nor working day adjusted", "COMPILING_ORG": "", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "STS_INSTITUTION": "4", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:02.848091+00
\.


--
-- Data for Name: _hyper_1_7_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_7_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
7	ecb	eurozone_hicp	1.9	2025-12-01	2026-08-30 11:02:02.586827+00	1	{"KEY": "ICP.M.U2.N.000000.4.ANR", "FREQ": "M", "UNIT": "PCCH", "TITLE": "HICP - Overall index", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "DECIMALS": "1", "DISS_ORG": "", "ICP_ITEM": "000000", "OBS_CONF": "F", "PUBL_ECB": "", "REF_AREA": "U2", "DATA_COMP": "", "OBS_VALUE": "1.9", "UNIT_MULT": "0", "ADJUSTMENT": "N", "COLLECTION": "A", "ICP_SUFFIX": "ANR", "OBS_STATUS": "A", "COMPILATION": "", "DOM_SER_IDS": "ICPT.M.VAL.HICP.RCH_A.EA.00.M", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1M", "TIME_PERIOD": "2025-12", "TITLE_COMPL": "Euro area (changing composition) - HICP - Overall index, Annual rate of change, Eurostat, Neither seasonally nor working day adjusted", "COMPILING_ORG": "", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "STS_INSTITUTION": "4", "UNIT_INDEX_BASE": ""}	2026-08-30 11:02:02.915832+00
\.


--
-- Data for Name: _hyper_1_8_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_8_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
8	ecb	eurozone_deposit_rate	2.25	2026-08-26	2026-08-30 11:02:11.028503+00	1	{"KEY": "FM.D.U2.EUR.4F.KR.DFR.LEV", "FREQ": "D", "UNIT": "PCPA", "TITLE": "Deposit facility - date of changes (raw data) - Level", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "CURRENCY": "EUR", "DECIMALS": "7", "DISS_ORG": "", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "2.25", "UNIT_MULT": "0", "COLLECTION": "E", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "DOM_SER_IDS": "", "FM_LOT_SIZE": "", "FM_MATURITY": "", "FM_PUT_CALL": "", "PROVIDER_FM": "4F", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1D", "TIME_PERIOD": "2026-08-26", "TITLE_COMPL": "Euro area (changing composition) - Key interest rate - Deposit facility - date of changes (raw data) - Level - Euro, provided by ECB", "DATA_TYPE_FM": "LEV", "COMPILING_ORG": "4F0", "FM_IDENTIFIER": "", "INSTRUMENT_FM": "KR", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "FM_COUPON_RATE": "", "FM_OUTS_AMOUNT": "", "PROVIDER_FM_ID": "DFR", "FM_STRIKE_PRICE": "", "UNIT_INDEX_BASE": "", "FM_CONTRACT_TIME": ""}	2026-08-30 11:02:11.03925+00
\.


--
-- Data for Name: _hyper_1_9_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: invest_agent
--

COPY _timescaledb_internal._hyper_1_9_chunk (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
9	ecb	eurozone_deposit_rate	2.25	2026-08-27	2026-08-30 11:02:11.028503+00	1	{"KEY": "FM.D.U2.EUR.4F.KR.DFR.LEV", "FREQ": "D", "UNIT": "PCPA", "TITLE": "Deposit facility - date of changes (raw data) - Level", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "CURRENCY": "EUR", "DECIMALS": "7", "DISS_ORG": "", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "2.25", "UNIT_MULT": "0", "COLLECTION": "E", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "DOM_SER_IDS": "", "FM_LOT_SIZE": "", "FM_MATURITY": "", "FM_PUT_CALL": "", "PROVIDER_FM": "4F", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1D", "TIME_PERIOD": "2026-08-27", "TITLE_COMPL": "Euro area (changing composition) - Key interest rate - Deposit facility - date of changes (raw data) - Level - Euro, provided by ECB", "DATA_TYPE_FM": "LEV", "COMPILING_ORG": "4F0", "FM_IDENTIFIER": "", "INSTRUMENT_FM": "KR", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "FM_COUPON_RATE": "", "FM_OUTS_AMOUNT": "", "PROVIDER_FM_ID": "DFR", "FM_STRIKE_PRICE": "", "UNIT_INDEX_BASE": "", "FM_CONTRACT_TIME": ""}	2026-08-30 11:02:11.14248+00
10	ecb	eurozone_deposit_rate	2.25	2026-08-28	2026-08-30 11:02:11.028503+00	1	{"KEY": "FM.D.U2.EUR.4F.KR.DFR.LEV", "FREQ": "D", "UNIT": "PCPA", "TITLE": "Deposit facility - date of changes (raw data) - Level", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "CURRENCY": "EUR", "DECIMALS": "7", "DISS_ORG": "", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "2.25", "UNIT_MULT": "0", "COLLECTION": "E", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "DOM_SER_IDS": "", "FM_LOT_SIZE": "", "FM_MATURITY": "", "FM_PUT_CALL": "", "PROVIDER_FM": "4F", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1D", "TIME_PERIOD": "2026-08-28", "TITLE_COMPL": "Euro area (changing composition) - Key interest rate - Deposit facility - date of changes (raw data) - Level - Euro, provided by ECB", "DATA_TYPE_FM": "LEV", "COMPILING_ORG": "4F0", "FM_IDENTIFIER": "", "INSTRUMENT_FM": "KR", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "FM_COUPON_RATE": "", "FM_OUTS_AMOUNT": "", "PROVIDER_FM_ID": "DFR", "FM_STRIKE_PRICE": "", "UNIT_INDEX_BASE": "", "FM_CONTRACT_TIME": ""}	2026-08-30 11:02:11.21522+00
11	ecb	eurozone_deposit_rate	2.25	2026-08-29	2026-08-30 11:02:11.028503+00	1	{"KEY": "FM.D.U2.EUR.4F.KR.DFR.LEV", "FREQ": "D", "UNIT": "PCPA", "TITLE": "Deposit facility - date of changes (raw data) - Level", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "CURRENCY": "EUR", "DECIMALS": "7", "DISS_ORG": "", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "2.25", "UNIT_MULT": "0", "COLLECTION": "E", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "DOM_SER_IDS": "", "FM_LOT_SIZE": "", "FM_MATURITY": "", "FM_PUT_CALL": "", "PROVIDER_FM": "4F", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1D", "TIME_PERIOD": "2026-08-29", "TITLE_COMPL": "Euro area (changing composition) - Key interest rate - Deposit facility - date of changes (raw data) - Level - Euro, provided by ECB", "DATA_TYPE_FM": "LEV", "COMPILING_ORG": "4F0", "FM_IDENTIFIER": "", "INSTRUMENT_FM": "KR", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "FM_COUPON_RATE": "", "FM_OUTS_AMOUNT": "", "PROVIDER_FM_ID": "DFR", "FM_STRIKE_PRICE": "", "UNIT_INDEX_BASE": "", "FM_CONTRACT_TIME": ""}	2026-08-30 11:02:11.224001+00
12	ecb	eurozone_deposit_rate	2.25	2026-08-30	2026-08-30 11:02:11.028503+00	1	{"KEY": "FM.D.U2.EUR.4F.KR.DFR.LEV", "FREQ": "D", "UNIT": "PCPA", "TITLE": "Deposit facility - date of changes (raw data) - Level", "BREAKS": "", "OBS_COM": "", "PUBL_MU": "", "COVERAGE": "", "CURRENCY": "EUR", "DECIMALS": "7", "DISS_ORG": "", "OBS_CONF": "F", "REF_AREA": "U2", "OBS_VALUE": "2.25", "UNIT_MULT": "0", "COLLECTION": "E", "OBS_STATUS": "A", "SOURCE_PUB": "", "COMPILATION": "", "DOM_SER_IDS": "", "FM_LOT_SIZE": "", "FM_MATURITY": "", "FM_PUT_CALL": "", "PROVIDER_FM": "4F", "PUBL_PUBLIC": "", "TIME_FORMAT": "P1D", "TIME_PERIOD": "2026-08-30", "TITLE_COMPL": "Euro area (changing composition) - Key interest rate - Deposit facility - date of changes (raw data) - Level - Euro, provided by ECB", "DATA_TYPE_FM": "LEV", "COMPILING_ORG": "4F0", "FM_IDENTIFIER": "", "INSTRUMENT_FM": "KR", "OBS_PRE_BREAK": "", "SOURCE_AGENCY": "", "FM_COUPON_RATE": "", "FM_OUTS_AMOUNT": "", "PROVIDER_FM_ID": "DFR", "FM_STRIKE_PRICE": "", "UNIT_INDEX_BASE": "", "FM_CONTRACT_TIME": ""}	2026-08-30 11:02:11.231513+00
\.


--
-- Data for Name: raw_observations; Type: TABLE DATA; Schema: public; Owner: invest_agent
--

COPY public.raw_observations (id, source, metric_id, value, observed_at, fetched_at, revision, raw_payload, created_at) FROM stdin;
\.


--
-- Data for Name: release_log; Type: TABLE DATA; Schema: public; Owner: invest_agent
--

COPY public.release_log (id, source, metric_id, scheduled_at, detected_at, impact_level, status, created_at) FROM stdin;
\.


--
-- Data for Name: sources; Type: TABLE DATA; Schema: public; Owner: invest_agent
--

COPY public.sources (name, category, source_type, notes, created_at) FROM stdin;
fred	macro	official_primary	Federal Reserve Economic Data (US)	2026-08-30 10:51:15.240063+00
ecb	macro	official_primary	ECB Data Portal (колишній SDW), єврозона	2026-08-30 11:01:46.123858+00
\.


--
-- Name: bgw_job_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.bgw_job_id_seq', 1000, false);


--
-- Name: chunk_column_stats_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_column_stats_id_seq', 1, false);


--
-- Name: chunk_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_id_seq', 14, true);


--
-- Name: dimension_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_id_seq', 1, true);


--
-- Name: dimension_slice_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_slice_id_seq', 14, true);


--
-- Name: hypertable_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: invest_agent
--

SELECT pg_catalog.setval('_timescaledb_catalog.hypertable_id_seq', 1, true);


--
-- Name: raw_observations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: invest_agent
--

SELECT pg_catalog.setval('public.raw_observations_id_seq', 17, true);


--
-- Name: release_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: invest_agent
--

SELECT pg_catalog.setval('public.release_log_id_seq', 1, false);


--
-- Name: _hyper_1_10_chunk 10_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk
    ADD CONSTRAINT "10_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_10_chunk 10_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk
    ADD CONSTRAINT "10_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_11_chunk 11_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk
    ADD CONSTRAINT "11_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_11_chunk 11_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk
    ADD CONSTRAINT "11_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_12_chunk 12_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk
    ADD CONSTRAINT "12_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_12_chunk 12_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk
    ADD CONSTRAINT "12_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_13_chunk 13_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk
    ADD CONSTRAINT "13_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_13_chunk 13_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk
    ADD CONSTRAINT "13_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_14_chunk 14_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk
    ADD CONSTRAINT "14_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_14_chunk 14_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk
    ADD CONSTRAINT "14_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_3_chunk 3_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk
    ADD CONSTRAINT "3_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_3_chunk 3_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk
    ADD CONSTRAINT "3_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_4_chunk 4_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk
    ADD CONSTRAINT "4_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_4_chunk 4_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk
    ADD CONSTRAINT "4_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_5_chunk 5_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk
    ADD CONSTRAINT "5_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_5_chunk 5_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk
    ADD CONSTRAINT "5_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_6_chunk 6_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk
    ADD CONSTRAINT "6_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_6_chunk 6_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk
    ADD CONSTRAINT "6_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_7_chunk 7_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk
    ADD CONSTRAINT "7_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_7_chunk 7_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk
    ADD CONSTRAINT "7_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_8_chunk 8_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk
    ADD CONSTRAINT "8_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_8_chunk 8_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk
    ADD CONSTRAINT "8_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: _hyper_1_9_chunk 9_raw_observations_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk
    ADD CONSTRAINT "9_raw_observations_pkey" PRIMARY KEY (id, observed_at);


--
-- Name: _hyper_1_9_chunk 9_raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk
    ADD CONSTRAINT "9_raw_observations_source_metric_id_observed_at_revision_key" UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: raw_observations raw_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.raw_observations
    ADD CONSTRAINT raw_observations_pkey PRIMARY KEY (id, observed_at);


--
-- Name: raw_observations raw_observations_source_metric_id_observed_at_revision_key; Type: CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.raw_observations
    ADD CONSTRAINT raw_observations_source_metric_id_observed_at_revision_key UNIQUE (source, metric_id, observed_at, revision);


--
-- Name: release_log release_log_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.release_log
    ADD CONSTRAINT release_log_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (name);


--
-- Name: _hyper_1_10_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_10_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_10_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_10_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_10_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_10_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_11_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_11_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_11_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_11_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_11_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_11_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_12_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_12_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_12_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_12_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_12_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_12_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_13_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_13_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_13_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_13_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_13_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_13_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_14_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_14_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_14_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_14_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_14_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_14_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_3_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_3_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_3_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_3_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_3_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_3_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_4_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_4_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_4_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_4_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_4_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_4_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_5_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_5_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_5_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_5_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_5_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_5_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_6_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_6_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_6_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_6_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_6_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_6_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_7_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_7_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_7_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_7_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_7_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_7_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_8_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_8_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_8_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_8_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_8_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_8_chunk USING btree (observed_at DESC);


--
-- Name: _hyper_1_9_chunk_idx_raw_observations_lookup; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_9_chunk_idx_raw_observations_lookup ON _timescaledb_internal._hyper_1_9_chunk USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: _hyper_1_9_chunk_raw_observations_observed_at_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: invest_agent
--

CREATE INDEX _hyper_1_9_chunk_raw_observations_observed_at_idx ON _timescaledb_internal._hyper_1_9_chunk USING btree (observed_at DESC);


--
-- Name: idx_raw_observations_lookup; Type: INDEX; Schema: public; Owner: invest_agent
--

CREATE INDEX idx_raw_observations_lookup ON public.raw_observations USING btree (source, metric_id, observed_at DESC, revision DESC);


--
-- Name: raw_observations_observed_at_idx; Type: INDEX; Schema: public; Owner: invest_agent
--

CREATE INDEX raw_observations_observed_at_idx ON public.raw_observations USING btree (observed_at DESC);


--
-- Name: _hyper_1_10_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_11_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_12_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_13_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_14_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_3_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_4_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_5_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_6_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_7_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_8_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: _hyper_1_9_chunk raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: invest_agent
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: raw_observations raw_observations_source_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.raw_observations
    ADD CONSTRAINT raw_observations_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- Name: release_log release_log_source_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_agent
--

ALTER TABLE ONLY public.release_log
    ADD CONSTRAINT release_log_source_fkey FOREIGN KEY (source) REFERENCES public.sources(name);


--
-- PostgreSQL database dump complete
--

\unrestrict 7A9Yc6wSFVvSPOXdvn1NManke8BDdPVno7ZnqSBuS4hG6jgHV5VipLrP5swx2ue


--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET timezone TO 'ROC';
ALTER ROLE db_username SET timezone TO 'ROC';
ALTER DATABASE db_name SET timezone TO 'ROC';

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner:
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner:
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: account; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.account (
    acct_id integer NOT NULL,
    mail character varying,
    name character varying,
    password character varying,
    acct_type integer DEFAULT 3,
    photo character varying DEFAULT ''::character varying,
    cover character varying DEFAULT ''::character varying,
    "group" character varying,
    lastip character varying(64) DEFAULT ''::character varying
);


ALTER TABLE public.account OWNER TO db_username;

--
-- Name: account_acct_id_seq; Type: SEQUENCE; Schema: public; Owner: db_username
--

CREATE SEQUENCE public.account_acct_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.account_acct_id_seq OWNER TO db_username;

--
-- Name: account_acct_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: db_username
--

ALTER SEQUENCE public.account_acct_id_seq OWNED BY public.account.acct_id;


--
-- Name: challenge; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.challenge (
    chal_id integer NOT NULL,
    pro_id integer,
    acct_id integer,
    "timestamp" timestamp with time zone DEFAULT now(),
    compiler_type character varying,
    contest_id integer DEFAULT 0
);


ALTER TABLE public.challenge OWNER TO db_username;

--
-- Name: challenge_chal_id_seq; Type: SEQUENCE; Schema: public; Owner: db_username
--

CREATE SEQUENCE public.challenge_chal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.challenge_chal_id_seq OWNER TO db_username;

--
-- Name: challenge_chal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: db_username
--

ALTER SEQUENCE public.challenge_chal_id_seq OWNED BY public.challenge.chal_id;


--
-- Name: problem; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.problem (
    pro_id integer NOT NULL,
    name character varying,
    status integer,
    expire timestamp with time zone,
    tags character varying
);


ALTER TABLE public.problem OWNER TO db_username;

--
-- Name: test; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.test (
    chal_id integer NOT NULL,
    pro_id integer NOT NULL,
    test_idx integer NOT NULL,
    state integer,
    runtime bigint DEFAULT 0,
    memory bigint DEFAULT 0,
    acct_id integer,
    "timestamp" timestamp with time zone,
    response character varying DEFAULT '{}'::character varying
);


ALTER TABLE public.test OWNER TO db_username;

--
-- Name: test_config; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.test_config (
    pro_id integer NOT NULL,
    test_idx integer NOT NULL,
    compile_type character varying,
    timelimit integer,
    memlimit integer,
    score_type character varying,
    check_type character varying,
    metadata character varying DEFAULT '{}'::character varying,
    weight integer,
    chalmeta character varying DEFAULT '{}'::character varying
);


ALTER TABLE public.test_config OWNER TO db_username;

--
-- Name: test_valid_rate; Type: MATERIALIZED VIEW; Schema: public; Owner: db_username; Tablespace:
--

CREATE MATERIALIZED VIEW public.test_valid_rate AS
 SELECT test_config.pro_id,
    test_config.test_idx,
    count(DISTINCT account.acct_id) AS count,
    test_config.weight AS rate
   FROM (((public.test
     JOIN public.account ON ((test.acct_id = account.acct_id)))
     JOIN public.problem ON (((((test.pro_id = problem.pro_id)) AND (test.state = 1)) AND (age(test."timestamp", problem.expire) < '7 days'::interval))))
     RIGHT JOIN public.test_config ON (((test.pro_id = test_config.pro_id) AND (test.test_idx = test_config.test_idx))))
  GROUP BY test_config.pro_id, test_config.test_idx, test_config.weight
  WITH NO DATA;


ALTER TABLE public.test_valid_rate OWNER TO db_username;

--
-- Name: challenge_state; Type: MATERIALIZED VIEW; Schema: public; Owner: db_username; Tablespace:
--

CREATE MATERIALIZED VIEW public.challenge_state AS
 SELECT test.chal_id,
    max(test.state) AS state,
    sum(test.runtime) AS runtime,
    sum(test.memory) AS memory,
    sum(
        CASE
            WHEN (test.state = 1) THEN test_valid_rate.rate
            ELSE 0
        END) AS rate
   FROM (public.test
     JOIN public.test_valid_rate ON (((test.pro_id = test_valid_rate.pro_id) AND (test.test_idx = test_valid_rate.test_idx))))
  GROUP BY test.chal_id
  WITH NO DATA;


ALTER TABLE public.challenge_state OWNER TO db_username;

--
-- Name: group; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public."group" (
    group_name character varying,
    group_type integer,
    group_class integer
);


ALTER TABLE public."group" OWNER TO db_username;

--
-- Name: log; Type: TABLE; Schema: public; Owner: db_username; Tablespace:
--

CREATE TABLE public.log (
    log_id integer NOT NULL,
    message text,
    "timestamp" timestamp with time zone DEFAULT now(),
    type character varying(64) DEFAULT NULL::character varying,
    params text
);


ALTER TABLE public.log OWNER TO db_username;

--
-- Name: log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: db_username
--

CREATE SEQUENCE public.log_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.log_log_id_seq OWNER TO db_username;

--
-- Name: log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: db_username
--

ALTER SEQUENCE public.log_log_id_seq OWNED BY public.log.log_id;

CREATE SEQUENCE public.problem_pro_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.problem_pro_id_seq OWNER TO db_username;

--
-- Name: problem_pro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: db_username
--

ALTER SEQUENCE public.problem_pro_id_seq OWNED BY public.problem.pro_id;

--- Bulletin
CREATE SEQUENCE public.bulletin_bulletin_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER TABLE IF EXISTS public.bulletin_bulletin_id_seq OWNER TO db_username;

CREATE TABLE public.bulletin (
    bulletin_id integer NOT NULL DEFAULT nextval('public.bulletin_bulletin_id_seq'::regclass),
    title text,
    content text,
    "timestamp" timestamp with time zone DEFAULT now(),
    color character varying(16) DEFAULT NULL::character varying,
    author_id integer NOT NULL,
    pinned boolean DEFAULT false
);
ALTER TABLE public.bulletin OWNER TO db_username;
ALTER SEQUENCE public.bulletin_bulletin_id_seq OWNED BY PUBLIC.bulletin.bulletin_id;
--- Bulletin end

--- PubClass
CREATE SEQUENCE IF NOT EXISTS public.pubclass_pubclass_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    CACHE 1;
ALTER SEQUENCE public.pubclass_pubclass_id_seq OWNER TO db_username;

CREATE TABLE IF NOT EXISTS public.pubclass
(
    pubclass_id integer NOT NULL DEFAULT nextval('public.pubclass_pubclass_id_seq'::regclass),
    name text COLLATE pg_catalog."default" NOT NULL,
    list integer[] NOT NULL,
    CONSTRAINT pubclass_pkey PRIMARY KEY (pubclass_id)
);
ALTER TABLE IF EXISTS public.pubclass OWNER to db_username;
ALTER SEQUENCE IF EXISTS public.pubclass_pubclass_id_seq OWNED BY PUBLIC.pubclass.pubclass_id;
--- PubClass end

--- Board
CREATE SEQUENCE IF NOT EXISTS public.board_board_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    CACHE 1;
ALTER SEQUENCE IF EXISTS public.board_board_id_seq OWNER TO db_username;

CREATE TABLE IF NOT EXISTS public.board (
    board_id integer NOT NULL DEFAULT nextval('public.board_board_id_seq'::regclass),
    name text COLLATE pg_catalog."default" NOT NULL,
    status integer NOT NULL,
    start timestamp with time zone,
    "end" timestamp with time zone,
    pro_list integer[] NOT NULL,
    acct_list integer[] NOT NULL,
    CONSTRAINT board_pkey PRIMARY KEY (board_id)
);
ALTER TABLE IF EXISTS public.board OWNER TO db_username;
ALTER SEQUENCE public.pubclass_pubclass_id_seq OWNED BY PUBLIC.board.board_id;
--- Board end

--- Contest
CREATE SEQUENCE IF NOT EXISTS public.contest_contest_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    CACHE 1;

ALTER SEQUENCE IF EXISTS public.contest_contest_id_seq OWNER TO db_username;

CREATE TABLE IF NOT EXISTS public.contest (
    contest_id integer NOT NULL DEFAULT nextval('public.contest_contest_id_seq'::regclass),
    name text COLLATE pg_catalog."default" NOT NULL,
    "desc_before_contest" character varying DEFAULT ''::character varying,
    "desc_during_contest" character varying DEFAULT ''::character varying,
    "desc_after_contest" character varying DEFAULT ''::character varying,
--    contest_status integer NOT NULL,
    contest_mode integer NOT NULL DEFAULT 0, -- 0: IOI 1: ACM
    contest_start timestamp with time zone NOT NULL DEFAULT now(),
    contest_end timestamp with time zone NOT NULL DEFAULT now(),

    pro_list integer[] NOT NULL DEFAULT '{}'::integer[],
    acct_list integer[] NOT NULL DEFAULT '{}'::integer[],
    admin_list integer[] NOT NULL,

    reg_mode integer NOT NULL DEFAULT 0, -- 0: INVITED 1: FREE_REG 2: REG_APPROVAL
    reg_list integer[] DEFAULT '{}'::integer[],
    reg_end timestamp with time zone NOT NULL DEFAULT now(),

    -- limit
    allow_compilers varchar[] NOT NULL DEFAULT array[]::varchar[],
    is_public_scoreboard boolean NOT NULL DEFAULT true,
    allow_view_other_page boolean NOT NULL DEFAULT false,
    hide_admin boolean NOT NULL DEFAULT true,
    submission_cd_time integer NOT NULL DEFAULT 30,
    freeze_scoreboard_period integer NOT NULL DEFAULT 0,

    CONSTRAINT contest_pkey PRIMARY KEY (contest_id)
);
ALTER TABLE IF EXISTS public.contest OWNER TO db_username;
ALTER SEQUENCE public.contest_contest_id_seq OWNED BY PUBLIC.contest.contest_id;
--- Contest end

--
-- Name: acct_id; Type: DEFAULT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.account ALTER COLUMN acct_id SET DEFAULT nextval('public.account_acct_id_seq'::regclass);


--
-- Name: chal_id; Type: DEFAULT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.challenge ALTER COLUMN chal_id SET DEFAULT nextval('public.challenge_chal_id_seq'::regclass);


--
-- Name: log_id; Type: DEFAULT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.log ALTER COLUMN log_id SET DEFAULT nextval('public.log_log_id_seq'::regclass);


--
-- Name: pro_id; Type: DEFAULT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.problem ALTER COLUMN pro_id SET DEFAULT nextval('public.problem_pro_id_seq'::regclass);


--
-- Data for Name: account; Type: TABLE DATA; Schema: public; Owner: db_username
--



--
-- Name: account_acct_id_seq; Type: SEQUENCE SET; Schema: public; Owner: db_username
--



--
-- Data for Name: challenge; Type: TABLE DATA; Schema: public; Owner: db_username
--



--
-- Name: challenge_chal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: db_username
--



--
-- Data for Name: group; Type: TABLE DATA; Schema: public; Owner: db_username
--

--
-- Data for Name: log; Type: TABLE DATA; Schema: public; Owner: db_username
--


--
-- Name: log_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: db_username
--

--
-- Data for Name: moodle; Type: TABLE DATA; Schema: public; Owner: db_username
--



--
-- Data for Name: problem; Type: TABLE DATA; Schema: public; Owner: db_username
--



--
-- Name: problem_pro_id_seq; Type: SEQUENCE SET; Schema: public; Owner: db_username
--



--
-- Data for Name: test; Type: TABLE DATA; Schema: public; Owner: db_username
--



--
-- Data for Name: test_config; Type: TABLE DATA; Schema: public; Owner: db_username
--
--
-- Name: account_mail_key; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_mail_key UNIQUE (mail);


--
-- Name: account_pkey; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (acct_id);


--
-- Name: challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.challenge
    ADD CONSTRAINT challenge_pkey PRIMARY KEY (chal_id);


--
-- Name: problem_pkey; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.problem
    ADD CONSTRAINT problem_pkey PRIMARY KEY (pro_id);


--
-- Name: test_config_pkey; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.test_config
    ADD CONSTRAINT test_config_pkey PRIMARY KEY (pro_id, test_idx);


--
-- Name: test_pkey; Type: CONSTRAINT; Schema: public; Owner: db_username; Tablespace:
--

ALTER TABLE ONLY public.test
    ADD CONSTRAINT test_pkey PRIMARY KEY (chal_id, pro_id, test_idx);


ALTER TABLE ONLY public.bulletin
    ADD CONSTRAINT bulletin_pkey PRIMARY KEY (bulletin_id);


--
-- Name: challenge_idx_acct_id; Type: INDEX; Schema: public; Owner: db_username; Tablespace:
--

CREATE INDEX challenge_idx_acct_id ON public.challenge USING btree (acct_id);


--
-- Name: challenge_idx_pro_id; Type: INDEX; Schema: public; Owner: db_username; Tablespace:
--

CREATE INDEX challenge_idx_pro_id ON public.challenge USING btree (pro_id);


--
-- Name: test_idx_acct_id; Type: INDEX; Schema: public; Owner: db_username; Tablespace:
--

CREATE INDEX test_idx_acct_id ON public.test USING btree (acct_id);


--
-- Name: challenge_forkey_acct_id; Type: FK CONSTRAINT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.challenge
    ADD CONSTRAINT challenge_forkey_acct_id FOREIGN KEY (acct_id) REFERENCES public.account(acct_id) ON DELETE CASCADE;


--
-- Name: challenge_forkey_pro_id; Type: FK CONSTRAINT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.challenge
    ADD CONSTRAINT challenge_forkey_pro_id FOREIGN KEY (pro_id) REFERENCES public.problem(pro_id) ON DELETE CASCADE;


--
-- Name: test_forkey_acct_id; Type: FK CONSTRAINT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.test
    ADD CONSTRAINT test_forkey_acct_id FOREIGN KEY (acct_id) REFERENCES public.account(acct_id) ON DELETE CASCADE;


--
-- Name: test_forkey_chal_id; Type: FK CONSTRAINT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.test
    ADD CONSTRAINT test_forkey_chal_id FOREIGN KEY (chal_id) REFERENCES public.challenge(chal_id) ON DELETE CASCADE;


--
-- Name: test_forkey_pro_id_test_idx; Type: FK CONSTRAINT; Schema: public; Owner: db_username
--

ALTER TABLE ONLY public.test
    ADD CONSTRAINT test_forkey_pro_id_test_idx FOREIGN KEY (pro_id, test_idx) REFERENCES public.test_config(pro_id, test_idx) ON DELETE CASCADE;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: test_valid_rate; Type: MATERIALIZED VIEW DATA; Schema: public; Owner: db_username
--

REFRESH MATERIALIZED VIEW public.test_valid_rate;


--
-- Name: challenge_state; Type: MATERIALIZED VIEW DATA; Schema: public; Owner: db_username
--

REFRESH MATERIALIZED VIEW public.challenge_state;


--
-- PostgreSQL database dump complete
--

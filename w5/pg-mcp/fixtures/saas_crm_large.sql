-- Dataset: saas_crm_large
-- Goal: large, multi-schema SaaS + CRM benchmark with many objects and high row volume.

SET client_min_messages = warning;
BEGIN;

CREATE SCHEMA core;
CREATE SCHEMA sales;
CREATE SCHEMA billing;
CREATE SCHEMA engagement;
CREATE SCHEMA platform;
CREATE SCHEMA analytics;

CREATE TYPE core.account_tier AS ENUM ('startup', 'growth', 'enterprise');
CREATE TYPE core.user_role AS ENUM ('rep', 'manager', 'csm', 'admin');
CREATE TYPE core.user_state AS ENUM ('active', 'inactive', 'leave');
CREATE TYPE sales.lead_status AS ENUM ('new', 'working', 'qualified', 'disqualified');
CREATE TYPE sales.oppty_stage AS ENUM ('prospecting', 'discovery', 'proposal', 'negotiation', 'won', 'lost');
CREATE TYPE sales.activity_type AS ENUM ('call', 'email', 'meeting', 'demo', 'note');
CREATE TYPE sales.ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE billing.sub_state AS ENUM ('trial', 'active', 'past_due', 'canceled');
CREATE TYPE billing.invoice_state AS ENUM ('issued', 'paid', 'overdue', 'void');
CREATE TYPE engagement.channel_kind AS ENUM ('email', 'paid_search', 'social', 'webinar', 'partner');
CREATE TYPE engagement.event_kind AS ENUM ('login', 'feature_use', 'export', 'api_call', 'error');
CREATE TYPE platform.integration_state AS ENUM ('active', 'paused', 'disabled');
CREATE TYPE platform.job_state AS ENUM ('queued', 'running', 'success', 'failed');

CREATE TABLE core.region (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE core.tenant (
    id BIGSERIAL PRIMARY KEY,
    tenant_key TEXT NOT NULL UNIQUE,
    tenant_name TEXT NOT NULL,
    tier core.account_tier NOT NULL,
    region_code TEXT NOT NULL REFERENCES core.region(code),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.app_user (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role core.user_role NOT NULL,
    state core.user_state NOT NULL DEFAULT 'active',
    manager_id BIGINT REFERENCES core.app_user(id),
    hired_at DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.team (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    team_name TEXT NOT NULL,
    manager_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.team_member (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES core.team(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES core.app_user(id) ON DELETE CASCADE,
    joined_at DATE NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (team_id, user_id)
);

CREATE TABLE sales.account (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    account_name TEXT NOT NULL,
    tier core.account_tier NOT NULL,
    industry TEXT NOT NULL,
    employee_count INTEGER NOT NULL CHECK (employee_count > 0),
    arr NUMERIC(14, 2) NOT NULL CHECK (arr >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sales.account_contact (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    title TEXT NOT NULL,
    is_decision_maker BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sales.lead_source (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    channel engagement.channel_kind NOT NULL
);

CREATE TABLE sales.lead (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    source_id BIGINT NOT NULL REFERENCES sales.lead_source(id),
    account_id BIGINT REFERENCES sales.account(id),
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    lead_name TEXT NOT NULL,
    email TEXT NOT NULL,
    status sales.lead_status NOT NULL,
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    qualified_at TIMESTAMPTZ
);

CREATE TABLE sales.opportunity (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    stage sales.oppty_stage NOT NULL,
    amount NUMERIC(14, 2) NOT NULL CHECK (amount >= 0),
    probability_pct SMALLINT NOT NULL CHECK (probability_pct BETWEEN 0 AND 100),
    expected_close_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sales.activity (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    contact_id BIGINT REFERENCES sales.account_contact(id),
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    activity_type sales.activity_type NOT NULL,
    activity_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK (duration_minutes >= 0),
    outcome TEXT
);

CREATE TABLE sales.ticket (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    contact_id BIGINT REFERENCES sales.account_contact(id),
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    priority sales.ticket_priority NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'pending', 'resolved', 'closed')),
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ
);

CREATE TABLE billing.plan (
    id BIGSERIAL PRIMARY KEY,
    plan_code TEXT NOT NULL UNIQUE,
    tier core.account_tier NOT NULL,
    interval_label TEXT NOT NULL CHECK (interval_label IN ('monthly', 'quarterly', 'yearly')),
    list_price NUMERIC(12, 2) NOT NULL CHECK (list_price >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE billing.subscription (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    plan_id BIGINT NOT NULL REFERENCES billing.plan(id),
    state billing.sub_state NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    seats INTEGER NOT NULL CHECK (seats > 0),
    mrr NUMERIC(12, 2) NOT NULL CHECK (mrr >= 0)
);

CREATE TABLE billing.invoice (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES billing.subscription(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    invoice_no TEXT NOT NULL UNIQUE,
    state billing.invoice_state NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE billing.payment (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES billing.invoice(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('stripe', 'adyen', 'wire')),
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'pending')),
    paid_at TIMESTAMPTZ,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    reference_no TEXT NOT NULL UNIQUE
);

CREATE TABLE engagement.campaign (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    owner_user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    campaign_name TEXT NOT NULL,
    channel engagement.channel_kind NOT NULL,
    budget NUMERIC(12, 2) NOT NULL CHECK (budget >= 0),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'running', 'paused', 'completed'))
);

CREATE TABLE engagement.campaign_member (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES engagement.campaign(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    contact_id BIGINT REFERENCES sales.account_contact(id),
    member_status TEXT NOT NULL CHECK (member_status IN ('targeted', 'responded', 'qualified', 'converted')),
    joined_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE engagement.email_event (
    id BIGSERIAL PRIMARY KEY,
    campaign_member_id BIGINT NOT NULL REFERENCES engagement.campaign_member(id) ON DELETE CASCADE,
    template_key TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    bounced BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE engagement.product_event (
    id BIGSERIAL NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES core.app_user(id),
    kind engagement.event_kind NOT NULL,
    event_name TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE platform.integration (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    integration_name TEXT NOT NULL,
    state platform.integration_state NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_sync_at TIMESTAMPTZ
);

CREATE TABLE platform.sync_job (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT NOT NULL REFERENCES platform.integration(id) ON DELETE CASCADE,
    state platform.job_state NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    rows_scanned INTEGER NOT NULL DEFAULT 0,
    rows_written INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE platform.webhook_endpoint (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(id) ON DELETE CASCADE,
    endpoint_url TEXT NOT NULL,
    secret_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE platform.webhook_delivery (
    id BIGSERIAL PRIMARY KEY,
    endpoint_id BIGINT NOT NULL REFERENCES platform.webhook_endpoint(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL,
    status_code INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    response_ms INTEGER NOT NULL CHECK (response_ms >= 0),
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    payload_size INTEGER NOT NULL CHECK (payload_size >= 0)
);

CREATE TABLE platform.api_token (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES core.app_user(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('read', 'write', 'admin')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE analytics.daily_account_metric (
    id BIGSERIAL NOT NULL,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    active_users INTEGER NOT NULL CHECK (active_users >= 0),
    events_count INTEGER NOT NULL CHECK (events_count >= 0),
    seats_in_use INTEGER NOT NULL CHECK (seats_in_use >= 0),
    expansion_mrr NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (expansion_mrr >= 0),
    contraction_mrr NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (contraction_mrr >= 0),
    churned BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id, metric_date)
) PARTITION BY RANGE (metric_date);

CREATE TABLE analytics.prediction (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES sales.account(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    predicted_label TEXT NOT NULL,
    score NUMERIC(6, 5) NOT NULL CHECK (score BETWEEN 0 AND 1),
    predicted_at TIMESTAMPTZ NOT NULL,
    features JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE analytics.rep_quota (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES core.app_user(id) ON DELETE CASCADE,
    quota_month DATE NOT NULL,
    target_arr NUMERIC(14, 2) NOT NULL CHECK (target_arr >= 0),
    UNIQUE (user_id, quota_month)
);

CREATE TABLE analytics.rep_quota_attainment (
    id BIGSERIAL PRIMARY KEY,
    quota_id BIGINT NOT NULL UNIQUE REFERENCES analytics.rep_quota(id) ON DELETE CASCADE,
    attained_arr NUMERIC(14, 2) NOT NULL CHECK (attained_arr >= 0),
    pipeline_arr NUMERIC(14, 2) NOT NULL CHECK (pipeline_arr >= 0),
    win_rate NUMERIC(5, 2) NOT NULL CHECK (win_rate BETWEEN 0 AND 100)
);

DO $$
DECLARE
    d DATE := DATE '2023-01-01';
    d_next DATE;
BEGIN
    WHILE d < DATE '2027-01-01' LOOP
        d_next := (d + INTERVAL '1 month')::DATE;
        EXECUTE format(
            'CREATE TABLE engagement.product_event_%s PARTITION OF engagement.product_event FOR VALUES FROM (%L) TO (%L);',
            to_char(d, 'YYYYMM'),
            d,
            d_next
        );
        EXECUTE format(
            'CREATE TABLE analytics.daily_account_metric_%s PARTITION OF analytics.daily_account_metric FOR VALUES FROM (%L) TO (%L);',
            to_char(d, 'YYYYMM'),
            d,
            d_next
        );
        d := d_next;
    END LOOP;
END $$;
INSERT INTO core.region (code, name) VALUES
('NA-E', 'North America East'),
('NA-W', 'North America West'),
('EU-N', 'Europe North'),
('EU-S', 'Europe South'),
('AP-JP', 'Asia Pacific Japan'),
('AP-SG', 'Asia Pacific Singapore'),
('LATAM', 'Latin America'),
('MEA', 'Middle East and Africa');

INSERT INTO core.tenant (tenant_key, tenant_name, tier, region_code, is_active, created_at)
SELECT
    format('tenant_%s', gs),
    format('Tenant %s', gs),
    CASE WHEN gs <= 45 THEN 'startup' WHEN gs <= 95 THEN 'growth' ELSE 'enterprise' END::core.account_tier,
    (ARRAY['NA-E', 'NA-W', 'EU-N', 'EU-S', 'AP-JP', 'AP-SG', 'LATAM', 'MEA'])[(gs % 8) + 1],
    gs % 23 <> 0,
    now() - ((gs % 1400) || ' days')::interval
FROM generate_series(1, 120) AS gs;

INSERT INTO core.app_user (tenant_id, email, full_name, role, state, manager_id, hired_at, created_at)
SELECT
    ((gs - 1) % 120) + 1,
    format('user_%s@tenant.local', gs),
    format('User %s', gs),
    CASE WHEN gs % 16 = 0 THEN 'admin' WHEN gs % 5 = 0 THEN 'manager' WHEN gs % 3 = 0 THEN 'csm' ELSE 'rep' END::core.user_role,
    CASE WHEN gs % 41 = 0 THEN 'leave' WHEN gs % 19 = 0 THEN 'inactive' ELSE 'active' END::core.user_state,
    CASE WHEN gs <= 150 THEN NULL ELSE ((gs - 1) % 150) + 1 END,
    date '2018-01-01' + ((gs * 7) % 2500),
    now() - ((gs % 2200) || ' days')::interval
FROM generate_series(1, 22000) AS gs;

INSERT INTO core.team (tenant_id, team_name, manager_user_id, created_at)
SELECT
    ((gs - 1) % 120) + 1,
    format('Team %s', gs),
    ((gs * 11) % 22000) + 1,
    now() - ((gs % 1500) || ' days')::interval
FROM generate_series(1, 2200) AS gs;

INSERT INTO core.team_member (team_id, user_id, joined_at, is_primary)
SELECT
    ((gs - 1) % 2200) + 1,
    ((gs * 17) % 22000) + 1,
    date '2020-01-01' + ((gs * 3) % 1800),
    gs % 7 = 0
FROM generate_series(1, 90000) AS gs
ON CONFLICT (team_id, user_id) DO NOTHING;

INSERT INTO sales.account (tenant_id, owner_user_id, account_name, tier, industry, employee_count, arr, created_at)
SELECT
    ((gs - 1) % 120) + 1,
    ((gs * 13) % 22000) + 1,
    format('Account %s', gs),
    CASE WHEN gs % 10 < 4 THEN 'startup' WHEN gs % 10 < 8 THEN 'growth' ELSE 'enterprise' END::core.account_tier,
    (ARRAY['SaaS', 'FinTech', 'Retail', 'Health', 'Media', 'Manufacturing'])[(gs % 6) + 1],
    15 + ((gs * 7) % 12000),
    ((gs % 900000) + 5000)::numeric / 10,
    now() - ((gs % 2000) || ' days')::interval
FROM generate_series(1, 30000) AS gs;

INSERT INTO sales.account_contact (account_id, full_name, email, title, is_decision_maker, created_at)
SELECT
    ((gs - 1) % 30000) + 1,
    format('Contact %s', gs),
    format('contact_%s@account.local', gs),
    (ARRAY['VP IT', 'Director Ops', 'Finance Lead', 'Manager', 'Admin'])[(gs % 5) + 1],
    gs % 5 = 0,
    now() - ((gs % 1800) || ' days')::interval
FROM generate_series(1, 90000) AS gs;

INSERT INTO sales.lead_source (source_name, channel) VALUES
('organic_search', 'paid_search'),
('content_download', 'webinar'),
('partner_referral', 'partner'),
('newsletter', 'email'),
('linkedin_ads', 'social'),
('cold_outreach', 'email'),
('community_event', 'webinar'),
('customer_referral', 'partner'),
('brand_campaign', 'social'),
('website_signup', 'paid_search');

INSERT INTO sales.lead (tenant_id, source_id, account_id, owner_user_id, lead_name, email, status, score, created_at, qualified_at)
SELECT
    ((gs - 1) % 120) + 1,
    ((gs - 1) % 10) + 1,
    CASE WHEN gs % 5 = 0 THEN NULL ELSE ((gs - 1) % 30000) + 1 END,
    ((gs * 19) % 22000) + 1,
    format('Lead %s', gs),
    format('lead_%s@prospect.local', gs),
    CASE WHEN gs % 11 = 0 THEN 'disqualified' WHEN gs % 7 = 0 THEN 'qualified' WHEN gs % 3 = 0 THEN 'working' ELSE 'new' END::sales.lead_status,
    (gs * 7) % 101,
    now() - ((gs % 900) || ' days')::interval,
    CASE WHEN gs % 7 = 0 THEN now() - ((gs % 600) || ' days')::interval ELSE NULL END
FROM generate_series(1, 180000) AS gs;

INSERT INTO sales.opportunity (account_id, owner_user_id, stage, amount, probability_pct, expected_close_date, created_at)
SELECT
    ((gs - 1) % 30000) + 1,
    ((gs * 23) % 22000) + 1,
    CASE
        WHEN gs % 17 = 0 THEN 'lost'
        WHEN gs % 13 = 0 THEN 'won'
        WHEN gs % 5 = 0 THEN 'negotiation'
        WHEN gs % 4 = 0 THEN 'proposal'
        WHEN gs % 3 = 0 THEN 'discovery'
        ELSE 'prospecting'
    END::sales.oppty_stage,
    ((gs % 700000) + 5000)::numeric / 10,
    (gs * 3) % 101,
    current_date + ((gs % 120) - 60),
    now() - ((gs % 700) || ' days')::interval
FROM generate_series(1, 70000) AS gs;

INSERT INTO sales.activity (tenant_id, account_id, contact_id, owner_user_id, activity_type, activity_at, duration_minutes, outcome)
SELECT
    ((gs - 1) % 120) + 1,
    ((gs - 1) % 30000) + 1,
    ((gs * 19) % 90000) + 1,
    ((gs * 31) % 22000) + 1,
    CASE
        WHEN gs % 5 = 0 THEN 'meeting'
        WHEN gs % 5 = 1 THEN 'call'
        WHEN gs % 5 = 2 THEN 'email'
        WHEN gs % 5 = 3 THEN 'demo'
        ELSE 'note'
    END::sales.activity_type,
    now() - ((gs % 540) || ' days')::interval,
    (gs * 7) % 120,
    CASE WHEN gs % 6 = 0 THEN 'positive' WHEN gs % 6 = 1 THEN 'neutral' ELSE NULL END
FROM generate_series(1, 500000) AS gs;

INSERT INTO sales.ticket (account_id, contact_id, owner_user_id, priority, state, opened_at, closed_at)
SELECT
    ((gs - 1) % 30000) + 1,
    ((gs * 11) % 90000) + 1,
    ((gs * 41) % 22000) + 1,
    CASE WHEN gs % 20 = 0 THEN 'urgent' WHEN gs % 8 = 0 THEN 'high' WHEN gs % 3 = 0 THEN 'medium' ELSE 'low' END::sales.ticket_priority,
    CASE WHEN gs % 6 = 0 THEN 'closed' WHEN gs % 5 = 0 THEN 'resolved' WHEN gs % 4 = 0 THEN 'pending' ELSE 'open' END,
    now() - ((gs % 600) || ' days')::interval,
    CASE WHEN gs % 6 = 0 OR gs % 5 = 0 THEN now() - ((gs % 580) || ' days')::interval ELSE NULL END
FROM generate_series(1, 160000) AS gs;

INSERT INTO billing.plan (plan_code, tier, interval_label, list_price, active)
SELECT
    format('PLAN-%02s', gs),
    CASE WHEN gs % 3 = 0 THEN 'enterprise' WHEN gs % 3 = 1 THEN 'startup' ELSE 'growth' END::core.account_tier,
    CASE WHEN gs % 3 = 0 THEN 'yearly' WHEN gs % 3 = 1 THEN 'monthly' ELSE 'quarterly' END,
    ((gs % 5000) + 200)::numeric / 10,
    gs % 10 <> 0
FROM generate_series(1, 30) AS gs;

INSERT INTO billing.subscription (account_id, plan_id, state, started_at, period_start, period_end, seats, mrr)
SELECT
    ((gs - 1) % 30000) + 1,
    ((gs - 1) % 30) + 1,
    CASE WHEN gs % 20 = 0 THEN 'canceled' WHEN gs % 9 = 0 THEN 'past_due' WHEN gs % 7 = 0 THEN 'trial' ELSE 'active' END::billing.sub_state,
    now() - ((gs % 1200) || ' days')::interval,
    now() - ((gs % 30) || ' days')::interval,
    now() + ((30 - (gs % 10)) || ' days')::interval,
    5 + ((gs * 3) % 1200),
    ((gs % 30000) + 200)::numeric / 10
FROM generate_series(1, 100000) AS gs;

INSERT INTO billing.invoice (subscription_id, account_id, invoice_no, state, issued_at, due_at, paid_at, total_amount)
SELECT
    ((gs - 1) % 100000) + 1,
    ((gs - 1) % 30000) + 1,
    format('INV-%09s', gs),
    CASE WHEN gs % 17 = 0 THEN 'void' WHEN gs % 13 = 0 THEN 'overdue' WHEN gs % 3 = 0 THEN 'paid' ELSE 'issued' END::billing.invoice_state,
    now() - ((gs % 800) || ' days')::interval,
    now() - (((gs % 800) - 30) || ' days')::interval,
    CASE WHEN gs % 3 = 0 THEN now() - ((gs % 760) || ' days')::interval ELSE NULL END,
    ((gs % 90000) + 1000)::numeric / 10
FROM generate_series(1, 300000) AS gs;

INSERT INTO billing.payment (invoice_id, provider, status, paid_at, amount, reference_no)
SELECT
    ((gs - 1) % 300000) + 1,
    CASE WHEN gs % 3 = 0 THEN 'stripe' WHEN gs % 3 = 1 THEN 'adyen' ELSE 'wire' END,
    CASE WHEN gs % 11 = 0 THEN 'failed' WHEN gs % 7 = 0 THEN 'pending' ELSE 'succeeded' END,
    CASE WHEN gs % 11 = 0 OR gs % 7 = 0 THEN NULL ELSE now() - ((gs % 730) || ' days')::interval END,
    ((gs % 85000) + 300)::numeric / 10,
    format('PAY-%09s', gs)
FROM generate_series(1, 260000) AS gs;
INSERT INTO engagement.campaign (tenant_id, owner_user_id, campaign_name, channel, budget, start_at, end_at, status)
SELECT
    ((gs - 1) % 120) + 1,
    ((gs * 47) % 22000) + 1,
    format('Campaign %s', gs),
    (ARRAY['email', 'paid_search', 'social', 'webinar', 'partner'])[(gs % 5) + 1]::engagement.channel_kind,
    ((gs % 400000) + 1000)::numeric / 10,
    now() - ((gs % 500) || ' days')::interval,
    now() + ((30 + (gs % 120)) || ' days')::interval,
    CASE WHEN gs % 9 = 0 THEN 'paused' WHEN gs % 7 = 0 THEN 'completed' WHEN gs % 5 = 0 THEN 'draft' ELSE 'running' END
FROM generate_series(1, 3200) AS gs;

INSERT INTO engagement.campaign_member (campaign_id, account_id, contact_id, member_status, joined_at)
SELECT
    ((gs - 1) % 3200) + 1,
    ((gs - 1) % 30000) + 1,
    ((gs * 13) % 90000) + 1,
    CASE WHEN gs % 8 = 0 THEN 'converted' WHEN gs % 5 = 0 THEN 'qualified' WHEN gs % 3 = 0 THEN 'responded' ELSE 'targeted' END,
    now() - ((gs % 420) || ' days')::interval
FROM generate_series(1, 300000) AS gs;

INSERT INTO engagement.email_event (campaign_member_id, template_key, sent_at, opened_at, clicked_at, bounced)
SELECT
    ((gs - 1) % 300000) + 1,
    format('template_%s', (gs % 40) + 1),
    now() - ((gs % 360) || ' days')::interval,
    CASE WHEN gs % 4 = 0 THEN now() - ((gs % 350) || ' days')::interval ELSE NULL END,
    CASE WHEN gs % 6 = 0 THEN now() - ((gs % 340) || ' days')::interval ELSE NULL END,
    gs % 37 = 0
FROM generate_series(1, 500000) AS gs;

INSERT INTO engagement.product_event (tenant_id, account_id, user_id, kind, event_name, occurred_at, properties)
SELECT
    ((gs - 1) % 120) + 1,
    ((gs - 1) % 30000) + 1,
    ((gs * 53) % 22000) + 1,
    CASE WHEN gs % 5 = 0 THEN 'api_call' WHEN gs % 5 = 1 THEN 'login' WHEN gs % 5 = 2 THEN 'feature_use' WHEN gs % 5 = 3 THEN 'export' ELSE 'error' END::engagement.event_kind,
    format('event_%s', (gs % 120) + 1),
    (timestamp '2023-01-01' + ((gs % 1460) || ' days')::interval) + ((gs % 86400) || ' seconds')::interval,
    jsonb_build_object('seq', gs, 'latency_ms', (gs % 2000))
FROM generate_series(1, 900000) AS gs;

INSERT INTO platform.integration (tenant_id, integration_name, state, created_at, last_sync_at)
SELECT
    ((gs - 1) % 120) + 1,
    format('integration_%s', (gs % 60) + 1),
    CASE WHEN gs % 13 = 0 THEN 'disabled' WHEN gs % 7 = 0 THEN 'paused' ELSE 'active' END::platform.integration_state,
    now() - ((gs % 1400) || ' days')::interval,
    now() - ((gs % 40) || ' days')::interval
FROM generate_series(1, 15000) AS gs;

INSERT INTO platform.sync_job (integration_id, state, started_at, finished_at, rows_scanned, rows_written, error_message)
SELECT
    ((gs - 1) % 15000) + 1,
    CASE WHEN gs % 17 = 0 THEN 'failed' WHEN gs % 5 = 0 THEN 'running' WHEN gs % 3 = 0 THEN 'queued' ELSE 'success' END::platform.job_state,
    now() - ((gs % 200) || ' days')::interval,
    CASE WHEN gs % 17 = 0 OR gs % 5 = 0 OR gs % 3 = 0 THEN NULL ELSE now() - ((gs % 199) || ' days')::interval END,
    (gs * 13) % 200000,
    (gs * 11) % 150000,
    CASE WHEN gs % 17 = 0 THEN 'upstream timeout' ELSE NULL END
FROM generate_series(1, 350000) AS gs;

INSERT INTO platform.webhook_endpoint (tenant_id, endpoint_url, secret_hash, is_active, created_at)
SELECT
    ((gs - 1) % 120) + 1,
    format('https://hooks.example.com/%s', gs),
    format('secret_%s', gs),
    gs % 9 <> 0,
    now() - ((gs % 900) || ' days')::interval
FROM generate_series(1, 22000) AS gs;

INSERT INTO platform.webhook_delivery (endpoint_id, event_type, delivered_at, status_code, response_ms, retry_count, payload_size)
SELECT
    ((gs - 1) % 22000) + 1,
    format('event.%s', (gs % 30) + 1),
    now() - ((gs % 240) || ' days')::interval - ((gs % 86400) || ' seconds')::interval,
    CASE WHEN gs % 20 = 0 THEN 500 WHEN gs % 11 = 0 THEN 429 ELSE 200 END,
    20 + ((gs * 7) % 6000),
    CASE WHEN gs % 20 = 0 THEN 4 WHEN gs % 11 = 0 THEN 2 ELSE 0 END,
    200 + ((gs * 17) % 50000)
FROM generate_series(1, 350000) AS gs;

INSERT INTO platform.api_token (user_id, scope, token_hash, created_at, expires_at, revoked_at)
SELECT
    ((gs - 1) % 22000) + 1,
    CASE WHEN gs % 10 = 0 THEN 'admin' WHEN gs % 3 = 0 THEN 'write' ELSE 'read' END,
    format('tok_%s', gs),
    now() - ((gs % 800) || ' days')::interval,
    now() + ((30 + (gs % 365)) || ' days')::interval,
    CASE WHEN gs % 21 = 0 THEN now() - ((gs % 120) || ' days')::interval ELSE NULL END
FROM generate_series(1, 85000) AS gs;

INSERT INTO analytics.daily_account_metric (
    account_id, metric_date, active_users, events_count, seats_in_use,
    expansion_mrr, contraction_mrr, churned
)
SELECT
    ((gs - 1) % 30000) + 1,
    (date '2023-01-01' + (gs % 1460)),
    1 + ((gs * 5) % 800),
    (gs * 37) % 40000,
    1 + ((gs * 11) % 1200),
    CASE WHEN gs % 10 = 0 THEN ((gs % 15000) + 100)::numeric / 100 ELSE 0::numeric END,
    CASE WHEN gs % 17 = 0 THEN ((gs % 9000) + 100)::numeric / 100 ELSE 0::numeric END,
    gs % 97 = 0
FROM generate_series(1, 420000) AS gs;

INSERT INTO analytics.prediction (account_id, model_name, predicted_label, score, predicted_at, features)
SELECT
    ((gs - 1) % 30000) + 1,
    'churn_v3',
    CASE WHEN gs % 5 = 0 THEN 'churn' ELSE 'retain' END,
    ((gs * 13) % 100000)::numeric / 100000,
    now() - ((gs % 180) || ' days')::interval,
    jsonb_build_object('usage_drop_pct', (gs % 70), 'ticket_volume', (gs % 35))
FROM generate_series(1, 220000) AS gs;

INSERT INTO analytics.rep_quota (user_id, quota_month, target_arr)
SELECT
    ((gs - 1) % 1200) + 1,
    date_trunc('month', date '2025-01-01' + (((gs - 1) % 12) * interval '1 month'))::date,
    ((gs % 900000) + 50000)::numeric / 10
FROM generate_series(1, 18000) AS gs
ON CONFLICT (user_id, quota_month) DO NOTHING;

INSERT INTO analytics.rep_quota_attainment (quota_id, attained_arr, pipeline_arr, win_rate)
SELECT
    q.id,
    q.target_arr * ((70 + (q.id % 61))::numeric / 100),
    q.target_arr * ((90 + (q.id % 101))::numeric / 100),
    ((q.id * 7) % 10000)::numeric / 100
FROM analytics.rep_quota AS q;

CREATE OR REPLACE FUNCTION analytics.fn_account_health_score(p_account_id BIGINT)
RETURNS NUMERIC
LANGUAGE SQL
STABLE
AS $$
SELECT COALESCE(
    (
        SELECT
            100
            - (avg(CASE WHEN d.churned THEN 1 ELSE 0 END)::numeric * 100)
            - least(35, avg(d.contraction_mrr) / NULLIF(avg(d.expansion_mrr) + 1, 0))
        FROM analytics.daily_account_metric AS d
        WHERE d.account_id = p_account_id
          AND d.metric_date >= current_date - 90
    ),
    0
);
$$;
CREATE VIEW sales.v_pipeline_by_stage AS
SELECT
    stage,
    count(*) AS opportunity_count,
    sum(amount) AS pipeline_amount,
    avg(probability_pct)::numeric(6, 2) AS avg_probability
FROM sales.opportunity
GROUP BY stage;

CREATE VIEW sales.v_rep_activity_30d AS
SELECT
    owner_user_id,
    count(*) AS activities,
    count(*) FILTER (WHERE activity_type = 'call') AS calls,
    count(*) FILTER (WHERE activity_type = 'meeting') AS meetings
FROM sales.activity
WHERE activity_at >= now() - interval '30 days'
GROUP BY owner_user_id;

CREATE VIEW sales.v_ticket_backlog AS
SELECT
    state,
    priority,
    count(*) AS ticket_count
FROM sales.ticket
GROUP BY state, priority;

CREATE VIEW billing.v_mrr_by_tier AS
SELECT
    a.tier,
    count(*) FILTER (WHERE s.state = 'active') AS active_subscriptions,
    sum(s.mrr) FILTER (WHERE s.state = 'active') AS total_mrr
FROM billing.subscription s
JOIN sales.account a ON a.id = s.account_id
GROUP BY a.tier;

CREATE VIEW billing.v_ar_aging AS
SELECT
    CASE
        WHEN now()::date - i.due_at::date <= 0 THEN 'current'
        WHEN now()::date - i.due_at::date <= 30 THEN '1_30'
        WHEN now()::date - i.due_at::date <= 60 THEN '31_60'
        ELSE '60_plus'
    END AS aging_bucket,
    count(*) AS invoice_count,
    sum(i.total_amount) AS total_amount
FROM billing.invoice i
WHERE i.state IN ('issued', 'overdue')
GROUP BY 1;

CREATE VIEW engagement.v_campaign_performance AS
SELECT
    c.id AS campaign_id,
    c.channel,
    count(cm.id) AS members,
    count(ee.id) AS sends,
    count(ee.id) FILTER (WHERE ee.opened_at IS NOT NULL) AS opens,
    count(ee.id) FILTER (WHERE ee.clicked_at IS NOT NULL) AS clicks
FROM engagement.campaign c
LEFT JOIN engagement.campaign_member cm ON cm.campaign_id = c.id
LEFT JOIN engagement.email_event ee ON ee.campaign_member_id = cm.id
GROUP BY c.id, c.channel;

CREATE VIEW platform.v_integration_sla AS
SELECT
    i.id AS integration_id,
    i.integration_name,
    count(j.id) AS total_jobs,
    count(j.id) FILTER (WHERE j.state = 'failed') AS failed_jobs
FROM platform.integration i
LEFT JOIN platform.sync_job j ON j.integration_id = i.id
GROUP BY i.id, i.integration_name;

CREATE VIEW analytics.v_churn_risk_accounts AS
SELECT
    a.id AS account_id,
    a.account_name,
    analytics.fn_account_health_score(a.id) AS health_score
FROM sales.account a
WHERE analytics.fn_account_health_score(a.id) < 60;

CREATE VIEW analytics.v_revenue_by_region AS
SELECT
    t.region_code,
    date_trunc('month', i.issued_at)::date AS month,
    sum(i.total_amount) AS invoiced_amount
FROM billing.invoice i
JOIN sales.account a ON a.id = i.account_id
JOIN core.tenant t ON t.id = a.tenant_id
GROUP BY t.region_code, date_trunc('month', i.issued_at)::date;

CREATE INDEX idx_core_tenant_tier_region ON core.tenant (tier, region_code, is_active);
CREATE INDEX idx_core_user_tenant_role ON core.app_user (tenant_id, role, state);
CREATE INDEX idx_core_user_manager ON core.app_user (manager_id);
CREATE INDEX idx_core_team_tenant ON core.team (tenant_id);
CREATE INDEX idx_core_team_member_user ON core.team_member (user_id, joined_at DESC);

CREATE INDEX idx_sales_account_tenant_owner ON sales.account (tenant_id, owner_user_id);
CREATE INDEX idx_sales_account_arr ON sales.account (arr DESC);
CREATE INDEX idx_sales_contact_account_dm ON sales.account_contact (account_id, is_decision_maker);
CREATE INDEX idx_sales_lead_owner_status ON sales.lead (owner_user_id, status, created_at DESC);
CREATE INDEX idx_sales_lead_account ON sales.lead (account_id);
CREATE INDEX idx_sales_oppty_stage_close ON sales.opportunity (stage, expected_close_date);
CREATE INDEX idx_sales_oppty_owner_stage ON sales.opportunity (owner_user_id, stage);
CREATE INDEX idx_sales_activity_owner_time ON sales.activity (owner_user_id, activity_at DESC);
CREATE INDEX idx_sales_activity_account_time ON sales.activity (account_id, activity_at DESC);
CREATE INDEX idx_sales_ticket_account_state ON sales.ticket (account_id, state, opened_at DESC);
CREATE INDEX idx_sales_ticket_owner_priority ON sales.ticket (owner_user_id, priority);

CREATE INDEX idx_billing_sub_account_state ON billing.subscription (account_id, state);
CREATE INDEX idx_billing_sub_plan_period_end ON billing.subscription (plan_id, period_end);
CREATE INDEX idx_billing_invoice_account_issued ON billing.invoice (account_id, issued_at DESC);
CREATE INDEX idx_billing_invoice_state_due ON billing.invoice (state, due_at);
CREATE INDEX idx_billing_payment_invoice_status ON billing.payment (invoice_id, status);
CREATE INDEX idx_billing_payment_paid ON billing.payment (paid_at DESC);

CREATE INDEX idx_eng_campaign_tenant_status ON engagement.campaign (tenant_id, status, start_at DESC);
CREATE INDEX idx_eng_member_campaign_status ON engagement.campaign_member (campaign_id, member_status);
CREATE INDEX idx_eng_member_account ON engagement.campaign_member (account_id);
CREATE INDEX idx_eng_email_member_sent ON engagement.email_event (campaign_member_id, sent_at DESC);
CREATE INDEX idx_eng_event_account_time ON engagement.product_event (account_id, occurred_at DESC);
CREATE INDEX idx_eng_event_kind_time ON engagement.product_event (kind, occurred_at DESC);

CREATE INDEX idx_platform_integration_tenant_state ON platform.integration (tenant_id, state);
CREATE INDEX idx_platform_sync_job_integration_time ON platform.sync_job (integration_id, started_at DESC);
CREATE INDEX idx_platform_sync_job_state_time ON platform.sync_job (state, started_at DESC);
CREATE INDEX idx_platform_endpoint_tenant_active ON platform.webhook_endpoint (tenant_id, is_active);
CREATE INDEX idx_platform_delivery_endpoint_time ON platform.webhook_delivery (endpoint_id, delivered_at DESC);
CREATE INDEX idx_platform_delivery_status ON platform.webhook_delivery (status_code, retry_count);
CREATE INDEX idx_platform_token_user_scope ON platform.api_token (user_id, scope, expires_at);

CREATE INDEX idx_analytics_daily_account_date ON analytics.daily_account_metric (account_id, metric_date DESC);
CREATE INDEX idx_analytics_daily_churn ON analytics.daily_account_metric (churned, metric_date DESC);
CREATE INDEX idx_analytics_prediction_account_time ON analytics.prediction (account_id, predicted_at DESC);
CREATE INDEX idx_analytics_prediction_label_score ON analytics.prediction (predicted_label, score DESC);
CREATE INDEX idx_analytics_quota_month_user ON analytics.rep_quota (quota_month, user_id);

ANALYZE;
COMMIT;

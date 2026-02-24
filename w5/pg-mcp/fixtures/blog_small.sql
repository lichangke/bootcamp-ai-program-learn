-- Dataset: blog_small
-- Goal: small but meaningful schema for MCP schema discovery and query tests.

SET client_min_messages = warning;
BEGIN;

CREATE TYPE user_role AS ENUM ('reader', 'author', 'editor', 'admin');
CREATE TYPE post_status AS ENUM ('draft', 'review', 'published', 'archived');
CREATE TYPE reaction_kind AS ENUM ('like', 'insightful', 'funny', 'bookmark');

CREATE TABLE app_user (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    role user_role NOT NULL DEFAULT 'reader',
    reputation INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE author_profile (
    user_id BIGINT PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    bio TEXT,
    website TEXT,
    expertise_tags TEXT[] NOT NULL DEFAULT '{}',
    verified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE category (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE tag (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    usage_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE post (
    id BIGSERIAL PRIMARY KEY,
    author_id BIGINT NOT NULL REFERENCES app_user(id),
    category_id BIGINT NOT NULL REFERENCES category(id),
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    body TEXT NOT NULL,
    status post_status NOT NULL DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    view_count INTEGER NOT NULL DEFAULT 0,
    reading_time_min SMALLINT NOT NULL DEFAULT 1,
    language_code CHAR(2) NOT NULL DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE post_revision (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    revision_no INTEGER NOT NULL,
    editor_id BIGINT NOT NULL REFERENCES app_user(id),
    body_snapshot TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, revision_no)
);

CREATE TABLE post_tag (
    post_id BIGINT NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    relevance SMALLINT NOT NULL DEFAULT 5 CHECK (relevance BETWEEN 1 AND 10),
    PRIMARY KEY (post_id, tag_id)
);

CREATE TABLE comment (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_user(id),
    parent_comment_id BIGINT REFERENCES comment(id),
    content TEXT NOT NULL,
    upvotes INTEGER NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reaction (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_user(id),
    kind reaction_kind NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, user_id, kind)
);

CREATE TABLE audit_event (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT REFERENCES app_user(id),
    entity_type TEXT NOT NULL,
    entity_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_user (username, email, role, reputation, is_active, created_at)
SELECT
    format('user_%s', gs),
    format('user_%s@example.com', gs),
    CASE
        WHEN gs <= 65 THEN 'reader'
        WHEN gs <= 105 THEN 'author'
        WHEN gs <= 116 THEN 'editor'
        ELSE 'admin'
    END::user_role,
    (gs * 13) % 700,
    gs % 17 <> 0,
    now() - ((gs % 400) || ' days')::interval
FROM generate_series(1, 120) AS gs;

INSERT INTO author_profile (user_id, bio, website, expertise_tags, verified)
SELECT
    u.id,
    format('Author profile for %s', u.username),
    format('https://%s.blog.local', u.username),
    ARRAY[
        format('topic_%s', (u.id % 10) + 1),
        format('topic_%s', (u.id % 15) + 1)
    ],
    (u.role IN ('editor', 'admin'))
FROM app_user AS u
WHERE u.role IN ('author', 'editor', 'admin');

INSERT INTO category (name, slug, description)
SELECT
    c.name,
    lower(replace(c.name, ' ', '-')),
    format('%s related posts', c.name)
FROM (
    VALUES
    ('Engineering'),
    ('Data Science'),
    ('DevOps'),
    ('Product'),
    ('Leadership'),
    ('Career'),
    ('Architecture'),
    ('Testing'),
    ('Security'),
    ('Frontend'),
    ('Backend'),
    ('AI')
) AS c(name);

INSERT INTO tag (name, slug)
SELECT
    format('tag_%s', gs),
    format('tag-%s', gs)
FROM generate_series(1, 80) AS gs;

INSERT INTO post (
    author_id, category_id, title, slug, body, status, published_at,
    view_count, reading_time_min, language_code, created_at, updated_at
)
SELECT
    ((gs - 1) % 90) + 1,
    ((gs - 1) % 12) + 1,
    format('Post %s', gs),
    format('post-%s', gs),
    repeat(format('Generated article content block %s. ', gs), 12),
    CASE
        WHEN gs % 10 = 0 THEN 'draft'
        WHEN gs % 10 = 1 THEN 'review'
        WHEN gs % 10 = 2 THEN 'archived'
        ELSE 'published'
    END::post_status,
    CASE
        WHEN gs % 10 IN (0, 1) THEN NULL
        ELSE now() - ((gs % 365) || ' days')::interval
    END,
    (gs * 37) % 50000,
    2 + (gs % 18),
    CASE WHEN gs % 5 = 0 THEN 'zh' ELSE 'en' END,
    now() - ((gs % 540) || ' days')::interval,
    now() - ((gs % 120) || ' days')::interval
FROM generate_series(1, 2500) AS gs;

INSERT INTO post_revision (post_id, revision_no, editor_id, body_snapshot, created_at)
SELECT
    p.id,
    rev.rev_no,
    ((p.id + rev.rev_no) % 120) + 1,
    left(p.body, 300) || format(' [revision %s]', rev.rev_no),
    p.created_at + (rev.rev_no || ' hours')::interval
FROM post AS p
CROSS JOIN LATERAL generate_series(1, 1 + (p.id % 3)) AS rev(rev_no);

INSERT INTO post_tag (post_id, tag_id, relevance)
SELECT
    p.id,
    ((p.id + offs) % 80) + 1,
    10 - offs
FROM post AS p
CROSS JOIN generate_series(0, 2) AS offs
ON CONFLICT DO NOTHING;

INSERT INTO comment (post_id, user_id, parent_comment_id, content, upvotes, is_deleted, created_at)
SELECT
    ((gs - 1) % 2500) + 1,
    ((gs * 7) % 120) + 1,
    CASE WHEN gs > 1 AND gs % 8 = 0 THEN gs - 1 ELSE NULL END,
    format('Comment %s on generated post.', gs),
    (gs * 3) % 40,
    (gs % 29 = 0),
    now() - ((gs % 240) || ' days')::interval - ((gs % 1440) || ' minutes')::interval
FROM generate_series(1, 22000) AS gs;

INSERT INTO reaction (post_id, user_id, kind, created_at)
SELECT
    ((gs - 1) % 2500) + 1,
    ((gs * 5) % 120) + 1,
    CASE (gs % 4)
        WHEN 0 THEN 'like'
        WHEN 1 THEN 'insightful'
        WHEN 2 THEN 'funny'
        ELSE 'bookmark'
    END::reaction_kind,
    now() - ((gs % 300) || ' days')::interval
FROM generate_series(1, 50000) AS gs
ON CONFLICT DO NOTHING;

INSERT INTO audit_event (actor_user_id, entity_type, entity_id, action, payload, created_at)
SELECT
    ((gs * 3) % 120) + 1,
    CASE
        WHEN gs % 3 = 0 THEN 'post'
        WHEN gs % 3 = 1 THEN 'comment'
        ELSE 'profile'
    END,
    ((gs * 11) % 2500) + 1,
    CASE
        WHEN gs % 4 = 0 THEN 'create'
        WHEN gs % 4 = 1 THEN 'update'
        WHEN gs % 4 = 2 THEN 'publish'
        ELSE 'archive'
    END,
    jsonb_build_object('source', 'seed', 'seq', gs),
    now() - ((gs % 365) || ' days')::interval
FROM generate_series(1, 15000) AS gs;

UPDATE tag AS t
SET usage_count = s.cnt
FROM (
    SELECT t2.id, count(pt.tag_id)::integer AS cnt
    FROM tag AS t2
    LEFT JOIN post_tag AS pt ON pt.tag_id = t2.id
    GROUP BY t2.id
) AS s
WHERE t.id = s.id;

CREATE OR REPLACE FUNCTION fn_post_word_count(p_post_id BIGINT)
RETURNS INTEGER
LANGUAGE SQL
STABLE
AS $$
SELECT COALESCE(array_length(regexp_split_to_array(trim(body), E'\\s+'), 1), 0)
FROM post
WHERE id = p_post_id;
$$;

CREATE VIEW v_post_summary AS
SELECT
    p.id,
    p.title,
    p.slug,
    p.status,
    p.published_at,
    p.view_count,
    u.username AS author_username,
    c.name AS category_name,
    count(DISTINCT cm.id) AS comment_count,
    count(DISTINCT r.id) AS reaction_count
FROM post AS p
JOIN app_user AS u ON u.id = p.author_id
JOIN category AS c ON c.id = p.category_id
LEFT JOIN comment AS cm ON cm.post_id = p.id AND cm.is_deleted = FALSE
LEFT JOIN reaction AS r ON r.post_id = p.id
GROUP BY p.id, u.username, c.name;

CREATE VIEW v_author_activity AS
SELECT
    u.id AS user_id,
    u.username,
    u.role,
    count(DISTINCT p.id) AS total_posts,
    count(DISTINCT CASE WHEN p.status = 'published' THEN p.id END) AS published_posts,
    count(DISTINCT cm.id) AS comments_received,
    COALESCE(sum(p.view_count), 0) AS total_views
FROM app_user AS u
LEFT JOIN post AS p ON p.author_id = u.id
LEFT JOIN comment AS cm ON cm.post_id = p.id AND cm.is_deleted = FALSE
GROUP BY u.id, u.username, u.role;

CREATE VIEW v_daily_content_velocity AS
SELECT
    date_trunc('day', p.created_at)::date AS day,
    count(*) AS post_count,
    avg(p.reading_time_min)::numeric(8, 2) AS avg_reading_time_min,
    sum(p.view_count) AS total_views
FROM post AS p
GROUP BY 1;

CREATE INDEX idx_app_user_role_active ON app_user (role, is_active);
CREATE INDEX idx_app_user_created_at ON app_user (created_at DESC);
CREATE INDEX idx_post_status_published_at ON post (status, published_at DESC);
CREATE INDEX idx_post_author_published_at ON post (author_id, published_at DESC);
CREATE INDEX idx_post_category_status ON post (category_id, status);
CREATE INDEX idx_post_language_code ON post (language_code);
CREATE INDEX idx_post_revision_post_created ON post_revision (post_id, created_at DESC);
CREATE INDEX idx_post_tag_tag_id ON post_tag (tag_id, post_id);
CREATE INDEX idx_comment_post_created ON comment (post_id, created_at DESC);
CREATE INDEX idx_comment_user_created ON comment (user_id, created_at DESC);
CREATE INDEX idx_comment_parent ON comment (parent_comment_id);
CREATE INDEX idx_reaction_post_kind ON reaction (post_id, kind);
CREATE INDEX idx_audit_event_entity ON audit_event (entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_event_actor ON audit_event (actor_user_id, created_at DESC);

ANALYZE;
COMMIT;

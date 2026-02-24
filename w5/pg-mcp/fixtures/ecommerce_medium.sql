-- Dataset: ecommerce_medium
-- Goal: medium-scale e-commerce schema with many relational paths and enough rows.

SET client_min_messages = warning;
BEGIN;

CREATE TYPE customer_tier AS ENUM ('new', 'silver', 'gold', 'platinum');
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'packed', 'shipped', 'delivered', 'cancelled', 'refunded');
CREATE TYPE payment_status AS ENUM ('initiated', 'authorized', 'captured', 'failed', 'refunded');
CREATE TYPE shipment_status AS ENUM ('created', 'in_transit', 'delivered', 'lost', 'returned');
CREATE TYPE promo_type AS ENUM ('percentage', 'fixed_amount', 'free_shipping');
CREATE TYPE return_status AS ENUM ('requested', 'approved', 'rejected', 'received', 'completed');

CREATE TABLE customer (
    id BIGSERIAL PRIMARY KEY,
    customer_code TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    tier customer_tier NOT NULL DEFAULT 'new',
    date_of_birth DATE,
    is_marketing_opt_in BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer_address (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
    address_type TEXT NOT NULL CHECK (address_type IN ('billing', 'shipping', 'both')),
    country_code CHAR(2) NOT NULL DEFAULT 'US',
    state TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    line1 TEXT NOT NULL,
    line2 TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE supplier (
    id BIGSERIAL PRIMARY KEY,
    supplier_code TEXT NOT NULL UNIQUE,
    supplier_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL DEFAULT 7,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE brand (
    id BIGSERIAL PRIMARY KEY,
    brand_name TEXT NOT NULL UNIQUE,
    origin_country CHAR(2) NOT NULL DEFAULT 'US'
);

CREATE TABLE product_category (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_category_id BIGINT REFERENCES product_category(id),
    depth SMALLINT NOT NULL DEFAULT 1 CHECK (depth BETWEEN 1 AND 4),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    product_code TEXT NOT NULL UNIQUE,
    category_id BIGINT NOT NULL REFERENCES product_category(id),
    supplier_id BIGINT NOT NULL REFERENCES supplier(id),
    brand_id BIGINT NOT NULL REFERENCES brand(id),
    product_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    base_price NUMERIC(12, 2) NOT NULL CHECK (base_price >= 0),
    tax_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.0800,
    rating_avg NUMERIC(3, 2),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_variant (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    sku TEXT NOT NULL UNIQUE,
    variant_name TEXT NOT NULL,
    color TEXT NOT NULL,
    size_code TEXT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    weight_grams INTEGER NOT NULL CHECK (weight_grams > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE warehouse (
    id BIGSERIAL PRIMARY KEY,
    warehouse_code TEXT NOT NULL UNIQUE,
    warehouse_name TEXT NOT NULL,
    country_code CHAR(2) NOT NULL DEFAULT 'US',
    region TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC'
);

CREATE TABLE inventory_stock (
    id BIGSERIAL PRIMARY KEY,
    variant_id BIGINT NOT NULL REFERENCES product_variant(id) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES warehouse(id),
    on_hand_qty INTEGER NOT NULL DEFAULT 0 CHECK (on_hand_qty >= 0),
    reserved_qty INTEGER NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    reorder_point INTEGER NOT NULL DEFAULT 10 CHECK (reorder_point >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (variant_id, warehouse_id)
);

CREATE TABLE shopping_cart (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('active', 'converted', 'abandoned')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cart_item (
    id BIGSERIAL PRIMARY KEY,
    cart_id BIGINT NOT NULL REFERENCES shopping_cart(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES product_variant(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cart_id, variant_id)
);

CREATE TABLE promotion (
    id BIGSERIAL PRIMARY KEY,
    promo_code TEXT NOT NULL UNIQUE,
    promo_name TEXT NOT NULL,
    promo_type promo_type NOT NULL,
    discount_value NUMERIC(10, 2) NOT NULL CHECK (discount_value >= 0),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    usage_limit INTEGER,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE order_header (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    billing_address_id BIGINT NOT NULL REFERENCES customer_address(id),
    shipping_address_id BIGINT NOT NULL REFERENCES customer_address(id),
    order_status order_status NOT NULL DEFAULT 'pending',
    placed_at TIMESTAMPTZ NOT NULL,
    subtotal_amount NUMERIC(12, 2) NOT NULL CHECK (subtotal_amount >= 0),
    tax_amount NUMERIC(12, 2) NOT NULL CHECK (tax_amount >= 0),
    shipping_amount NUMERIC(12, 2) NOT NULL CHECK (shipping_amount >= 0),
    discount_amount NUMERIC(12, 2) NOT NULL CHECK (discount_amount >= 0),
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    source_channel TEXT NOT NULL CHECK (source_channel IN ('web', 'mobile', 'marketplace'))
);

CREATE TABLE order_item (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES order_header(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL CHECK (line_no > 0),
    variant_id BIGINT NOT NULL REFERENCES product_variant(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
    UNIQUE (order_id, line_no)
);

CREATE TABLE payment_txn (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES order_header(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('stripe', 'paypal', 'adyen')),
    payment_status payment_status NOT NULL,
    provider_txn_id TEXT NOT NULL UNIQUE,
    attempted_at TIMESTAMPTZ NOT NULL,
    captured_at TIMESTAMPTZ,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    failure_reason TEXT
);

CREATE TABLE shipment (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL UNIQUE REFERENCES order_header(id) ON DELETE CASCADE,
    warehouse_id BIGINT NOT NULL REFERENCES warehouse(id),
    carrier TEXT NOT NULL CHECK (carrier IN ('ups', 'fedex', 'usps', 'dhl')),
    tracking_number TEXT NOT NULL UNIQUE,
    shipment_status shipment_status NOT NULL DEFAULT 'created',
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    shipping_cost NUMERIC(12, 2) NOT NULL CHECK (shipping_cost >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shipment_event (
    id BIGSERIAL PRIMARY KEY,
    shipment_id BIGINT NOT NULL REFERENCES shipment(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    location TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE return_request (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES order_header(id),
    order_item_id BIGINT NOT NULL REFERENCES order_item(id),
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    reason TEXT NOT NULL,
    return_status return_status NOT NULL DEFAULT 'requested',
    requested_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ,
    refund_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (refund_amount >= 0)
);

CREATE TABLE product_review (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    is_verified_purchase BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support_ticket (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    order_id BIGINT REFERENCES order_header(id),
    subject TEXT NOT NULL,
    ticket_status TEXT NOT NULL CHECK (ticket_status IN ('open', 'pending', 'resolved', 'closed')),
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);

CREATE TABLE promotion_redemption (
    id BIGSERIAL PRIMARY KEY,
    promotion_id BIGINT NOT NULL REFERENCES promotion(id),
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    order_id BIGINT REFERENCES order_header(id),
    redeemed_at TIMESTAMPTZ NOT NULL,
    discount_amount NUMERIC(12, 2) NOT NULL CHECK (discount_amount >= 0)
);

CREATE TABLE website_session (
    id BIGSERIAL PRIMARY KEY,
    session_token TEXT NOT NULL UNIQUE,
    customer_id BIGINT REFERENCES customer(id),
    channel TEXT NOT NULL CHECK (channel IN ('organic', 'paid', 'email', 'social', 'direct')),
    device_type TEXT NOT NULL CHECK (device_type IN ('desktop', 'mobile', 'tablet')),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    converted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE click_event (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES website_session(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL,
    page_url TEXT NOT NULL,
    referrer TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    event_time TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO customer (
    customer_code, first_name, last_name, email, phone, tier,
    date_of_birth, is_marketing_opt_in, created_at
)
SELECT
    format('C%06s', gs),
    format('First%s', gs),
    format('Last%s', gs),
    format('customer_%s@example.com', gs),
    format('+1-202-555-%04s', gs % 10000),
    CASE
        WHEN gs <= 2500 THEN 'new'
        WHEN gs <= 5200 THEN 'silver'
        WHEN gs <= 7300 THEN 'gold'
        ELSE 'platinum'
    END::customer_tier,
    date '1970-01-01' + ((gs * 13) % 18000),
    gs % 6 <> 0,
    now() - ((gs % 900) || ' days')::interval
FROM generate_series(1, 8000) AS gs;

INSERT INTO customer_address (
    customer_id, address_type, country_code, state, city, postal_code,
    line1, line2, is_default, created_at
)
SELECT
    ((gs - 1) % 8000) + 1,
    CASE
        WHEN gs % 3 = 0 THEN 'billing'
        WHEN gs % 3 = 1 THEN 'shipping'
        ELSE 'both'
    END,
    'US',
    format('State-%s', (gs % 50) + 1),
    format('City-%s', (gs % 180) + 1),
    format('%05s', (gs * 17) % 99999),
    format('%s Market Street', (gs % 3000) + 1),
    format('Suite %s', (gs % 300) + 1),
    gs % 5 = 0,
    now() - ((gs % 950) || ' days')::interval
FROM generate_series(1, 12000) AS gs;

INSERT INTO supplier (supplier_code, supplier_name, contact_email, lead_time_days, active)
SELECT
    format('SUP-%03s', gs),
    format('Supplier %s', gs),
    format('supplier_%s@vendor.example.com', gs),
    3 + (gs % 20),
    gs % 17 <> 0
FROM generate_series(1, 200) AS gs;

INSERT INTO brand (brand_name, origin_country)
SELECT
    format('Brand %s', gs),
    CASE WHEN gs % 5 = 0 THEN 'JP' WHEN gs % 7 = 0 THEN 'DE' ELSE 'US' END
FROM generate_series(1, 120) AS gs;

INSERT INTO product_category (name, parent_category_id, depth, active)
SELECT
    format('Category %s', gs),
    CASE
        WHEN gs <= 10 THEN NULL
        WHEN gs <= 40 THEN ((gs - 1) % 10) + 1
        ELSE ((gs - 1) % 30) + 11
    END,
    CASE
        WHEN gs <= 10 THEN 1
        WHEN gs <= 40 THEN 2
        ELSE 3
    END,
    gs % 29 <> 0
FROM generate_series(1, 90) AS gs;

INSERT INTO product (
    product_code, category_id, supplier_id, brand_id, product_name, description,
    base_price, tax_rate, rating_avg, active, created_at
)
SELECT
    format('P%07s', gs),
    ((gs - 1) % 90) + 1,
    ((gs - 1) % 200) + 1,
    ((gs - 1) % 120) + 1,
    format('Product %s', gs),
    format('Generated description for product %s', gs),
    ((gs % 7000) + 500)::numeric / 100,
    CASE WHEN gs % 4 = 0 THEN 0.0700 ELSE 0.0850 END,
    2.50 + ((gs % 25)::numeric / 10),
    gs % 37 <> 0,
    now() - ((gs % 900) || ' days')::interval
FROM generate_series(1, 7000) AS gs;

INSERT INTO product_variant (
    product_id, sku, variant_name, color, size_code,
    unit_price, weight_grams, is_active, created_at
)
SELECT
    p.id,
    format('SKU-%s-%s', p.id, sz.size_code),
    format('%s %s', p.product_name, sz.size_code),
    format('color_%s', (p.id + sz.sz_offset) % 16),
    sz.size_code,
    p.base_price + (sz.sz_offset * 2)::numeric,
    180 + ((p.id + sz.sz_offset) % 2200),
    p.active,
    p.created_at
FROM product AS p
CROSS JOIN (
    VALUES
    ('S', 0),
    ('M', 1),
    ('L', 2)
) AS sz(size_code, sz_offset);

INSERT INTO warehouse (warehouse_code, warehouse_name, country_code, region, timezone)
SELECT
    format('WH-%02s', gs),
    format('Warehouse %s', gs),
    'US',
    format('Region-%s', (gs % 6) + 1),
    CASE WHEN gs % 2 = 0 THEN 'America/Los_Angeles' ELSE 'America/New_York' END
FROM generate_series(1, 12) AS gs;

INSERT INTO inventory_stock (variant_id, warehouse_id, on_hand_qty, reserved_qty, reorder_point, updated_at)
SELECT
    v.id,
    w.id,
    ((v.id * 37 + w.id * 11) % 220),
    ((v.id * 13 + w.id * 5) % 30),
    8 + ((v.id + w.id) % 40),
    now() - (((v.id + w.id) % 45) || ' days')::interval
FROM product_variant AS v
JOIN warehouse AS w ON (v.id + w.id) % 3 <> 0;

INSERT INTO shopping_cart (customer_id, status, created_at, updated_at)
SELECT
    gs,
    CASE
        WHEN gs % 6 = 0 THEN 'converted'
        WHEN gs % 5 = 0 THEN 'abandoned'
        ELSE 'active'
    END,
    now() - ((gs % 120) || ' days')::interval,
    now() - ((gs % 60) || ' days')::interval
FROM generate_series(1, 6000) AS gs;

INSERT INTO cart_item (cart_id, variant_id, quantity, added_at)
SELECT
    c.id,
    ((c.id * 13 + ln * 7) % 21000) + 1,
    1 + ((c.id + ln) % 3),
    c.created_at + ((ln * 10) || ' minutes')::interval
FROM shopping_cart AS c
CROSS JOIN generate_series(1, 4) AS ln
ON CONFLICT (cart_id, variant_id) DO NOTHING;

INSERT INTO promotion (promo_code, promo_name, promo_type, discount_value, starts_at, ends_at, usage_limit, active)
SELECT
    format('PROMO%04s', gs),
    format('Promotion %s', gs),
    CASE
        WHEN gs % 3 = 0 THEN 'percentage'
        WHEN gs % 3 = 1 THEN 'fixed_amount'
        ELSE 'free_shipping'
    END::promo_type,
    CASE
        WHEN gs % 3 = 0 THEN (5 + (gs % 25))::numeric
        WHEN gs % 3 = 1 THEN ((gs % 2000) + 200)::numeric / 100
        ELSE 0::numeric
    END,
    now() - ((gs % 120) || ' days')::interval,
    now() + ((45 + (gs % 120)) || ' days')::interval,
    CASE WHEN gs % 7 = 0 THEN 5000 ELSE NULL END,
    gs % 19 <> 0
FROM generate_series(1, 160) AS gs;

INSERT INTO order_header (
    customer_id, billing_address_id, shipping_address_id, order_status, placed_at,
    subtotal_amount, tax_amount, shipping_amount, discount_amount, total_amount, source_channel
)
SELECT
    s.customer_id,
    ((s.customer_id * 2 - 1) % 12000) + 1,
    ((s.customer_id * 2) % 12000) + 1,
    s.order_status,
    s.placed_at,
    s.subtotal_amount,
    s.tax_amount,
    s.shipping_amount,
    s.discount_amount,
    s.subtotal_amount + s.tax_amount + s.shipping_amount - s.discount_amount,
    s.source_channel
FROM (
    SELECT
        gs,
        ((gs - 1) % 8000) + 1 AS customer_id,
        CASE
            WHEN gs % 17 = 0 THEN 'cancelled'
            WHEN gs % 19 = 0 THEN 'refunded'
            WHEN gs % 13 = 0 THEN 'shipped'
            WHEN gs % 11 = 0 THEN 'packed'
            WHEN gs % 7 = 0 THEN 'paid'
            ELSE 'delivered'
        END::order_status AS order_status,
        now() - ((gs % 780) || ' days')::interval AS placed_at,
        ((gs % 50000) + 2000)::numeric / 100 AS subtotal_amount,
        ((gs % 1600) + 120)::numeric / 100 AS tax_amount,
        ((gs % 1000) + 50)::numeric / 100 AS shipping_amount,
        CASE WHEN gs % 9 = 0 THEN ((gs % 1200) + 100)::numeric / 100 ELSE 0::numeric END AS discount_amount,
        CASE
            WHEN gs % 7 = 0 THEN 'marketplace'
            WHEN gs % 5 = 0 THEN 'mobile'
            ELSE 'web'
        END AS source_channel
    FROM generate_series(1, 70000) AS gs
) AS s;

INSERT INTO order_item (
    order_id, line_no, variant_id, quantity, unit_price, discount_amount, line_total
)
SELECT
    o.id,
    x.line_no,
    ((o.id * 17 + x.line_no * 13) % 21000) + 1,
    x.quantity,
    x.unit_price,
    x.discount_amount,
    (x.unit_price * x.quantity) - x.discount_amount
FROM order_header AS o
CROSS JOIN LATERAL (
    SELECT
        ln AS line_no,
        1 + ((o.id + ln) % 3) AS quantity,
        ((o.id * 23 + ln * 11) % 7000 + 500)::numeric / 100 AS unit_price,
        CASE WHEN (o.id + ln) % 8 = 0 THEN ((o.id + ln) % 400)::numeric / 100 ELSE 0::numeric END AS discount_amount
    FROM generate_series(1, 1 + (o.id % 4)) AS ln
) AS x;

INSERT INTO payment_txn (
    order_id, provider, payment_status, provider_txn_id, attempted_at,
    captured_at, amount, currency, failure_reason
)
SELECT
    o.id,
    CASE
        WHEN o.id % 3 = 0 THEN 'stripe'
        WHEN o.id % 3 = 1 THEN 'paypal'
        ELSE 'adyen'
    END,
    CASE
        WHEN o.order_status = 'cancelled' THEN 'failed'
        WHEN o.order_status = 'refunded' THEN 'refunded'
        WHEN o.order_status IN ('paid', 'packed', 'shipped', 'delivered') THEN 'captured'
        ELSE 'authorized'
    END::payment_status,
    format('TXN-%08s', o.id),
    o.placed_at + ((o.id % 120) || ' minutes')::interval,
    CASE
        WHEN o.order_status IN ('paid', 'packed', 'shipped', 'delivered', 'refunded')
            THEN o.placed_at + ((2 + (o.id % 240)) || ' minutes')::interval
        ELSE NULL
    END,
    o.total_amount,
    'USD',
    CASE WHEN o.order_status = 'cancelled' THEN 'issuer_declined' ELSE NULL END
FROM order_header AS o;

INSERT INTO shipment (
    order_id, warehouse_id, carrier, tracking_number, shipment_status,
    shipped_at, delivered_at, shipping_cost, created_at
)
SELECT
    o.id,
    ((o.id - 1) % 12) + 1,
    CASE
        WHEN o.id % 4 = 0 THEN 'ups'
        WHEN o.id % 4 = 1 THEN 'fedex'
        WHEN o.id % 4 = 2 THEN 'usps'
        ELSE 'dhl'
    END,
    format('TRK-%09s', o.id),
    CASE
        WHEN o.order_status = 'delivered' THEN 'delivered'
        WHEN o.order_status = 'shipped' THEN 'in_transit'
        ELSE 'created'
    END::shipment_status,
    CASE
        WHEN o.order_status IN ('shipped', 'delivered')
            THEN o.placed_at + ((1 + (o.id % 4)) || ' days')::interval
        ELSE NULL
    END,
    CASE
        WHEN o.order_status = 'delivered'
            THEN o.placed_at + ((3 + (o.id % 9)) || ' days')::interval
        ELSE NULL
    END,
    o.shipping_amount,
    o.placed_at + ((o.id % 90) || ' minutes')::interval
FROM order_header AS o
WHERE o.order_status NOT IN ('cancelled');

INSERT INTO shipment_event (shipment_id, event_type, event_time, location, payload)
SELECT
    s.id,
    e.event_type,
    COALESCE(s.shipped_at, s.created_at) + e.event_offset,
    format('Hub-%s', (s.id % 40) + 1),
    jsonb_build_object('carrier', s.carrier, 'tracking', s.tracking_number)
FROM shipment AS s
JOIN (
    VALUES
    ('label_created', interval '0 hours'),
    ('in_transit', interval '18 hours'),
    ('delivered', interval '54 hours')
) AS e(event_type, event_offset)
    ON (e.event_type <> 'delivered' OR s.delivered_at IS NOT NULL);

INSERT INTO return_request (
    order_id, order_item_id, customer_id, reason, return_status,
    requested_at, processed_at, refund_amount
)
SELECT
    oi.order_id,
    oi.id,
    oh.customer_id,
    CASE
        WHEN oi.id % 3 = 0 THEN 'damaged'
        WHEN oi.id % 3 = 1 THEN 'wrong_item'
        ELSE 'not_as_described'
    END,
    CASE
        WHEN oi.id % 5 = 0 THEN 'completed'
        WHEN oi.id % 5 = 1 THEN 'received'
        WHEN oi.id % 5 = 2 THEN 'approved'
        ELSE 'requested'
    END::return_status,
    oh.placed_at + ((10 + (oi.id % 30)) || ' days')::interval,
    CASE
        WHEN oi.id % 5 IN (0, 1, 2)
            THEN oh.placed_at + ((15 + (oi.id % 35)) || ' days')::interval
        ELSE NULL
    END,
    (oi.line_total * 0.85)
FROM order_item AS oi
JOIN order_header AS oh ON oh.id = oi.order_id
WHERE oi.id % 23 = 0
LIMIT 6000;

INSERT INTO product_review (
    product_id, customer_id, rating, title, body, is_verified_purchase, created_at
)
SELECT
    ((gs * 13) % 7000) + 1,
    ((gs * 17) % 8000) + 1,
    1 + (gs % 5),
    format('Review title %s', gs),
    format('Generated review body for record %s.', gs),
    gs % 3 <> 0,
    now() - ((gs % 540) || ' days')::interval
FROM generate_series(1, 50000) AS gs;

INSERT INTO support_ticket (
    customer_id, order_id, subject, ticket_status, priority, opened_at, closed_at
)
SELECT
    ((gs - 1) % 8000) + 1,
    ((gs * 11) % 70000) + 1,
    format('Support ticket %s', gs),
    CASE
        WHEN gs % 5 = 0 THEN 'closed'
        WHEN gs % 5 = 1 THEN 'resolved'
        WHEN gs % 5 = 2 THEN 'pending'
        ELSE 'open'
    END,
    CASE
        WHEN gs % 10 = 0 THEN 'urgent'
        WHEN gs % 4 = 0 THEN 'high'
        WHEN gs % 3 = 0 THEN 'medium'
        ELSE 'low'
    END,
    now() - ((gs % 420) || ' days')::interval,
    CASE
        WHEN gs % 5 IN (0, 1)
            THEN now() - ((gs % 380) || ' days')::interval
        ELSE NULL
    END
FROM generate_series(1, 15000) AS gs;

INSERT INTO promotion_redemption (
    promotion_id, customer_id, order_id, redeemed_at, discount_amount
)
SELECT
    ((gs - 1) % 160) + 1,
    ((gs * 5) % 8000) + 1,
    CASE WHEN gs % 4 = 0 THEN ((gs * 19) % 70000) + 1 ELSE NULL END,
    now() - ((gs % 365) || ' days')::interval,
    ((gs % 1800) + 100)::numeric / 100
FROM generate_series(1, 45000) AS gs;

INSERT INTO website_session (
    session_token, customer_id, channel, device_type, started_at, ended_at, converted
)
SELECT
    format('sess_%s', gs),
    CASE WHEN gs % 9 = 0 THEN NULL ELSE ((gs - 1) % 8000) + 1 END,
    CASE
        WHEN gs % 5 = 0 THEN 'paid'
        WHEN gs % 5 = 1 THEN 'organic'
        WHEN gs % 5 = 2 THEN 'email'
        WHEN gs % 5 = 3 THEN 'social'
        ELSE 'direct'
    END,
    CASE
        WHEN gs % 3 = 0 THEN 'mobile'
        WHEN gs % 3 = 1 THEN 'desktop'
        ELSE 'tablet'
    END,
    now() - ((gs % 200) || ' days')::interval,
    now() - ((gs % 200) || ' days')::interval + ((5 + (gs % 180)) || ' minutes')::interval,
    gs % 6 = 0
FROM generate_series(1, 180000) AS gs;

INSERT INTO click_event (
    session_id, event_name, page_url, referrer, duration_ms, event_time, metadata
)
SELECT
    ((gs - 1) % 180000) + 1,
    CASE
        WHEN gs % 6 = 0 THEN 'purchase_click'
        WHEN gs % 6 = 1 THEN 'add_to_cart'
        WHEN gs % 6 = 2 THEN 'product_view'
        WHEN gs % 6 = 3 THEN 'search'
        WHEN gs % 6 = 4 THEN 'checkout_start'
        ELSE 'home_view'
    END,
    format('/page/%s', (gs % 900) + 1),
    CASE WHEN gs % 4 = 0 THEN 'google' WHEN gs % 4 = 1 THEN 'newsletter' ELSE NULL END,
    100 + ((gs * 17) % 20000),
    now() - ((gs % 200) || ' days')::interval - ((gs % 86400) || ' seconds')::interval,
    jsonb_build_object('seq', gs, 'experiment', (gs % 12))
FROM generate_series(1, 600000) AS gs;

CREATE OR REPLACE FUNCTION fn_customer_ltv(p_customer_id BIGINT)
RETURNS NUMERIC
LANGUAGE SQL
STABLE
AS $$
SELECT COALESCE(sum(total_amount), 0)
FROM order_header
WHERE customer_id = p_customer_id
  AND order_status IN ('paid', 'packed', 'shipped', 'delivered', 'refunded');
$$;

CREATE VIEW v_daily_sales AS
SELECT
    date_trunc('day', placed_at)::date AS order_day,
    count(*) AS order_count,
    sum(total_amount) AS gross_revenue,
    avg(total_amount)::numeric(12, 2) AS avg_order_value
FROM order_header
WHERE order_status NOT IN ('cancelled')
GROUP BY 1;

CREATE VIEW v_top_products_30d AS
SELECT
    p.id AS product_id,
    p.product_name,
    sum(oi.quantity) AS qty_sold,
    sum(oi.line_total) AS line_revenue
FROM order_item AS oi
JOIN order_header AS oh ON oh.id = oi.order_id
JOIN product_variant AS pv ON pv.id = oi.variant_id
JOIN product AS p ON p.id = pv.product_id
WHERE oh.placed_at >= now() - interval '30 days'
  AND oh.order_status NOT IN ('cancelled')
GROUP BY p.id, p.product_name;

CREATE VIEW v_customer_ltv AS
SELECT
    c.id AS customer_id,
    c.customer_code,
    c.tier,
    count(DISTINCT oh.id) AS order_count,
    COALESCE(sum(oh.total_amount), 0) AS total_revenue
FROM customer AS c
LEFT JOIN order_header AS oh ON oh.customer_id = c.id
    AND oh.order_status NOT IN ('cancelled')
GROUP BY c.id, c.customer_code, c.tier;

CREATE VIEW v_inventory_risk AS
SELECT
    pv.id AS variant_id,
    pv.sku,
    sum(i.on_hand_qty - i.reserved_qty) AS available_qty,
    min(i.reorder_point) AS min_reorder_point,
    CASE
        WHEN sum(i.on_hand_qty - i.reserved_qty) < min(i.reorder_point) THEN 'at_risk'
        ELSE 'healthy'
    END AS stock_state
FROM product_variant AS pv
JOIN inventory_stock AS i ON i.variant_id = pv.id
GROUP BY pv.id, pv.sku;

CREATE VIEW v_fulfillment_performance AS
SELECT
    s.carrier,
    count(*) AS shipments,
    avg(extract(epoch FROM (s.delivered_at - s.shipped_at)) / 3600)::numeric(10, 2) AS avg_delivery_hours,
    sum(CASE WHEN s.shipment_status = 'delivered' THEN 1 ELSE 0 END) AS delivered_count
FROM shipment AS s
GROUP BY s.carrier;

CREATE VIEW v_channel_conversion AS
SELECT
    ws.channel,
    count(*) AS sessions,
    sum(CASE WHEN ws.converted THEN 1 ELSE 0 END) AS converted_sessions,
    (sum(CASE WHEN ws.converted THEN 1 ELSE 0 END)::numeric / NULLIF(count(*), 0))::numeric(8, 4) AS conversion_rate
FROM website_session AS ws
GROUP BY ws.channel;

CREATE INDEX idx_customer_tier_created ON customer (tier, created_at DESC);
CREATE INDEX idx_customer_email ON customer (email);
CREATE INDEX idx_address_customer_default ON customer_address (customer_id, is_default DESC);
CREATE INDEX idx_product_category_parent ON product_category (parent_category_id);
CREATE INDEX idx_product_category_supplier ON product (category_id, supplier_id);
CREATE INDEX idx_product_brand_active ON product (brand_id, active);
CREATE INDEX idx_variant_product_active ON product_variant (product_id, is_active);
CREATE INDEX idx_inventory_variant_warehouse ON inventory_stock (variant_id, warehouse_id);
CREATE INDEX idx_inventory_reorder ON inventory_stock (reorder_point, on_hand_qty);
CREATE INDEX idx_cart_customer_status ON shopping_cart (customer_id, status);
CREATE INDEX idx_cart_item_variant ON cart_item (variant_id);
CREATE INDEX idx_order_customer_placed ON order_header (customer_id, placed_at DESC);
CREATE INDEX idx_order_status_placed ON order_header (order_status, placed_at DESC);
CREATE INDEX idx_order_channel_placed ON order_header (source_channel, placed_at DESC);
CREATE INDEX idx_order_item_order ON order_item (order_id);
CREATE INDEX idx_order_item_variant ON order_item (variant_id);
CREATE INDEX idx_payment_order_status ON payment_txn (order_id, payment_status);
CREATE INDEX idx_shipment_status_dates ON shipment (shipment_status, shipped_at DESC);
CREATE INDEX idx_shipment_event_time ON shipment_event (shipment_id, event_time DESC);
CREATE INDEX idx_return_customer_status ON return_request (customer_id, return_status, requested_at DESC);
CREATE INDEX idx_review_product_rating ON product_review (product_id, rating DESC);
CREATE INDEX idx_ticket_customer_status ON support_ticket (customer_id, ticket_status, opened_at DESC);
CREATE INDEX idx_redemption_promo_time ON promotion_redemption (promotion_id, redeemed_at DESC);
CREATE INDEX idx_session_channel_start ON website_session (channel, started_at DESC);
CREATE INDEX idx_session_customer_start ON website_session (customer_id, started_at DESC);
CREATE INDEX idx_click_session_time ON click_event (session_id, event_time DESC);
CREATE INDEX idx_click_event_name_time ON click_event (event_name, event_time DESC);

ANALYZE;
COMMIT;

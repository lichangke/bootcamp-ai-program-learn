CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS 'application users';
COMMENT ON COLUMN users.id IS 'user primary key';
COMMENT ON COLUMN users.email IS 'user login email';

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE orders IS 'customer purchase orders';
COMMENT ON COLUMN orders.total IS 'order total amount';

INSERT INTO users(name, email, status) VALUES
('Alice', 'alice@example.com', 'active'),
('Bob', 'bob@example.com', 'inactive'),
('Carol', 'carol@example.com', 'active')
ON CONFLICT (email) DO NOTHING;

INSERT INTO orders(user_id, total) VALUES
(1, 19.99),
(1, 39.99),
(2, 9.99),
(3, 29.99)
ON CONFLICT DO NOTHING;


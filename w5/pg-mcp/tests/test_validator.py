"""Tests for SQL read-only validator."""

import pytest

from pg_mcp.security.validator import SQLValidator


@pytest.fixture
def validator(security_config) -> SQLValidator:
    """Build validator with default security policy."""
    return SQLValidator(security_config)


def test_simple_select_allowed(validator: SQLValidator) -> None:
    """Plain select should be allowed."""
    result = validator.validate("SELECT * FROM users")
    assert result.is_safe


def test_select_with_where_allowed(validator: SQLValidator) -> None:
    """Select with filter should be allowed."""
    result = validator.validate("SELECT name FROM users WHERE id = 1")
    assert result.is_safe


def test_select_with_join_allowed(validator: SQLValidator) -> None:
    """Join query should be allowed."""
    result = validator.validate("SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id")
    assert result.is_safe


def test_cte_select_allowed(validator: SQLValidator) -> None:
    """CTE with read-only body should be allowed."""
    sql = """
    WITH active_users AS (
        SELECT * FROM users WHERE status = 'active'
    )
    SELECT * FROM active_users
    """
    result = validator.validate(sql)
    assert result.is_safe


def test_complex_select_allowed(validator: SQLValidator) -> None:
    """Aggregation query should be allowed."""
    sql = """
    SELECT u.name, COUNT(o.id) AS order_count
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    WHERE u.created_at > '2024-01-01'
    GROUP BY u.id, u.name
    HAVING COUNT(o.id) > 5
    ORDER BY order_count DESC
    LIMIT 10
    """
    result = validator.validate(sql)
    assert result.is_safe


def test_insert_blocked(validator: SQLValidator) -> None:
    """Insert must be blocked."""
    result = validator.validate("INSERT INTO users VALUES (1, 'test')")
    assert not result.is_safe


def test_update_blocked(validator: SQLValidator) -> None:
    """Update must be blocked."""
    result = validator.validate("UPDATE users SET name = 'test' WHERE id = 1")
    assert not result.is_safe


def test_delete_blocked(validator: SQLValidator) -> None:
    """Delete must be blocked."""
    result = validator.validate("DELETE FROM users WHERE id = 1")
    assert not result.is_safe


def test_drop_blocked(validator: SQLValidator) -> None:
    """Drop must be blocked."""
    result = validator.validate("DROP TABLE users")
    assert not result.is_safe


def test_truncate_blocked(validator: SQLValidator) -> None:
    """Truncate must be blocked."""
    result = validator.validate("TRUNCATE TABLE users")
    assert not result.is_safe


def test_select_into_blocked(validator: SQLValidator) -> None:
    """SELECT INTO must be blocked."""
    result = validator.validate("SELECT * INTO new_table FROM users")
    assert not result.is_safe
    assert any("INTO" in issue.upper() for issue in result.detected_issues)


def test_pg_sleep_blocked(validator: SQLValidator) -> None:
    """Dangerous function should be blocked."""
    result = validator.validate("SELECT pg_sleep(1)")
    assert not result.is_safe
    assert any("pg_sleep" in issue for issue in result.detected_issues)


def test_lo_export_blocked(validator: SQLValidator) -> None:
    """lo_export should be blocked."""
    result = validator.validate("SELECT lo_export(12345, '/tmp/file')")
    assert not result.is_safe


def test_pg_read_file_blocked(validator: SQLValidator) -> None:
    """pg_read_file should be blocked."""
    result = validator.validate("SELECT pg_read_file('/etc/passwd')")
    assert not result.is_safe


def test_subquery_with_delete_blocked(validator: SQLValidator) -> None:
    """Write operation in nested query should still be blocked."""
    sql = "SELECT * FROM (DELETE FROM users RETURNING *) AS deleted"
    result = validator.validate(sql)
    assert not result.is_safe


def test_subquery_select_allowed(validator: SQLValidator) -> None:
    """Read-only subquery should pass."""
    sql = "SELECT * FROM (SELECT id, name FROM users) AS subq"
    result = validator.validate(sql)
    assert result.is_safe


def test_empty_sql_blocked(validator: SQLValidator) -> None:
    """Empty SQL should be blocked."""
    result = validator.validate("")
    assert not result.is_safe


def test_invalid_sql_blocked(validator: SQLValidator) -> None:
    """Invalid SQL should be blocked."""
    result = validator.validate("NOT VALID SQL AT ALL")
    assert not result.is_safe


def test_get_query_info_extracts_metadata(validator: SQLValidator) -> None:
    """Query metadata helper should return table and limit information."""
    info = validator.get_query_info("SELECT id FROM users ORDER BY id DESC LIMIT 5")
    assert info["statement_types"] == ["Select"]
    assert info["tables"] == ["users"]
    assert info["has_limit"] is True
    assert info["has_order_by"] is True


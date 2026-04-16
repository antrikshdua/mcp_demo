"""Unit tests for bigquery/query_safety.py — no GCP credentials required."""

import pytest

from bigquery.query_safety import is_query_safe, _has_multiple_statements_outside_quotes


# ── _has_multiple_statements_outside_quotes ────────────────────────────────────

class TestMultipleStatements:
    def test_single_statement_no_semicolon(self):
        assert _has_multiple_statements_outside_quotes("SELECT 1") is False

    def test_single_trailing_semicolon(self):
        assert _has_multiple_statements_outside_quotes("SELECT 1;") is False

    def test_two_statements(self):
        assert _has_multiple_statements_outside_quotes("SELECT 1; SELECT 2") is True

    def test_content_after_semicolon(self):
        assert _has_multiple_statements_outside_quotes("SELECT 1; -- DROP TABLE x") is True

    def test_semicolon_inside_single_quotes(self):
        assert _has_multiple_statements_outside_quotes("SELECT ';' AS x") is False

    def test_semicolon_inside_double_quotes(self):
        assert _has_multiple_statements_outside_quotes('SELECT ";" AS x') is False

    def test_semicolon_inside_backticks(self):
        assert _has_multiple_statements_outside_quotes("SELECT `a;b` FROM t") is False

    def test_doubled_single_quote_escape(self):
        # '' is a valid single-quote escape in SQL; must not confuse quote tracking
        assert _has_multiple_statements_outside_quotes("SELECT 'it''s fine' AS x") is False

    def test_two_semicolons(self):
        assert _has_multiple_statements_outside_quotes("SELECT 1;; ") is True


# ── is_query_safe ──────────────────────────────────────────────────────────────

class TestIsQuerySafe:
    # Safe queries
    def test_simple_select(self):
        ok, msg = is_query_safe("SELECT * FROM my_table LIMIT 10")
        assert ok is True
        assert msg == ""

    def test_select_with_where(self):
        ok, _ = is_query_safe("SELECT id, name FROM users WHERE active = TRUE LIMIT 100")
        assert ok is True

    def test_cte_with_clause(self):
        ok, _ = is_query_safe("WITH cte AS (SELECT 1 AS n) SELECT * FROM cte")
        assert ok is True

    def test_trailing_semicolon_allowed(self):
        ok, _ = is_query_safe("SELECT 1;")
        assert ok is True

    # Comment stripping
    def test_line_comment_stripped(self):
        ok, _ = is_query_safe("SELECT 1 -- DROP TABLE users")
        assert ok is True

    def test_block_comment_stripped(self):
        ok, _ = is_query_safe("SELECT /* DROP TABLE users */ 1")
        assert ok is True

    def test_comment_only_query(self):
        ok, msg = is_query_safe("-- just a comment")
        assert ok is False
        assert "only comments" in msg.lower()

    # Empty
    def test_empty_string(self):
        ok, msg = is_query_safe("")
        assert ok is False
        assert "empty" in msg.lower()

    def test_whitespace_only(self):
        ok, msg = is_query_safe("   ")
        assert ok is False
        assert "empty" in msg.lower()

    # Dangerous DML / DDL
    @pytest.mark.parametrize("bad_sql", [
        "DELETE FROM users WHERE id = 1",
        "UPDATE users SET name = 'x'",
        "INSERT INTO users VALUES (1, 'a')",
        "DROP TABLE users",
        "CREATE TABLE x (id INT)",
        "ALTER TABLE users ADD COLUMN y INT",
        "TRUNCATE TABLE users",
        "MERGE INTO target USING source ON target.id = source.id WHEN MATCHED THEN UPDATE SET name = source.name",
        "GRANT SELECT ON TABLE users TO USER 'alice'",
        "REVOKE SELECT ON TABLE users FROM USER 'bob'",
        "EXEC sp_help",
        "EXECUTE IMMEDIATE 'DROP TABLE x'",
        "CALL my_proc()",
        "EXPORT DATA OPTIONS(uri='gs://bucket/file') AS SELECT 1",
    ])
    def test_dangerous_keyword_rejected(self, bad_sql: str):
        ok, msg = is_query_safe(bad_sql)
        assert ok is False
        assert len(msg) > 0

    # Wrong start keyword
    def test_show_tables_rejected(self):
        ok, msg = is_query_safe("SHOW TABLES")
        assert ok is False

    def test_describe_rejected(self):
        ok, msg = is_query_safe("DESCRIBE my_table")
        assert ok is False

    # Multi-statement
    def test_multi_statement_rejected(self):
        ok, msg = is_query_safe("SELECT 1; SELECT 2")
        assert ok is False
        assert "multiple" in msg.lower()

    # Case-insensitivity
    def test_lowercase_select_allowed(self):
        ok, _ = is_query_safe("select * from t limit 1")
        assert ok is True

    def test_lowercase_drop_rejected(self):
        ok, _ = is_query_safe("select * from t where drop = 1")
        # 'drop' as a column value in string context should not be caught, but 'drop' as a bare word is
        # This tests the word-boundary regex
        ok2, _ = is_query_safe("drop table t")
        assert ok2 is False

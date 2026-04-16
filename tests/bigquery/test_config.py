"""Unit tests for bigquery/config.py — no GCP credentials required."""

import pytest

from bigquery.config import get_bigquery_config, BigQueryConfig, _parse_bool, _parse_list


class TestParseBool:
    @pytest.mark.parametrize("val,expected", [
        ("true", True), ("True", True), ("TRUE", True),
        ("1", True), ("yes", True), ("on", True),
        ("false", False), ("False", False), ("0", False),
        ("no", False), ("off", False), ("", False),
    ])
    def test_parse_bool(self, val: str, expected: bool):
        assert _parse_bool(val, default=False) is expected

    def test_empty_uses_default_true(self):
        assert _parse_bool("", default=True) is True


class TestParseList:
    def test_comma_separated(self):
        assert _parse_list("a,b,c") == ["a", "b", "c"]

    def test_spaces_trimmed(self):
        assert _parse_list(" a , b , c ") == ["a", "b", "c"]

    def test_empty_string(self):
        assert _parse_list("") == []

    def test_trailing_comma(self):
        assert _parse_list("a,b,") == ["a", "b"]


class TestGetBigQueryConfig:
    def test_returns_none_without_project_id(self, monkeypatch):
        monkeypatch.delenv("BIGQUERY_PROJECT_ID", raising=False)
        assert get_bigquery_config() is None

    def test_returns_config_with_project_id(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT_ID", "my-project")
        monkeypatch.setenv("BIGQUERY_LOCATION", "EU")
        cfg = get_bigquery_config()
        assert cfg is not None
        assert cfg.project_id == "my-project"
        assert cfg.location == "EU"

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT_ID", "proj")
        for var in [
            "BIGQUERY_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
            "BIGQUERY_ALLOWED_DATASETS", "BIGQUERY_MAX_BYTES_BILLED",
            "BIGQUERY_TIMEOUT", "BIGQUERY_MAX_RESULTS",
            "BIGQUERY_VECTOR_SEARCH_ENABLED",
        ]:
            monkeypatch.delenv(var, raising=False)
        cfg = get_bigquery_config()
        assert cfg is not None
        assert cfg.location == "US"
        assert cfg.key_file is None
        assert cfg.allowed_datasets == []
        assert cfg.max_bytes_billed == 109_951_162_777
        assert cfg.timeout == 30
        assert cfg.max_results == 20
        assert cfg.vector_search_enabled is False

    def test_allowed_datasets_parsed(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT_ID", "proj")
        monkeypatch.setenv("BIGQUERY_ALLOWED_DATASETS", "ds1,ds2,ds3")
        cfg = get_bigquery_config()
        assert cfg is not None
        assert cfg.allowed_datasets == ["ds1", "ds2", "ds3"]

    def test_vector_search_enabled(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT_ID", "proj")
        monkeypatch.setenv("BIGQUERY_VECTOR_SEARCH_ENABLED", "true")
        monkeypatch.setenv("BIGQUERY_EMBEDDING_MODEL", "proj.ds.model")
        monkeypatch.setenv("BIGQUERY_DISTANCE_TYPE", "EUCLIDEAN")
        cfg = get_bigquery_config()
        assert cfg is not None
        assert cfg.vector_search_enabled is True
        assert cfg.embedding_model == "proj.ds.model"
        assert cfg.distance_type == "EUCLIDEAN"

    def test_billing_cap_from_env(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT_ID", "proj")
        monkeypatch.setenv("BIGQUERY_MAX_BYTES_BILLED", "1000000")
        cfg = get_bigquery_config()
        assert cfg is not None
        assert cfg.max_bytes_billed == 1_000_000

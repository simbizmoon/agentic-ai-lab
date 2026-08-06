"""Tests for HTTP/HTML reader configuration."""

import pytest
from pydantic import ValidationError

from app.schemas.http_html_reader_config import HttpHtmlReaderConfig


def test_config_accepts_safe_defaults() -> None:
    config = HttpHtmlReaderConfig()

    assert config.timeout_seconds == 15
    assert config.maximum_bytes == 1_000_000
    assert config.maximum_redirects == 3


def test_config_rejects_invalid_limits() -> None:
    with pytest.raises(ValidationError):
        HttpHtmlReaderConfig(timeout_seconds=0)

    with pytest.raises(ValidationError):
        HttpHtmlReaderConfig(maximum_bytes=100)

    with pytest.raises(ValidationError):
        HttpHtmlReaderConfig(maximum_redirects=11)


def test_config_rejects_blank_user_agent() -> None:
    with pytest.raises(
        ValidationError,
        match="user_agent must not be blank",
    ):
        HttpHtmlReaderConfig(user_agent=" ")

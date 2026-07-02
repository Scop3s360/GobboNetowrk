"""
Tests: Configuration Loading (config/settings.py)
==================================================
Covers:
  - Default values load when environment variables are absent.
  - Explicit environment variable values override defaults.
  - Invalid log level raises ConfigurationError.
  - Invalid environment tag raises ConfigurationError.
  - Settings object is immutable (frozen dataclass).
"""

import os
import pytest

from config.settings import Settings
from core.exceptions import ConfigurationError


class TestSettingsDefaults:
    """Settings loads sensible defaults when env vars are not set."""

    def test_default_app_name(self, clean_env):
        settings = Settings.from_env()
        assert settings.app_name == "CallerOS"

    def test_default_version(self, clean_env):
        settings = Settings.from_env()
        assert settings.version == "1.0.0"

    def test_default_log_level(self, clean_env):
        settings = Settings.from_env()
        assert settings.log_level == "INFO"

    def test_default_environment(self, clean_env):
        settings = Settings.from_env()
        assert settings.environment == "development"

    def test_log_dir_is_path(self, clean_env):
        from pathlib import Path

        settings = Settings.from_env()
        assert isinstance(settings.log_dir, Path)


class TestSettingsFromEnv:
    """Environment variables are correctly read and stored."""

    def test_custom_app_name(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_APP_NAME", "MyApp")
        settings = Settings.from_env()
        assert settings.app_name == "MyApp"

    def test_custom_log_level_debug(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_LEVEL", "debug")
        settings = Settings.from_env()
        assert settings.log_level == "DEBUG"

    def test_production_environment(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_ENVIRONMENT", "production")
        settings = Settings.from_env()
        assert settings.environment == "production"

    def test_test_environment(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_ENVIRONMENT", "test")
        settings = Settings.from_env()
        assert settings.environment == "test"


class TestSettingsValidation:
    """Invalid values raise ConfigurationError."""

    def test_invalid_log_level_raises(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_LEVEL", "VERBOSE")
        with pytest.raises(ConfigurationError, match="Invalid log level"):
            Settings.from_env()

    def test_invalid_environment_raises(self, clean_env, monkeypatch):
        monkeypatch.setenv("CALLER_OS_ENVIRONMENT", "staging")
        with pytest.raises(ConfigurationError, match="Invalid environment"):
            Settings.from_env()


class TestSettingsImmutability:
    """Frozen dataclass prevents mutation."""

    def test_settings_is_immutable(self, clean_env):
        settings = Settings.from_env()
        with pytest.raises((AttributeError, TypeError)):
            settings.app_name = "changed"  # type: ignore[misc]

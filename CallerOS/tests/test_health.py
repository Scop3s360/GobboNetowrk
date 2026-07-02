"""
Tests: Health Validator (core/health.py)
========================================
Covers:
  - READY status when configuration, logging, and registry are all valid.
  - FAILED status when settings is None.
  - FAILED status when logging has no handlers.
  - FAILED status when registry is None.
  - HealthReport.is_ready property.
"""

import logging

import pytest

from config.settings import Settings
from core.health import HealthReport, HealthStatus, HealthValidator
from core.service_registry import ServiceRegistry
from app_logging.logger import reset_logging, setup_logging
from pathlib import Path


def _make_settings(**overrides) -> Settings:
    """Return a minimal valid Settings object for testing."""
    defaults = dict(
        app_name="TestApp",
        version="0.0.1",
        log_level="DEBUG",
        log_dir=Path("logs"),
        environment="test",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _isolated_logging():
    """Reset logging before and after every test in this module."""
    reset_logging()
    yield
    reset_logging()


class TestHealthValidatorReady:
    """Full valid state → READY."""

    def test_ready_when_all_valid(self, tmp_path):
        settings = _make_settings(log_dir=tmp_path / "logs")
        registry = ServiceRegistry()

        setup_logging(settings)

        validator = HealthValidator()
        report = validator.validate(settings=settings, registry=registry)

        assert report.status is HealthStatus.READY
        assert report.is_ready is True
        assert report.issues == []


class TestHealthValidatorFailed:
    """Individual failures cause FAILED status."""

    def test_failed_when_settings_none(self, tmp_path):
        settings = _make_settings(log_dir=tmp_path / "logs")
        setup_logging(settings)
        registry = ServiceRegistry()

        validator = HealthValidator()
        report = validator.validate(settings=None, registry=registry)

        assert report.status is HealthStatus.FAILED
        assert any("Configuration" in issue for issue in report.issues)

    def test_failed_when_no_logging_handlers(self):
        import logging as _logging

        settings = _make_settings()
        registry = ServiceRegistry()

        # pytest attaches its own LogCaptureHandler to the root logger during
        # collection, so reset_logging() alone is not enough to produce a
        # handler-free state.  We temporarily remove ALL handlers (including
        # pytest's) and restore them after the check.
        root = _logging.getLogger()
        original_handlers = list(root.handlers)
        for h in original_handlers:
            root.removeHandler(h)

        try:
            validator = HealthValidator()
            report = validator.validate(settings=settings, registry=registry)
        finally:
            # Always restore so the rest of the test session is not broken.
            for h in original_handlers:
                root.addHandler(h)

        assert report.status is HealthStatus.FAILED
        assert any("Logging" in issue for issue in report.issues)

    def test_failed_when_registry_none(self, tmp_path):
        settings = _make_settings(log_dir=tmp_path / "logs")
        setup_logging(settings)

        validator = HealthValidator()
        report = validator.validate(settings=settings, registry=None)

        assert report.status is HealthStatus.FAILED
        assert any("registry" in issue.lower() for issue in report.issues)

    def test_multiple_failures_reported(self):
        validator = HealthValidator()
        report = validator.validate(settings=None, registry=None)

        # At least configuration and registry issues should be present.
        assert len(report.issues) >= 2


class TestHealthReport:
    """HealthReport behaviour."""

    def test_is_ready_false_when_failed(self):
        report = HealthReport(status=HealthStatus.FAILED, issues=["problem"])
        assert report.is_ready is False

    def test_is_ready_false_when_ready_with_issues(self):
        # Defensive: READY with leftover issues should not be trusted.
        report = HealthReport(status=HealthStatus.READY, issues=["stale issue"])
        assert report.is_ready is False

    def test_is_ready_true_when_clean(self):
        report = HealthReport(status=HealthStatus.READY)
        assert report.is_ready is True

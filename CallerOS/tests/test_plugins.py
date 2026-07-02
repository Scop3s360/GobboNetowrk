"""
Tests: Plugin System (Stage 10)
===============================
Covers:
  - Manifest parsing & validation (missing keys, invalid formats).
  - Folder structure validation (missing files, entry point mismatch).
  - Plugin Registry operations, duplicate protection, and lookups.
  - PluginLoader executing dynamic module imports.
  - PluginManager coordinating loading, initialization, enable/disable status.
  - Resilience: a failing plugin must not block other plugins or crash the system.
  - Example Plugin verification.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from plugins.base_plugin import BasePlugin
from plugins.exceptions import (
    PluginError,
    PluginLoadError,
    PluginManifestError,
    PluginRegistrationError,
    PluginValidationError,
)
from plugins.loader import PluginLoader
from plugins.manager import PluginManager
from plugins.manifest import PluginManifest
from plugins.registry import PluginRegistry


# Helper content strings
VALID_MANIFEST_DICT = {
    "name": "test-plugin",
    "version": "1.2.3",
    "author": "Tester",
    "description": "Mock plugin for unit testing.",
    "entry": "plugin.py",
}

VALID_PLUGIN_CODE = """
from plugins.base_plugin import BasePlugin

class MockTestPlugin(BasePlugin):
    def initialise(self) -> None:
        self.init_run = True

    def shutdown(self) -> None:
        self.shutdown_run = True
"""

FAILING_PLUGIN_CODE = """
from plugins.base_plugin import BasePlugin

class FailingPlugin(BasePlugin):
    def initialise(self) -> None:
        raise ValueError("Initialization failed!")

    def shutdown(self) -> None:
        raise ValueError("Shutdown failed!")
"""


# ---------------------------------------------------------------------------
# Manifest & Validation Tests
# ---------------------------------------------------------------------------

class TestPluginManifest:
    def test_parse_valid_dict(self) -> None:
        manifest = PluginManifest.from_dict(VALID_MANIFEST_DICT)
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.2.3"
        assert manifest.entry == "plugin.py"

    def test_missing_fields_raises_validation_error(self) -> None:
        invalid_dict = VALID_MANIFEST_DICT.copy()
        del invalid_dict["entry"]
        with pytest.raises(PluginValidationError, match="missing required field"):
            PluginManifest.from_dict(invalid_dict)

    def test_empty_fields_raises_validation_error(self) -> None:
        invalid_dict = VALID_MANIFEST_DICT.copy()
        invalid_dict["name"] = " "
        with pytest.raises(PluginValidationError, match="must be a non-empty string"):
            PluginManifest.from_dict(invalid_dict)

    def test_from_file_invalid_json_raises_error(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text("{invalid json", encoding="utf-8")
        
        with pytest.raises(PluginManifestError, match="invalid JSON"):
            PluginManifest.from_file(manifest_file)


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    def test_registration_and_lookups(self) -> None:
        manifest = PluginManifest.from_dict(VALID_MANIFEST_DICT)
        class DummyPlugin(BasePlugin):
            def initialise(self) -> None: pass
            def shutdown(self) -> None: pass

        plugin = DummyPlugin(manifest)
        registry = PluginRegistry()
        
        registry.register(plugin)
        assert registry.is_registered("test-plugin") is True
        assert registry.get("test-plugin") is plugin
        assert len(registry.list_plugins()) == 1
        
        # Test enabling
        registry.enable("test-plugin")
        assert registry.is_enabled("test-plugin") is True
        assert len(registry.list_enabled()) == 1
        
        # Test disabling
        registry.disable("test-plugin")
        assert registry.is_enabled("test-plugin") is False

    def test_duplicate_registration_raises_error(self) -> None:
        manifest = PluginManifest.from_dict(VALID_MANIFEST_DICT)
        class DummyPlugin(BasePlugin):
            def initialise(self) -> None: pass
            def shutdown(self) -> None: pass

        plugin1 = DummyPlugin(manifest)
        plugin2 = DummyPlugin(manifest)
        registry = PluginRegistry()
        
        registry.register(plugin1)
        with pytest.raises(PluginRegistrationError, match="already registered"):
            registry.register(plugin2)


# ---------------------------------------------------------------------------
# Loader & Manager Lifecycle Tests
# ---------------------------------------------------------------------------

class TestPluginLoaderAndManager:
    @pytest.fixture
    def plugins_root(self, tmp_path: Path) -> Path:
        """Create a temporary directory structure representing plugins dir."""
        root = tmp_path / "plugins"
        root.mkdir()
        return root

    def test_loader_scans_and_instantiates_plugins(self, plugins_root: Path) -> None:
        # Create a valid plugin directory
        plugin_dir = plugins_root / "valid_plugin"
        plugin_dir.mkdir()
        
        (plugin_dir / "manifest.json").write_text(json.dumps(VALID_MANIFEST_DICT), encoding="utf-8")
        (plugin_dir / "plugin.py").write_text(VALID_PLUGIN_CODE, encoding="utf-8")
        
        loader = PluginLoader(plugins_root)
        loaded = loader.scan_and_load()
        
        assert len(loaded) == 1
        assert loaded[0].manifest.name == "test-plugin"
        assert isinstance(loaded[0], BasePlugin)

    def test_loader_skips_invalid_plugins_gracefully(self, plugins_root: Path) -> None:
        # 1. Plugin directory with missing entrypoint file
        bad_plugin_dir = plugins_root / "missing_entry"
        bad_plugin_dir.mkdir()
        (bad_plugin_dir / "manifest.json").write_text(json.dumps(VALID_MANIFEST_DICT), encoding="utf-8")
        
        # 2. Plugin directory with valid manifest and entrypoint
        good_plugin_dir = plugins_root / "valid_plugin"
        good_plugin_dir.mkdir()
        good_manifest = VALID_MANIFEST_DICT.copy()
        good_manifest["name"] = "good-plugin"
        (good_plugin_dir / "manifest.json").write_text(json.dumps(good_manifest), encoding="utf-8")
        (good_plugin_dir / "plugin.py").write_text(VALID_PLUGIN_CODE, encoding="utf-8")

        loader = PluginLoader(plugins_root)
        loaded = loader.scan_and_load()
        
        # Should skip bad_plugin_dir and successfully load good-plugin
        assert len(loaded) == 1
        assert loaded[0].manifest.name == "good-plugin"

    def test_loader_prevents_directory_traversal(self, plugins_root: Path, tmp_path: Path) -> None:
        # Create a directory outside the plugins root
        external_dir = tmp_path / "external_plugin"
        external_dir.mkdir()
        (external_dir / "manifest.json").write_text(json.dumps(VALID_MANIFEST_DICT), encoding="utf-8")
        (external_dir / "plugin.py").write_text(VALID_PLUGIN_CODE, encoding="utf-8")

        loader = PluginLoader(plugins_root)
        with pytest.raises(PluginLoadError, match="outside the approved plugins root"):
            loader.load_plugin(external_dir)

    def test_manager_coordinates_enable_disable(self, plugins_root: Path) -> None:
        plugin_dir = plugins_root / "valid_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(json.dumps(VALID_MANIFEST_DICT), encoding="utf-8")
        (plugin_dir / "plugin.py").write_text(VALID_PLUGIN_CODE, encoding="utf-8")

        manager = PluginManager(plugins_root)
        manager.discover_and_load()
        
        assert manager.registry.is_registered("test-plugin") is True
        assert manager.registry.is_enabled("test-plugin") is True
        
        # Get plugin instance and inspect state
        plugin_instance = manager.registry.get("test-plugin")
        assert getattr(plugin_instance, "init_run", False) is True
        
        # Disable plugin
        manager.disable_plugin("test-plugin")
        assert manager.registry.is_enabled("test-plugin") is False
        assert getattr(plugin_instance, "shutdown_run", False) is True

    def test_failing_plugin_initialisation_handled_by_manager(self, plugins_root: Path) -> None:
        plugin_dir = plugins_root / "failing_plugin"
        plugin_dir.mkdir()
        failing_manifest = VALID_MANIFEST_DICT.copy()
        failing_manifest["name"] = "failing-plugin"
        (plugin_dir / "manifest.json").write_text(json.dumps(failing_manifest), encoding="utf-8")
        (plugin_dir / "plugin.py").write_text(FAILING_PLUGIN_CODE, encoding="utf-8")

        manager = PluginManager(plugins_root)
        # Should not crash during discover_and_load (catches exception during enable/initialise)
        manager.discover_and_load()
        
        # The failing plugin should not end up registered/enabled
        assert manager.registry.is_registered("failing-plugin") is False

    def test_empty_plugins_directory_ok(self, plugins_root: Path) -> None:
        manager = PluginManager(plugins_root)
        manager.discover_and_load()
        assert len(manager.registry) == 0

    def test_extension_point_registration(self, plugins_root: Path) -> None:
        manager = PluginManager(plugins_root)
        
        class MockWorkerClass: pass
        class MockToolClass: pass
        class MockServiceClass: pass
        
        manager.register_worker(MockWorkerClass)
        manager.register_tool(MockToolClass)
        manager.register_service(MockServiceClass)
        
        assert MockWorkerClass in manager.registered_workers
        assert MockToolClass in manager.registered_tools
        assert MockServiceClass in manager.registered_services


# ---------------------------------------------------------------------------
# Production Example Plugin Tests
# ---------------------------------------------------------------------------

class TestProductionExamplePlugin:
    def test_example_plugin_loads_successfully(self) -> None:
        # Test loading the actual production ExamplePlugin from plugins/ directory
        project_root = Path(__file__).parent.parent
        plugins_dir = project_root / "plugins"
        
        loader = PluginLoader(plugins_dir)
        loaded = loader.scan_and_load()
        
        example_plugin = next((p for p in loaded if p.manifest.name == "example-plugin"), None)
        assert example_plugin is not None
        assert example_plugin.manifest.author == "James"
        
        # Verify lifecycle
        example_plugin.initialise()
        assert getattr(example_plugin, "log_message", None) == "initialized"
        example_plugin.shutdown()
        assert getattr(example_plugin, "log_message", None) == "shutdown"

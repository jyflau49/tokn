"""Tests for backend abstraction and migration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tokn.cli import cli
from tokn.core.backend.factory import (
    get_backend,
    get_config,
    migrate_backend,
    save_config,
)
from tokn.core.backend.local import LocalBackend
from tokn.core.token import RotationType, TokenLocation, TokenMetadata, TokenRegistry


class TestLocalBackend:
    def test_backend_type(self):
        """Test backend type property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalBackend(data_dir=tmpdir)
            assert backend.backend_type == "local"

    def test_load_empty_registry(self):
        """Test loading when no registry file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalBackend(data_dir=tmpdir)
            registry = backend.load_registry()
            assert isinstance(registry, TokenRegistry)
            assert len(registry.tokens) == 0

    def test_save_and_load_registry(self):
        """Test saving and loading a registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalBackend(data_dir=tmpdir)

            token = TokenMetadata(
                name="test-token",
                service="github",
                rotation_type=RotationType.MANUAL,
                locations=[TokenLocation(type="doppler", path="TEST")],
            )
            registry = TokenRegistry()
            registry.add_token(token)

            backend.save_registry(registry)

            # Verify file exists with secure permissions
            registry_file = Path(tmpdir) / "registry.json"
            assert registry_file.exists()
            assert oct(os.stat(registry_file).st_mode)[-3:] == "600"

            # Load and verify
            loaded = backend.load_registry()
            assert len(loaded.tokens) == 1
            assert loaded.get_token("test-token") is not None
            assert loaded.get_token("test-token").service == "github"

    def test_sync_returns_registry(self):
        """Test sync method returns loaded registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalBackend(data_dir=tmpdir)

            token = TokenMetadata(
                name="sync-test",
                service="cloudflare-account-token",
                rotation_type=RotationType.AUTO,
                locations=[],
            )
            registry = TokenRegistry()
            registry.add_token(token)
            backend.save_registry(registry)

            synced = backend.sync()
            assert len(synced.tokens) == 1
            assert synced.get_token("sync-test") is not None


class TestBackendFactory:
    def test_get_backend_local_default(self):
        """Test factory returns local backend by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("tokn.core.backend.factory.CONFIG_FILE", config_path):
                backend = get_backend()
                assert backend.backend_type == "local"

    def test_get_backend_explicit_type(self):
        """Test factory with explicit backend type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("tokn.core.backend.factory.CONFIG_FILE", config_path):
                backend = get_backend("local")
                assert backend.backend_type == "local"

    def test_get_backend_invalid_type(self):
        """Test factory raises error for invalid backend type."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            get_backend("invalid")

    def test_config_save_and_load(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_dir = Path(tmpdir)

            with patch("tokn.core.backend.factory.CONFIG_FILE", config_file):
                with patch("tokn.core.backend.factory.CONFIG_DIR", config_dir):
                    config = {"backend": "doppler", "doppler": {"project": "test"}}
                    save_config(config)

                    assert config_file.exists()

                    loaded = get_config()
                    assert loaded["backend"] == "doppler"
                    assert loaded["doppler"]["project"] == "test"


class TestBackendMigration:
    def test_migrate_local_to_local_fails(self):
        """Test migration to same backend fails."""
        success, message, count = migrate_backend("local", "local")
        assert not success
        assert "same" in message.lower()

    def test_migrate_empty_source_fails(self):
        """Test migration from empty source fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("tokn.core.backend.factory.CONFIG_FILE", config_path):
                with patch("tokn.core.backend.factory.CONFIG_DIR", Path(tmpdir)):
                    # Create empty local backend
                    local_backend = LocalBackend(data_dir=tmpdir)
                    local_backend.save_registry(TokenRegistry())

                    with patch("tokn.core.backend.factory.get_backend") as mock_get:
                        mock_get.return_value = local_backend
                        success, message, count = migrate_backend("local", "doppler")
                        assert not success
                        assert "No tokens" in message


class TestBackendCLI:
    def test_backend_show(self):
        """Test backend show command."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("tokn.cli.get_config") as mock_config:
                mock_config.return_value = {
                    "backend": "local",
                    "local": {"data_dir": tmpdir},
                }
                with patch("tokn.cli.get_backend") as mock_backend:
                    mock_instance = MagicMock()
                    mock_instance.load_registry.return_value = TokenRegistry()
                    mock_backend.return_value = mock_instance

                    result = runner.invoke(cli, ["backend", "show"])

                    assert result.exit_code == 0
                    assert "local" in result.output

    def test_backend_set_local(self):
        """Test backend set command for local."""
        runner = CliRunner()

        with patch("tokn.cli.get_config") as mock_get_config:
            mock_get_config.return_value = {"backend": "doppler"}
            with patch("tokn.cli.save_config") as mock_save:
                with patch("tokn.cli.get_backend") as mock_backend:
                    mock_instance = MagicMock()
                    mock_instance.load_registry.return_value = TokenRegistry()
                    mock_backend.return_value = mock_instance

                    result = runner.invoke(cli, ["backend", "set", "local"])

                    assert result.exit_code == 0
                    assert "Backend set to" in result.output
                    mock_save.assert_called_once()

    def test_backend_migrate_same_fails(self):
        """Test migration to same backend fails."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["backend", "migrate", "--from", "local", "--to", "local"]
        )

        assert result.exit_code == 1
        assert "same" in result.output.lower()

    def test_backend_migrate_with_force(self):
        """Test migration with --force flag."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with tokens
            source_backend = LocalBackend(data_dir=Path(tmpdir) / "source")
            token = TokenMetadata(
                name="migrate-test",
                service="github",
                rotation_type=RotationType.MANUAL,
                locations=[],
            )
            registry = TokenRegistry()
            registry.add_token(token)
            source_backend.save_registry(registry)

            with patch("tokn.cli.get_backend") as mock_get:
                with patch("tokn.cli.migrate_backend") as mock_migrate:
                    mock_migrate.return_value = (True, "Migrated 1 token(s)", 1)

                    # Mock destination check
                    mock_dest = MagicMock()
                    mock_dest.load_registry.return_value = TokenRegistry()
                    mock_get.return_value = mock_dest

                    result = runner.invoke(
                        cli,
                        [
                            "backend",
                            "migrate",
                            "--from",
                            "local",
                            "--to",
                            "doppler",
                            "--force",
                        ],
                    )

                    assert result.exit_code == 0
                    mock_migrate.assert_called_once_with("local", "doppler")

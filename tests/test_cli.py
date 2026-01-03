"""Integration tests for CLI commands."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tokn.cli import cli
from tokn.core.token import RotationType, TokenLocation, TokenMetadata, TokenRegistry


class TestTrackCommand:
    def test_track_token_success(self):
        """Test tracking a new token."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(
                cli,
                [
                    "track",
                    "test-token",
                    "--service",
                    "github",
                    "--rotation-type",
                    "manual",
                    "--location",
                    "doppler:TEST_TOKEN:project=test,config=dev",
                ],
            )

            assert result.exit_code == 0
            assert "tracked successfully" in result.output
            mock_instance.save_registry.assert_called_once()

    def test_track_token_with_metadata_parsing(self):
        """Test location metadata is correctly parsed."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(
                cli,
                [
                    "track",
                    "test-token",
                    "--service",
                    "cloudflare",
                    "--rotation-type",
                    "auto",
                    "--location",
                    "doppler:CF_TOKEN:project=myproj,config=prod",
                ],
            )

            assert result.exit_code == 0

            saved_registry = mock_instance.save_registry.call_args[0][0]
            token = saved_registry.get_token("test-token")
            assert token is not None
            assert len(token.locations) == 1
            assert token.locations[0].type == "doppler"
            assert token.locations[0].path == "CF_TOKEN"
            assert token.locations[0].metadata == {
                "project": "myproj",
                "config": "prod",
            }

    def test_track_duplicate_token(self):
        """Test tracking duplicate token fails."""
        runner = CliRunner()

        existing_token = TokenMetadata(
            name="existing",
            service="github",
            rotation_type=RotationType.MANUAL,
            locations=[],
        )
        registry = TokenRegistry()
        registry.add_token(existing_token)

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = registry
            mock_backend.return_value = mock_instance

            result = runner.invoke(
                cli,
                [
                    "track",
                    "existing",
                    "--service",
                    "github",
                    "--rotation-type",
                    "manual",
                    "--location",
                    "doppler:TOKEN",
                ],
            )

            assert result.exit_code == 1
            assert "already exists" in result.output

    def test_track_invalid_location_format(self):
        """Test invalid location format is rejected."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(
                cli,
                [
                    "track",
                    "test-token",
                    "--service",
                    "github",
                    "--rotation-type",
                    "manual",
                    "--location",
                    "invalid-format",
                ],
            )

            assert result.exit_code == 1
            assert "Invalid location format" in result.output

    def test_track_no_locations(self):
        """Test tracking without locations fails."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(
                cli,
                [
                    "track",
                    "test-token",
                    "--service",
                    "github",
                    "--rotation-type",
                    "manual",
                ],
            )

            assert result.exit_code == 1
            assert "At least one location is required" in result.output


class TestListCommand:
    def test_list_no_tokens(self):
        """Test list with no tokens tracked."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            assert "No tokens tracked" in result.output

    def test_list_with_tokens(self):
        """Test list displays tracked tokens."""
        runner = CliRunner()

        token = TokenMetadata(
            name="test-token",
            service="github",
            rotation_type=RotationType.MANUAL,
            locations=[TokenLocation(type="doppler", path="TEST")],
            expires_at=datetime.now() + timedelta(days=30),
        )
        registry = TokenRegistry()
        registry.add_token(token)

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = registry
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            assert "test-token" in result.output
            assert "github" in result.output


class TestRemoveCommand:
    def test_remove_existing_token(self):
        """Test removing an existing token."""
        runner = CliRunner()

        token = TokenMetadata(
            name="to-remove",
            service="github",
            rotation_type=RotationType.MANUAL,
            locations=[],
        )
        registry = TokenRegistry()
        registry.add_token(token)

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = registry
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["remove", "to-remove"])

            assert result.exit_code == 0
            assert "removed" in result.output
            mock_instance.save_registry.assert_called_once()

    def test_remove_nonexistent_token(self):
        """Test removing non-existent token."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["remove", "nonexistent"])

            assert result.exit_code == 1
            assert "not found" in result.output


class TestDescribeCommand:
    def test_describe_existing_token(self):
        """Test showing details for existing token."""
        runner = CliRunner()

        token = TokenMetadata(
            name="test-token",
            service="github",
            rotation_type=RotationType.MANUAL,
            locations=[
                TokenLocation(
                    type="doppler",
                    path="GITHUB_TOKEN",
                    metadata={"project": "test", "config": "dev"},
                )
            ],
            expires_at=datetime.now() + timedelta(days=30),
            notes="Test notes",
        )
        registry = TokenRegistry()
        registry.add_token(token)

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = registry
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["describe", "test-token"])

            assert result.exit_code == 0
            assert "test-token" in result.output
            assert "github" in result.output
            assert "doppler" in result.output
            assert "Test notes" in result.output

    def test_describe_nonexistent_token(self):
        """Test describe for non-existent token."""
        runner = CliRunner()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.load_registry.return_value = TokenRegistry()
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["describe", "nonexistent"])

            assert result.exit_code == 1
            assert "not found" in result.output


class TestSyncCommand:
    def test_sync_success(self):
        """Test syncing metadata from Doppler."""
        runner = CliRunner()

        registry = TokenRegistry()
        registry.last_sync = datetime.now()

        with patch("tokn.cli.DopplerBackend") as mock_backend:
            mock_instance = MagicMock()
            mock_instance.sync.return_value = registry
            mock_backend.return_value = mock_instance

            result = runner.invoke(cli, ["sync"])

            assert result.exit_code == 0
            assert "Synced" in result.output
            mock_instance.sync.assert_called_once()

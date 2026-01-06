"""Tests for location handlers with security focus."""

import stat

from tokn.locations.local_files import (
    SECURE_FILE_MODE,
    GitCredentialsHandler,
    LinodeCLIHandler,
    TerraformCredentialsHandler,
)


class TestGitCredentialsHandler:
    def test_write_token_creates_secure_file(self, tmp_path):
        """Verify credential files are created with 0600 permissions."""
        handler = GitCredentialsHandler()
        cred_file = tmp_path / ".git-credentials"

        result = handler.write_token(str(cred_file), "test_token_123", username="git")

        assert result is True
        assert cred_file.exists()

        # Check file permissions are secure (owner read/write only)
        file_mode = stat.S_IMODE(cred_file.stat().st_mode)
        assert file_mode == SECURE_FILE_MODE, f"Expected 0600, got {oct(file_mode)}"

    def test_write_token_preserves_non_github_entries(self, tmp_path):
        """Verify other credential entries are preserved."""
        handler = GitCredentialsHandler()
        cred_file = tmp_path / ".git-credentials"
        cred_file.write_text("https://user:token@gitlab.com\n")

        handler.write_token(str(cred_file), "new_github_token", username="git")

        content = cred_file.read_text()
        assert "gitlab.com" in content
        assert "github.com" in content

    def test_backup_returns_content_not_file_path(self, tmp_path):
        """Verify backup returns content (in-memory) not file path."""
        handler = GitCredentialsHandler()
        cred_file = tmp_path / ".git-credentials"
        original_content = "https://git:secret@github.com\n"
        cred_file.write_text(original_content)

        backup = handler.backup_token(str(cred_file))

        # Should return content, not a file path
        assert backup == original_content
        # No backup file should be created on disk
        backup_file = tmp_path / ".git-credentials.tokn-backup"
        assert not backup_file.exists()

    def test_rollback_restores_from_content(self, tmp_path):
        """Verify rollback restores from in-memory content."""
        handler = GitCredentialsHandler()
        cred_file = tmp_path / ".git-credentials"
        original_content = "https://git:original@github.com\n"
        cred_file.write_text(original_content)

        # Modify file
        cred_file.write_text("https://git:modified@github.com\n")

        # Rollback using original content
        result = handler.rollback_token(str(cred_file), original_content)

        assert result is True
        assert cred_file.read_text() == original_content


class TestLinodeCLIHandler:
    def test_write_token_creates_secure_file(self, tmp_path):
        """Verify linode-cli config is created with 0600 permissions."""
        handler = LinodeCLIHandler()
        config_file = tmp_path / "linode-cli"

        result = handler.write_token(str(config_file), "test_linode_token")

        assert result is True
        assert config_file.exists()

        file_mode = stat.S_IMODE(config_file.stat().st_mode)
        assert file_mode == SECURE_FILE_MODE

    def test_read_token_extracts_correctly(self, tmp_path):
        """Verify token extraction from linode-cli config."""
        handler = LinodeCLIHandler()
        config_file = tmp_path / "linode-cli"
        config_file.write_text("[DEFAULT]\ntoken = my_secret_token\nregion = us-east\n")

        token = handler.read_token(str(config_file))

        assert token == "my_secret_token"


class TestTerraformCredentialsHandler:
    def test_write_token_creates_secure_file(self, tmp_path):
        """Verify terraform credentials are created with 0600 permissions."""
        handler = TerraformCredentialsHandler()
        cred_file = tmp_path / "credentials.tfrc.json"

        result = handler.write_token(str(cred_file), "tf_token_123")

        assert result is True
        assert cred_file.exists()

        file_mode = stat.S_IMODE(cred_file.stat().st_mode)
        assert file_mode == SECURE_FILE_MODE

    def test_read_token_from_json(self, tmp_path):
        """Verify token extraction from terraform credentials JSON."""
        handler = TerraformCredentialsHandler()
        cred_file = tmp_path / "credentials.tfrc.json"
        cred_file.write_text(
            '{"credentials": {"app.terraform.io": {"token": "secret"}}}'
        )

        token = handler.read_token(str(cred_file))

        assert token == "secret"

    def test_preserves_other_hosts(self, tmp_path):
        """Verify other terraform hosts are preserved."""
        handler = TerraformCredentialsHandler()
        cred_file = tmp_path / "credentials.tfrc.json"
        cred_file.write_text(
            '{"credentials": {"other.terraform.io": {"token": "other"}}}'
        )

        handler.write_token(str(cred_file), "new_token")

        import json

        data = json.loads(cred_file.read_text())
        assert data["credentials"]["other.terraform.io"]["token"] == "other"
        assert data["credentials"]["app.terraform.io"]["token"] == "new_token"

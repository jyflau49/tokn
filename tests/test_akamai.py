"""Tests for Akamai EdgeGrid provider and Edgerc location handler."""

import os
from unittest.mock import MagicMock, patch

from tokn.locations.edgerc import EdgercHandler
from tokn.providers.akamai import AkamaiEdgeGridProvider


class TestEdgercHandler:
    """Tests for EdgercHandler location handler."""

    def test_read_token_from_section(self, tmp_path):
        """Test reading client_secret from .edgerc section."""
        edgerc_content = """[default]
client_secret = test-secret-123
host = akab-test.luna.akamaiapis.net
access_token = akab-access-token
client_token = akab-client-token

[other]
client_secret = other-secret
host = akab-other.luna.akamaiapis.net
access_token = akab-other-access
client_token = akab-other-client
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(edgerc_content)

        handler = EdgercHandler()

        result = handler.read_token(str(edgerc_path), section="default")
        assert result == "test-secret-123"

        result = handler.read_token(str(edgerc_path), section="other")
        assert result == "other-secret"

    def test_read_token_nonexistent_section(self, tmp_path):
        """Test reading from non-existent section returns None."""
        edgerc_content = """[default]
client_secret = test-secret
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(edgerc_content)

        handler = EdgercHandler()
        result = handler.read_token(str(edgerc_path), section="nonexistent")
        assert result is None

    def test_read_token_nonexistent_file(self):
        """Test reading from non-existent file returns None."""
        handler = EdgercHandler()
        result = handler.read_token("/nonexistent/path/.edgerc", section="default")
        assert result is None

    def test_write_token_updates_section(self, tmp_path):
        """Test writing client_secret updates only the specified section."""
        edgerc_content = """[default]
client_secret = old-secret
host = akab-test.luna.akamaiapis.net
access_token = akab-access-token
client_token = akab-client-token

[other]
client_secret = other-secret
host = akab-other.luna.akamaiapis.net
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(edgerc_content)

        handler = EdgercHandler()
        result = handler.write_token(
            str(edgerc_path),
            "new-secret-456",
            section="default",
            client_token="new-client-token",
        )

        assert result is True

        updated_content = edgerc_path.read_text()
        assert "new-secret-456" in updated_content
        assert "new-client-token" in updated_content
        assert "other-secret" in updated_content
        assert "akab-test.luna.akamaiapis.net" in updated_content

    def test_write_token_creates_file(self, tmp_path):
        """Test writing to non-existent file creates it."""
        edgerc_path = tmp_path / "subdir" / ".edgerc"

        handler = EdgercHandler()
        result = handler.write_token(str(edgerc_path), "new-secret", section="default")

        assert result is True
        assert edgerc_path.exists()
        assert "new-secret" in edgerc_path.read_text()

    def test_write_token_sets_secure_permissions(self, tmp_path):
        """Test that written file has 0600 permissions."""
        edgerc_path = tmp_path / ".edgerc"

        handler = EdgercHandler()
        handler.write_token(str(edgerc_path), "secret", section="default")

        file_mode = os.stat(edgerc_path).st_mode & 0o777
        assert file_mode == 0o600

    def test_backup_and_rollback(self, tmp_path):
        """Test backup and rollback functionality."""
        original_content = """[default]
client_secret = original-secret
host = akab-test.luna.akamaiapis.net
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(original_content)

        handler = EdgercHandler()

        backup = handler.backup_token(str(edgerc_path))
        assert backup == original_content

        handler.write_token(str(edgerc_path), "new-secret", section="default")
        assert "new-secret" in edgerc_path.read_text()

        result = handler.rollback_token(str(edgerc_path), backup)
        assert result is True
        assert edgerc_path.read_text() == original_content

    def test_get_section_credentials(self, tmp_path):
        """Test getting all credentials from a section."""
        edgerc_content = """[default]
client_secret = test-secret
host = akab-test.luna.akamaiapis.net
access_token = akab-access-token
client_token = akab-client-token
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(edgerc_content)

        handler = EdgercHandler()
        creds = handler.get_section_credentials(str(edgerc_path), "default")

        assert creds is not None
        assert creds["client_secret"] == "test-secret"
        assert creds["host"] == "akab-test.luna.akamaiapis.net"
        assert creds["access_token"] == "akab-access-token"
        assert creds["client_token"] == "akab-client-token"


class TestAkamaiEdgeGridProvider:
    """Tests for AkamaiEdgeGridProvider."""

    def test_supports_auto_rotation(self):
        """Test that provider supports auto rotation."""
        provider = AkamaiEdgeGridProvider()
        assert provider.supports_auto_rotation is True

    def test_provider_name(self):
        """Test provider name."""
        provider = AkamaiEdgeGridProvider()
        assert provider.name == "Akamai EdgeGrid Credentials"

    @patch("tokn.providers.akamai.requests.Session")
    @patch("tokn.providers.akamai.EdgeGridAuth")
    @patch("tokn.providers.akamai.EdgeRc")
    def test_rotate_success(self, mock_edgerc, mock_auth, mock_session, tmp_path):
        """Test successful credential rotation."""
        edgerc_content = """[default]
client_secret = old-secret
host = akab-test.luna.akamaiapis.net
access_token = akab-access-token
client_token = akab-old-client-token
"""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text(edgerc_content)

        mock_edgerc_instance = MagicMock()
        mock_edgerc_instance.get.side_effect = lambda section, key: {
            "host": "akab-test.luna.akamaiapis.net",
            "client_token": "akab-old-client-token",
        }.get(key)
        mock_edgerc.return_value = mock_edgerc_instance

        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        list_response = MagicMock()
        list_response.json.return_value = [
            {
                "clientToken": "akab-old-client-token",
                "credentialId": 12345,
                "status": "ACTIVE",
            }
        ]
        list_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = {
            "clientSecret": "new-secret-xyz",
            "clientToken": "akab-new-client-token",
            "credentialId": 67890,
            "status": "ACTIVE",
        }
        create_response.raise_for_status = MagicMock()

        update_response = MagicMock()
        update_response.raise_for_status = MagicMock()

        mock_session_instance.get.return_value = list_response
        mock_session_instance.post.return_value = create_response
        mock_session_instance.put.return_value = update_response

        provider = AkamaiEdgeGridProvider()
        result = provider.rotate(
            "old-secret",
            edgerc_path=str(edgerc_path),
            section="default",
        )

        assert result.success is True
        assert result.new_token == "new-secret-xyz"
        assert result.expires_at is not None

        assert provider.get_new_client_token() == "akab-new-client-token"

    @patch("tokn.providers.akamai.EdgeRc")
    def test_rotate_file_not_found(self, mock_edgerc):
        """Test rotation fails when .edgerc file not found."""
        mock_edgerc.side_effect = FileNotFoundError("File not found")

        provider = AkamaiEdgeGridProvider()
        result = provider.rotate(
            "old-secret",
            edgerc_path="/nonexistent/.edgerc",
            section="default",
        )

        assert result.success is False
        assert ".edgerc file not found" in result.error

    @patch("tokn.providers.akamai.requests.Session")
    @patch("tokn.providers.akamai.EdgeGridAuth")
    @patch("tokn.providers.akamai.EdgeRc")
    def test_rotate_credential_not_found(
        self, mock_edgerc, mock_auth, mock_session, tmp_path
    ):
        """Test rotation fails when credential not found in list."""
        edgerc_path = tmp_path / ".edgerc"
        edgerc_path.write_text("[default]\nclient_secret = x\nhost = y\n")

        mock_edgerc_instance = MagicMock()
        mock_edgerc_instance.get.side_effect = lambda section, key: {
            "host": "akab-test.luna.akamaiapis.net",
            "client_token": "akab-missing-token",
        }.get(key)
        mock_edgerc.return_value = mock_edgerc_instance

        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        list_response = MagicMock()
        list_response.json.return_value = [
            {"clientToken": "akab-different-token", "credentialId": 12345}
        ]
        list_response.raise_for_status = MagicMock()
        mock_session_instance.get.return_value = list_response

        provider = AkamaiEdgeGridProvider()
        result = provider.rotate(
            "old-secret",
            edgerc_path=str(edgerc_path),
            section="default",
        )

        assert result.success is False
        assert "Could not find credential" in result.error

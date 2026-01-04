"""Integration tests for rotation orchestrator with service-specific logic."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from tokn.core.rotation import RotationOrchestrator
from tokn.core.token import RotationType, TokenLocation, TokenMetadata
from tokn.providers.base import RotationResult


class TestAkamaiRotationIntegration:
    """Regression tests for Akamai-specific rotation logic."""

    def test_akamai_service_name_triggers_client_token_update(self):
        """Regression test: Ensure 'akamai' service name triggers client_token update.

        This test prevents a bug where service name was changed from 'akamai-edgegrid'
        to 'akamai' in v0.7.0, but the rotation logic still checked for the old name,
        causing client_token to not be updated in .edgerc files.
        """
        orchestrator = RotationOrchestrator()

        # Create token metadata with 'akamai' service
        token_metadata = TokenMetadata(
            name="test-akamai",
            service="akamai",  # Current service name
            rotation_type=RotationType.AUTO,
            locations=[
                TokenLocation(
                    type="edgerc",
                    path="~/.edgerc",
                    metadata={"section": "test"},
                )
            ],
        )

        # Mock provider to return successful rotation with new client_token
        mock_provider = MagicMock()
        mock_provider.supports_auto_rotation = True
        mock_provider.rotate.return_value = RotationResult(
            success=True,
            new_token="new-client-secret",
            expires_at=datetime.now() + timedelta(days=90),
        )
        mock_provider.get_new_client_token.return_value = "new-client-token"

        # Mock location handler
        mock_handler = MagicMock()
        mock_handler.backup_token.return_value = "backup-content"
        mock_handler.write_token.return_value = True

        # Inject mocks
        orchestrator.providers["akamai"] = mock_provider
        orchestrator.location_handlers["edgerc"] = mock_handler

        # Mock backend
        with patch.object(orchestrator.backend, "load_registry") as mock_load:
            with patch.object(orchestrator.backend, "save_registry"):
                mock_registry = MagicMock()
                mock_load.return_value = mock_registry

                # Execute rotation
                success, message, locations = orchestrator.rotate_token(token_metadata)

                # Verify rotation succeeded
                assert success is True
                assert "edgerc:~/.edgerc" in locations

                # CRITICAL: Verify client_token was passed to location handler
                mock_handler.write_token.assert_called_once()
                call_args = mock_handler.write_token.call_args

                # Check that client_token was in the metadata
                assert call_args[0][0] == "~/.edgerc"  # path
                assert call_args[0][1] == "new-client-secret"  # token
                assert "client_token" in call_args[1]  # kwargs
                assert call_args[1]["client_token"] == "new-client-token"

    def test_non_akamai_service_does_not_trigger_client_token_update(self):
        """Verify non-Akamai services don't trigger client_token logic."""
        orchestrator = RotationOrchestrator()

        # Create token metadata with non-Akamai service
        token_metadata = TokenMetadata(
            name="test-linode",
            service="linode",
            rotation_type=RotationType.AUTO,
            locations=[
                TokenLocation(
                    type="linode-cli",
                    path="~/.config/linode-cli",
                    metadata={},
                )
            ],
        )

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.supports_auto_rotation = True
        mock_provider.rotate.return_value = RotationResult(
            success=True,
            new_token="new-linode-token",
            expires_at=datetime.now() + timedelta(days=90),
        )

        # Mock location handler
        mock_handler = MagicMock()
        mock_handler.backup_token.return_value = "backup-content"
        mock_handler.write_token.return_value = True

        # Inject mocks
        orchestrator.providers["linode"] = mock_provider
        orchestrator.location_handlers["linode-cli"] = mock_handler

        # Mock backend
        with patch.object(orchestrator.backend, "load_registry") as mock_load:
            with patch.object(orchestrator.backend, "save_registry"):
                mock_registry = MagicMock()
                mock_load.return_value = mock_registry

                # Execute rotation
                success, message, locations = orchestrator.rotate_token(token_metadata)

                # Verify rotation succeeded
                assert success is True

                # Verify client_token was NOT passed (no client_token in kwargs)
                mock_handler.write_token.assert_called_once()
                call_args = mock_handler.write_token.call_args
                assert "client_token" not in call_args[1]  # kwargs should not have it

"""Generic provider for unsupported/custom token services.

This provider allows users to track tokens from services not officially supported
by tokn. It provides basic tracking and manual rotation instructions.
"""

from tokn.providers.base import RotationResult, TokenProvider


class OtherProvider(TokenProvider):
    """Provider for custom/unsupported token services.

    This is a generic provider that only supports manual rotation.
    Users can leverage the --notes field to add custom rotation instructions.
    """

    def __init__(self):
        super().__init__("Other/Custom Service")

    @property
    def supports_auto_rotation(self) -> bool:
        return False

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        return RotationResult(
            success=False,
            error="Manual rotation required for custom services",
        )

    def get_manual_instructions(self) -> str:
        return """
Manual rotation required for this custom service.

Check the token's notes field for provider-specific instructions:
  tokn describe <token-name>

General steps:
1. Rotate the token via your service provider's web UI or API
2. Update all locations manually or via tokn update command
3. Update expiry: tokn update <name> --expiry-days <days>
"""

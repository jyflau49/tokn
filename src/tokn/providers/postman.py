"""Postman API Key rotation provider.

NOTE: Postman API keys cannot be programmatically rotated via API.
This provider validates the token and provides manual rotation instructions.
"""

import httpx

from tokn.providers.base import RotationResult, TokenProvider


class PostmanProvider(TokenProvider):
    """Provider for Postman API Key rotation.

    Postman API keys must be manually rotated via the web UI.
    This provider validates the current token and provides instructions.
    """

    API_BASE = "https://api.getpostman.com"

    def __init__(self):
        super().__init__("Postman API Key")

    @property
    def supports_auto_rotation(self) -> bool:
        return False

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        if not self._validate_token(current_token):
            return RotationResult(
                success=False, error="Current token is invalid or expired"
            )

        return RotationResult(
            success=False,
            error="Postman API keys require manual rotation. See instructions.",
        )

    def _validate_token(self, token: str) -> bool:
        """Validate token by checking /me endpoint."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.API_BASE}/me", headers={"X-API-Key": token}
                )
                return response.status_code == 200
        except Exception:
            return False

    def get_manual_instructions(self) -> str:
        return """
Manual rotation required for Postman API Key:

1. Go to: https://go.postman.co/settings/me/api-keys
2. Click "..." next to your key → "Regenerate API Key"
3. Copy the new key
4. Update locations:
   - Doppler: doppler secrets set POSTMAN_API_KEY=<new_token>
   - Postman Environment: tokn handles this automatically
5. Run: tokn update <name> --expiry-days <days>
"""

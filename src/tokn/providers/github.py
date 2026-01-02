"""GitHub Personal Access Token rotation provider.

NOTE: GitHub PATs (both classic and fine-grained) cannot be programmatically
rotated via API without an OAuth App or GitHub App. This provider validates
the token and provides manual rotation instructions.

For true auto-rotation, consider:
1. Using GitHub App installation tokens (short-lived, auto-rotate)
2. Setting up an OAuth App for token refresh
"""

import httpx

from tokn.providers.base import RotationResult, TokenProvider


class GitHubProvider(TokenProvider):
    API_BASE = "https://api.github.com"

    def __init__(self):
        super().__init__("GitHub PAT")

    @property
    def supports_auto_rotation(self) -> bool:
        # GitHub PATs cannot be auto-rotated without OAuth App
        # Mark as False to trigger manual instructions
        return False

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        # Validate current token is still working
        if not self._validate_token(current_token):
            return RotationResult(
                success=False,
                error="Current token is invalid or expired"
            )

        return RotationResult(
            success=False,
            error="GitHub PATs require manual rotation. See instructions."
        )

    def _validate_token(self, token: str) -> bool:
        """Validate token by checking user endpoint."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.API_BASE}/user",
                    headers={"Authorization": f"token {token}"}
                )
                return response.status_code == 200
        except Exception:
            return False

    def get_manual_instructions(self) -> str:
        return """
Manual rotation required for GitHub PAT:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" (fine-grained recommended)
3. Set expiration to 30 days
4. Select required permissions (repo, etc.)
5. Generate and copy the new token
6. Update in Doppler: doppler secrets set GITHUB_TOKEN=<new_token>
7. Update ~/.git-credentials manually or run:
   git credential reject <<EOF
   protocol=https
   host=github.com
   EOF
8. Run: tokn sync to update metadata
"""

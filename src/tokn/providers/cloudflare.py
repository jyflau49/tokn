"""Cloudflare API Token rotation provider.

Rotates Cloudflare API tokens by:
1. Getting current token details (including policies)
2. Creating new token with same policies
3. Deleting old token after successful creation
"""

from datetime import datetime

import httpx

from tokn.providers.base import RotationResult, TokenProvider


class CloudflareProvider(TokenProvider):
    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        super().__init__("Cloudflare API Token")

    @property
    def supports_auto_rotation(self) -> bool:
        return True

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        date_str = datetime.now().strftime('%Y%m%d')
        name = kwargs.get("name", f"tokn-rotated-{date_str}")

        try:
            with httpx.Client() as client:
                # Get current token details including policies
                token_details = self._get_token_details(client, current_token)
                if not token_details:
                    return RotationResult(
                        success=False,
                        error="Could not retrieve current token details"
                    )

                old_token_id = token_details["id"]
                policies = token_details.get("policies", [])

                if not policies:
                    return RotationResult(
                        success=False,
                        error="Current token has no policies - cannot replicate"
                    )

                # Create new token with same policies
                new_token = self._create_token(
                    client, current_token, name, policies
                )

                # Delete old token only after successful creation
                self._delete_token(client, current_token, old_token_id)

                return RotationResult(success=True, new_token=new_token)

        except httpx.HTTPStatusError as e:
            return RotationResult(
                success=False,
                error=f"Cloudflare API error: {e.response.status_code}"
            )
        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def _get_token_details(
        self, client: httpx.Client, token: str
    ) -> dict | None:
        """Get current token details including policies."""
        try:
            # First verify and get token ID
            verify_resp = client.get(
                f"{self.API_BASE}/user/tokens/verify",
                headers={"Authorization": f"Bearer {token}"}
            )
            verify_resp.raise_for_status()
            token_id = verify_resp.json()["result"]["id"]

            # Get full token details including policies
            details_resp = client.get(
                f"{self.API_BASE}/user/tokens/{token_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            details_resp.raise_for_status()
            return details_resp.json()["result"]
        except Exception:
            return None

    def _create_token(
        self,
        client: httpx.Client,
        current_token: str,
        name: str,
        policies: list[dict]
    ) -> str:
        response = client.post(
            f"{self.API_BASE}/user/tokens",
            headers={"Authorization": f"Bearer {current_token}"},
            json={
                "name": name,
                "policies": policies
            }
        )
        response.raise_for_status()
        return response.json()["result"]["value"]

    def _delete_token(
        self, client: httpx.Client, token: str, token_id: str
    ) -> None:
        client.delete(
            f"{self.API_BASE}/user/tokens/{token_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

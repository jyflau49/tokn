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
        account_id = kwargs.get("account_id")

        if not account_id:
            return RotationResult(
                success=False,
                error="account_id is required for Cloudflare token rotation"
            )

        try:
            with httpx.Client() as client:
                # Get current token details including policies
                token_details, error_msg = self._get_token_details(
                    client, current_token, account_id
                )
                if not token_details:
                    return RotationResult(
                        success=False,
                        error=error_msg or "Could not retrieve current token details"
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
                    client, current_token, account_id, name, policies
                )

                # Delete old token only after successful creation
                self._delete_token(client, current_token, account_id, old_token_id)

                return RotationResult(success=True, new_token=new_token)

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                if "errors" in error_data and error_data["errors"]:
                    error_detail = f": {error_data['errors'][0].get('message', '')}"
            except Exception:
                pass
            return RotationResult(
                success=False,
                error=f"Cloudflare API error {e.response.status_code}{error_detail}"
            )
        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def _get_token_details(
        self, client: httpx.Client, token: str, account_id: str
    ) -> tuple[dict | None, str | None]:
        """Get current token details including policies.

        Returns:
            Tuple of (token_details, error_message)
        """
        try:
            # First verify and get token ID using Account API
            verify_resp = client.get(
                f"{self.API_BASE}/accounts/{account_id}/tokens/verify",
                headers={"Authorization": f"Bearer {token}"}
            )
            verify_resp.raise_for_status()
            verify_data = verify_resp.json()

            if not verify_data.get("success"):
                errors = verify_data.get("errors", [])
                error_msg = (
                    errors[0].get("message") if errors
                    else "Token verification failed"
                )
                return None, error_msg

            token_id = verify_data["result"]["id"]

            # Get full token details including policies
            details_resp = client.get(
                f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            details_resp.raise_for_status()
            details_data = details_resp.json()

            if not details_data.get("success"):
                errors = details_data.get("errors", [])
                error_msg = (
                    errors[0].get("message") if errors
                    else "Failed to get token details"
                )
                return None, error_msg

            return details_data["result"], None
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}"
        except KeyError as e:
            return None, f"Unexpected API response format: missing {str(e)}"
        except Exception as e:
            return None, str(e)

    def _create_token(
        self,
        client: httpx.Client,
        current_token: str,
        account_id: str,
        name: str,
        policies: list[dict]
    ) -> str:
        response = client.post(
            f"{self.API_BASE}/accounts/{account_id}/tokens",
            headers={"Authorization": f"Bearer {current_token}"},
            json={
                "name": name,
                "policies": policies
            }
        )
        response.raise_for_status()
        return response.json()["result"]["value"]

    def _delete_token(
        self, client: httpx.Client, token: str, account_id: str, token_id: str
    ) -> None:
        client.delete(
            f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

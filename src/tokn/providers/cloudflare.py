"""Cloudflare Account API Token rotation provider.

Rotates Cloudflare Account API tokens using the Roll Token endpoint:
1. Verify token to get its ID
2. Get token details (name, policies)
3. Roll token to generate new value
4. Update token expiry to 90 days from now

Requires account_id in location metadata for rotation.
"""

from datetime import UTC, datetime, timedelta

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
        account_id = kwargs.get("account_id")
        expiry_days = kwargs.get("expiry_days", 90)

        if not account_id:
            return RotationResult(
                success=False,
                error="account_id is required for Cloudflare token rotation",
            )

        try:
            with httpx.Client() as client:
                # Verify token to get its ID
                token_id, error_msg = self._get_token_id(
                    client, current_token, account_id
                )
                if not token_id:
                    return RotationResult(
                        success=False, error=error_msg or "Could not retrieve token ID"
                    )

                # Get token details for update
                token_details, error_msg = self._get_token_details(
                    client, current_token, account_id, token_id
                )
                if not token_details:
                    return RotationResult(
                        success=False,
                        error=error_msg or "Could not retrieve token details",
                    )

                # Roll token to generate new value
                new_token = self._roll_token(
                    client, current_token, account_id, token_id
                )

                # Update token expiry (use new token for auth)
                expires_at = self._update_token_expiry(
                    client, new_token, account_id, token_id, token_details, expiry_days
                )

                return RotationResult(
                    success=True, new_token=new_token, expires_at=expires_at
                )

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
                error=f"Cloudflare API error {e.response.status_code}{error_detail}",
            )
        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def _get_token_id(
        self, client: httpx.Client, token: str, account_id: str
    ) -> tuple[str | None, str | None]:
        """Get current token's ID via verify endpoint.

        Returns:
            Tuple of (token_id, error_message)
        """
        try:
            verify_url = f"{self.API_BASE}/accounts/{account_id}/tokens/verify"
            verify_resp = client.get(
                verify_url, headers={"Authorization": f"Bearer {token}"}
            )
            if verify_resp.status_code != 200:
                try:
                    err_data = verify_resp.json()
                    err_msg = err_data.get("errors", [{}])[0].get("message", "")
                    return None, f"Token verify failed: {err_msg}"
                except Exception:
                    return None, f"Token verify failed: HTTP {verify_resp.status_code}"

            verify_data = verify_resp.json()
            if not verify_data.get("success"):
                errors = verify_data.get("errors", [])
                error_msg = (
                    errors[0].get("message") if errors else "Token verification failed"
                )
                return None, error_msg

            return verify_data["result"]["id"], None
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}"
        except KeyError as e:
            return None, f"Unexpected API response format: missing {str(e)}"
        except Exception as e:
            return None, str(e)

    def _get_token_details(
        self, client: httpx.Client, token: str, account_id: str, token_id: str
    ) -> tuple[dict | None, str | None]:
        """Get token details (name, policies) for update."""
        try:
            response = client.get(
                f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code != 200:
                try:
                    err_data = response.json()
                    err_msg = err_data.get("errors", [{}])[0].get("message", "")
                    return None, f"Get token details failed: {err_msg}"
                except Exception:
                    status = response.status_code
                    return None, f"Get token details failed: HTTP {status}"

            data = response.json()
            if not data.get("success"):
                errors = data.get("errors", [])
                error_msg = (
                    errors[0].get("message")
                    if errors
                    else "Failed to get token details"
                )
                return None, error_msg

            return data["result"], None
        except Exception as e:
            return None, str(e)

    def _roll_token(
        self, client: httpx.Client, current_token: str, account_id: str, token_id: str
    ) -> str:
        """Roll token to generate new value."""
        response = client.put(
            f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}/value",
            headers={
                "Authorization": f"Bearer {current_token}",
                "Content-Type": "application/json",
            },
            json={},
        )
        response.raise_for_status()
        return response.json()["result"]

    def _update_token_expiry(
        self,
        client: httpx.Client,
        token: str,
        account_id: str,
        token_id: str,
        token_details: dict,
        expiry_days: int,
    ) -> datetime:
        """Update token expiry date and return new expiry datetime."""
        new_expiry = datetime.now(UTC) + timedelta(days=expiry_days)
        expiry_str = new_expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build update payload from existing token details
        policies = []
        for policy in token_details.get("policies", []):
            clean_policy = {
                "effect": policy.get("effect", "allow"),
                "resources": policy.get("resources", {}),
                "permission_groups": [
                    {"id": pg["id"]} for pg in policy.get("permission_groups", [])
                ],
            }
            policies.append(clean_policy)

        response = client.put(
            f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "name": token_details.get("name", "tokn-rotated"),
                "policies": policies,
                "expires_on": expiry_str,
                "status": "active",
            },
        )
        response.raise_for_status()
        return new_expiry

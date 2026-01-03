"""Cloudflare Account API Token rotation provider.

Rotates Cloudflare Account API tokens using the Roll Token endpoint:
1. Verify token to get its ID
2. Roll token to generate new value (preserves all permissions)

Requires account_id in location metadata for rotation.
"""

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

        if not account_id:
            return RotationResult(
                success=False,
                error="account_id is required for Cloudflare token rotation"
            )

        try:
            with httpx.Client() as client:
                # Verify token to get its ID
                token_id, error_msg = self._get_token_id(
                    client, current_token, account_id
                )
                if not token_id:
                    return RotationResult(
                        success=False,
                        error=error_msg or "Could not retrieve token ID"
                    )

                # Roll token to generate new value
                new_token = self._roll_token(
                    client, current_token, account_id, token_id
                )

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
                verify_url,
                headers={"Authorization": f"Bearer {token}"}
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
                    errors[0].get("message") if errors
                    else "Token verification failed"
                )
                return None, error_msg

            return verify_data["result"]["id"], None
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}"
        except KeyError as e:
            return None, f"Unexpected API response format: missing {str(e)}"
        except Exception as e:
            return None, str(e)

    def _roll_token(
        self,
        client: httpx.Client,
        current_token: str,
        account_id: str,
        token_id: str
    ) -> str:
        """Roll token to generate new value (preserves all permissions).

        Uses PUT /accounts/{account_id}/tokens/{token_id}/value endpoint.
        """
        response = client.put(
            f"{self.API_BASE}/accounts/{account_id}/tokens/{token_id}/value",
            headers={
                "Authorization": f"Bearer {current_token}",
                "Content-Type": "application/json"
            },
            json={}
        )
        response.raise_for_status()
        return response.json()["result"]

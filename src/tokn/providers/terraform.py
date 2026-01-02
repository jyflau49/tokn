"""HCP Terraform token rotation providers."""

import httpx

from tokn.providers.base import RotationResult, TokenProvider


class TerraformAccountProvider(TokenProvider):
    def __init__(self):
        super().__init__("HCP Terraform Account Token")

    @property
    def supports_auto_rotation(self) -> bool:
        return False

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        return RotationResult(
            success=False,
            error="Manual rotation required via 'terraform login'"
        )

    def get_manual_instructions(self) -> str:
        return """
Manual rotation required for HCP Terraform Account Token:

1. Run: terraform login
2. Follow OAuth flow in browser
3. Token will be saved to ~/.terraform.d/credentials.tfrc.json
4. Run: tokn sync to update metadata
"""


class TerraformOrgProvider(TokenProvider):
    API_BASE = "https://app.terraform.io/api/v2"

    def __init__(self):
        super().__init__("HCP Terraform Org Token")

    @property
    def supports_auto_rotation(self) -> bool:
        return True

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        org_name = kwargs.get("org_name")
        if not org_name:
            return RotationResult(
                success=False,
                error="org_name required for Terraform Org token rotation"
            )

        try:
            with httpx.Client() as client:
                new_token = self._create_org_token(client, current_token, org_name)

                old_token_id = self._get_current_token_id(
                    client, current_token, org_name
                )
                if old_token_id:
                    self._delete_token(client, current_token, old_token_id)

                return RotationResult(success=True, new_token=new_token)

        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def _get_current_token_id(
        self, client: httpx.Client, token: str, org_name: str
    ) -> str | None:
        try:
            response = client.get(
                f"{self.API_BASE}/organizations/{org_name}/authentication-tokens",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/vnd.api+json"
                }
            )
            response.raise_for_status()

            tokens = response.json()["data"]
            if tokens:
                return tokens[0]["id"]
            return None
        except Exception:
            return None

    def _create_org_token(
        self, client: httpx.Client, current_token: str, org_name: str
    ) -> str:
        response = client.post(
            f"{self.API_BASE}/organizations/{org_name}/authentication-tokens",
            headers={
                "Authorization": f"Bearer {current_token}",
                "Content-Type": "application/vnd.api+json"
            },
            json={
                "data": {
                    "type": "authentication-tokens"
                }
            }
        )
        response.raise_for_status()
        return response.json()["data"]["attributes"]["token"]

    def _delete_token(self, client: httpx.Client, token: str, token_id: str) -> None:
        client.delete(
            f"{self.API_BASE}/authentication-tokens/{token_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.api+json"
            }
        )

"""Linode Personal Access Token rotation provider."""

from datetime import datetime, timedelta

import httpx

from tokn.providers.base import RotationResult, TokenProvider


class LinodeProvider(TokenProvider):
    API_BASE = "https://api.linode.com/v4"

    def __init__(self, token_type: str = "CLI"):
        super().__init__(f"Linode {token_type} Token")
        self.token_type = token_type

    @property
    def supports_auto_rotation(self) -> bool:
        return True

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        date_str = datetime.now().strftime('%Y%m%d')
        default_label = f"tokn-{self.token_type.lower()}-{date_str}"
        label = kwargs.get("label", default_label)
        scopes = kwargs.get("scopes", "*")
        expiry_days = kwargs.get("expiry_days", 30)

        try:
            with httpx.Client() as client:
                new_token = self._create_token(
                    client,
                    current_token,
                    label,
                    scopes,
                    expiry_days
                )

                old_token_id = self._get_current_token_id(client, current_token)
                if old_token_id:
                    self._revoke_token(client, current_token, old_token_id)

                return RotationResult(success=True, new_token=new_token)

        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def _get_current_token_id(self, client: httpx.Client, token: str) -> int | None:
        try:
            response = client.get(
                f"{self.API_BASE}/profile/tokens",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()

            tokens = response.json()["data"]
            for t in tokens:
                if t.get("token") == token[:16]:
                    return t["id"]
            return None
        except Exception:
            return None

    def _create_token(
        self,
        client: httpx.Client,
        current_token: str,
        label: str,
        scopes: str,
        expiry_days: int
    ) -> str:
        expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat()

        response = client.post(
            f"{self.API_BASE}/profile/tokens",
            headers={"Authorization": f"Bearer {current_token}"},
            json={
                "label": label,
                "scopes": scopes,
                "expiry": expiry
            }
        )
        response.raise_for_status()
        return response.json()["token"]

    def _revoke_token(self, client: httpx.Client, token: str, token_id: int) -> None:
        client.delete(
            f"{self.API_BASE}/profile/tokens/{token_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

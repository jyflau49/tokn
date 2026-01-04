"""Akamai API Client Credentials rotation provider.

Rotates Akamai EdgeGrid credentials using the Identity Management API:
1. List credentials to find current one by clientToken
2. Update old credential expiry to +7 days (overlap period)
3. Create new credential (returns new clientSecret and clientToken)
4. Return new credentials for .edgerc update

Uses requests + edgegrid-python for EdgeGrid authentication.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from akamai.edgegrid import EdgeGridAuth, EdgeRc

from tokn.providers.base import RotationResult, TokenProvider


class AkamaiEdgeGridProvider(TokenProvider):
    """Provider for Akamai API Client Credentials rotation.

    Rotation strategy:
    - Create new credential (new clientSecret + clientToken)
    - Update old credential to expire in 7 days (safe overlap)
    - host and access_token remain unchanged (same API client)
    """

    OVERLAP_DAYS = 7
    DEFAULT_EXPIRY_DAYS = 90

    def __init__(self):
        super().__init__("Akamai EdgeGrid Credentials")

    @property
    def supports_auto_rotation(self) -> bool:
        return True

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        """Rotate Akamai API credentials.

        Args:
            current_token: Current client_secret (used for auth via .edgerc)
            **kwargs:
                edgerc_path: Path to .edgerc file (default: ~/.edgerc)
                section: Section name in .edgerc (default: default)
                expiry_days: Days until new credential expires (default: 90)

        Returns:
            RotationResult with new_token (client_secret) and metadata
        """
        edgerc_path = kwargs.get("edgerc_path", "~/.edgerc")
        section = kwargs.get("section", "default")
        expiry_days = kwargs.get("expiry_days", self.DEFAULT_EXPIRY_DAYS)

        try:
            expanded_path = str(Path(edgerc_path).expanduser())
            edgerc = EdgeRc(expanded_path)
            baseurl = f"https://{edgerc.get(section, 'host')}"

            session = requests.Session()
            session.auth = EdgeGridAuth.from_edgerc(edgerc, section)

            current_client_token = edgerc.get(section, "client_token")

            current_cred = self._find_current_credential(
                session, baseurl, current_client_token
            )
            if not current_cred:
                return RotationResult(
                    success=False,
                    error=f"Could not find credential with clientToken: "
                    f"{current_client_token}",
                )

            new_cred = self._create_credential(session, baseurl)
            if not new_cred:
                return RotationResult(
                    success=False,
                    error="Failed to create new credential",
                )

            self._update_credential_expiry(
                session, baseurl, current_cred["credentialId"], self.OVERLAP_DAYS
            )

            expires_at = datetime.now(UTC) + timedelta(days=expiry_days)

            return RotationResult(
                success=True,
                new_token=new_cred["clientSecret"],
                expires_at=expires_at,
            )

        except FileNotFoundError:
            return RotationResult(
                success=False,
                error=f".edgerc file not found: {edgerc_path}",
            )
        except Exception as e:
            return RotationResult(success=False, error=str(e))

    def get_new_client_token(self, **kwargs) -> str | None:
        """Get the new client_token after rotation.

        Must be called after a successful rotate() to retrieve the new client_token.
        This is stored temporarily during rotation.
        """
        return getattr(self, "_new_client_token", None)

    def _find_current_credential(
        self, session: requests.Session, baseurl: str, client_token: str
    ) -> dict | None:
        """Find credential by clientToken from list of credentials."""
        url = f"{baseurl}/identity-management/v3/api-clients/self/credentials"

        response = session.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()

        credentials = response.json()
        for cred in credentials:
            if cred.get("clientToken") == client_token:
                return cred

        return None

    def _create_credential(
        self, session: requests.Session, baseurl: str
    ) -> dict | None:
        """Create new credential for the API client.

        Returns dict with clientSecret, clientToken, credentialId, expiresOn.
        """
        url = f"{baseurl}/identity-management/v3/api-clients/self/credentials"

        response = session.post(url, headers={"Accept": "application/json"})
        response.raise_for_status()

        new_cred = response.json()

        self._new_client_token = new_cred.get("clientToken")

        return new_cred

    def _update_credential_expiry(
        self,
        session: requests.Session,
        baseurl: str,
        credential_id: int,
        days_from_now: int,
    ) -> None:
        """Update credential expiry to specified days from now."""
        url = (
            f"{baseurl}/identity-management/v3/"
            f"api-clients/self/credentials/{credential_id}"
        )

        new_expiry = datetime.now(UTC) + timedelta(days=days_from_now)
        expiry_str = new_expiry.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        payload = {
            "expiresOn": expiry_str,
            "status": "ACTIVE",
        }

        response = session.put(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

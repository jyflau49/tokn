"""Postman Environment location handler.

Handles reading and writing variables to Postman Environments via the Postman API.
Similar to .edgerc sections - each environment can store multiple credential variables.

Requires:
- POSTMAN_API_KEY environment variable
- Environment ID (from metadata)
- Variable key name (from path)
"""

import os

import httpx

from tokn.locations.base import LocationHandler


class PostmanEnvironmentHandler(LocationHandler):
    """Handler for Postman Environment variable locations.

    Postman environments store key-value pairs that can be used in API requests.
    This handler reads/writes specific variables within an environment.

    Metadata required:
        environment_id: The Postman environment UID

    Environment variable required:
        POSTMAN_API_KEY: Postman API key for authentication
    """

    API_BASE = "https://api.getpostman.com"

    def __init__(self):
        super().__init__("postman-env")

    def read_token(self, path: str, **kwargs) -> str | None:
        """Read a variable value from a Postman environment.

        Args:
            path: Variable key name (e.g., "AKAMAI_CLIENT_SECRET")
            **kwargs:
                environment_id: Postman environment UID

        Returns:
            The variable value or None if not found
        """
        environment_id = kwargs.get("environment_id")
        api_key = os.environ.get("POSTMAN_API_KEY")

        if not environment_id or not api_key:
            return None

        try:
            env_data = self._get_environment(api_key, environment_id)
            if not env_data:
                return None

            for var in env_data.get("environment", {}).get("values", []):
                if var.get("key") == path:
                    return var.get("value")

            return None
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        """Write a variable value to a Postman environment.

        Updates the specified variable in the environment. If the variable
        doesn't exist, it will be created.

        Args:
            path: Variable key name (e.g., "AKAMAI_CLIENT_SECRET")
            token: New value for the variable
            **kwargs:
                environment_id: Postman environment UID

        Returns:
            True if successful, False otherwise
        """
        environment_id = kwargs.get("environment_id")
        api_key = os.environ.get("POSTMAN_API_KEY")

        if not environment_id or not api_key:
            return False

        try:
            env_data = self._get_environment(api_key, environment_id)
            if not env_data:
                return False

            environment = env_data.get("environment", {})
            values = environment.get("values", [])

            variable_found = False
            for var in values:
                if var.get("key") == path:
                    var["value"] = token
                    variable_found = True
                    break

            if not variable_found:
                values.append({"key": path, "value": token, "enabled": True})

            return self._update_environment(
                api_key, environment_id, environment.get("name", ""), values
            )
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        """Return current variable value as backup."""
        return self.read_token(path, **kwargs)

    def _get_environment(self, api_key: str, environment_id: str) -> dict | None:
        """Get environment data from Postman API."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.API_BASE}/environments/{environment_id}",
                    headers={"X-API-Key": api_key},
                )
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None

    def _update_environment(
        self, api_key: str, environment_id: str, name: str, values: list[dict]
    ) -> bool:
        """Update environment variables via Postman API.

        Uses PUT to replace the environment with updated values.
        """
        try:
            with httpx.Client() as client:
                response = client.put(
                    f"{self.API_BASE}/environments/{environment_id}",
                    headers={
                        "X-API-Key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={"environment": {"name": name, "values": values}},
                )
                return response.status_code == 200
        except Exception:
            return False

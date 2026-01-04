"""Akamai .edgerc file location handler.

Handles reading and writing credentials to .edgerc INI-style configuration files.
Only modifies the specified section, preserving all other sections intact.
"""

import configparser
import os
import stat
from pathlib import Path

from tokn.locations.base import LocationHandler

SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600


class EdgercHandler(LocationHandler):
    """Handler for Akamai .edgerc credential files.

    The .edgerc file uses INI format with sections for different API clients.
    Each section contains: client_secret, host, access_token, client_token.

    During rotation, only client_secret and client_token are updated.
    host and access_token remain unchanged (same API client, new credential).
    """

    def __init__(self):
        super().__init__("edgerc")

    def read_token(self, path: str, **kwargs) -> str | None:
        """Read client_secret from specified .edgerc section.

        Args:
            path: Path to .edgerc file
            **kwargs: Must include 'section' (default: 'default')

        Returns:
            The client_secret value or None if not found
        """
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        section = kwargs.get("section", "default")

        try:
            config = self._read_edgerc(file_path)
            if section not in config:
                return None
            return config.get(section, "client_secret", fallback=None)
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        """Write new credentials to specified .edgerc section.

        Updates client_secret and optionally client_token in the section.
        Preserves all other sections and fields unchanged.

        Args:
            path: Path to .edgerc file
            token: New client_secret value
            **kwargs:
                section: Section name (default: 'default')
                client_token: New client_token value (optional)

        Returns:
            True if successful, False otherwise
        """
        file_path = Path(path).expanduser()
        section = kwargs.get("section", "default")
        client_token = kwargs.get("client_token")

        try:
            if file_path.exists():
                config = self._read_edgerc(file_path)
            else:
                config = configparser.ConfigParser()
                config.optionxform = str  # type: ignore[method-assign]

            if section not in config:
                config.add_section(section)

            config.set(section, "client_secret", token)

            if client_token:
                config.set(section, "client_token", client_token)

            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_edgerc(file_path, config)

            os.chmod(file_path, SECURE_FILE_MODE)
            return True
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        """Return current file content as backup (in-memory)."""
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        try:
            return file_path.read_text()
        except Exception:
            return None

    def rollback_token(self, path: str, backup: str, **kwargs) -> bool:
        """Restore from in-memory backup content."""
        file_path = Path(path).expanduser()
        try:
            file_path.write_text(backup)
            os.chmod(file_path, SECURE_FILE_MODE)
            return True
        except Exception:
            return False

    def _read_edgerc(self, file_path: Path) -> configparser.ConfigParser:
        """Read .edgerc file preserving comments and formatting.

        The .edgerc format allows inline comments with semicolons in section names
        like [section];comment and also standalone comment lines.
        """
        config = configparser.ConfigParser()
        config.optionxform = str  # type: ignore[method-assign]

        content = file_path.read_text()
        config.read_string(content)
        return config

    def _write_edgerc(self, file_path: Path, config: configparser.ConfigParser) -> None:
        """Write .edgerc file with proper formatting.

        Writes without extra spacing that configparser adds by default.
        """
        with open(file_path, "w") as f:
            for section in config.sections():
                f.write(f"[{section}]\n")
                for key, value in config.items(section):
                    f.write(f"{key} = {value}\n")
                f.write("\n")

    def get_section_credentials(
        self, path: str, section: str = "default"
    ) -> dict | None:
        """Get all credentials from a section for API authentication.

        Returns:
            Dict with client_secret, host, access_token, client_token or None
        """
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        try:
            config = self._read_edgerc(file_path)
            if section not in config:
                return None

            return {
                "client_secret": config.get(section, "client_secret", fallback=None),
                "host": config.get(section, "host", fallback=None),
                "access_token": config.get(section, "access_token", fallback=None),
                "client_token": config.get(section, "client_token", fallback=None),
            }
        except Exception:
            return None

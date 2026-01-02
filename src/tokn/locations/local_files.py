"""Local file location handlers for various token storage formats."""

import json
import os
import stat
from pathlib import Path

from tokn.locations.base import LocationHandler

# Secure file permissions: owner read/write only
SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600


class GitCredentialsHandler(LocationHandler):
    def __init__(self):
        super().__init__("git-credentials")

    def read_token(self, path: str, **kwargs) -> str | None:
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()
            for line in content.splitlines():
                if "github.com" in line and "@" in line:
                    parts = line.split(":")
                    if len(parts) >= 3:
                        token_part = parts[2].split("@")[0]
                        return token_part
            return None
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        file_path = Path(path).expanduser()
        username = kwargs.get("username", "git")

        try:
            new_line = f"https://{username}:{token}@github.com\n"

            if file_path.exists():
                content = file_path.read_text()
                lines = []
                for line in content.splitlines():
                    if "github.com" not in line:
                        lines.append(line)
                lines.append(new_line.strip())
                file_path.write_text("\n".join(lines) + "\n")
            else:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(new_line)

            # Ensure secure permissions
            os.chmod(file_path, SECURE_FILE_MODE)
            return True
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        """Return current file content as backup (in-memory, not written to disk)."""
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


class LinodeCLIHandler(LocationHandler):
    def __init__(self):
        super().__init__("linode-cli")

    def read_token(self, path: str, **kwargs) -> str | None:
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()
            for line in content.splitlines():
                if line.startswith("token ="):
                    return line.split("=", 1)[1].strip()
            return None
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        file_path = Path(path).expanduser()

        try:
            if file_path.exists():
                content = file_path.read_text()
                lines = []
                for line in content.splitlines():
                    if line.startswith("token ="):
                        lines.append(f"token = {token}")
                    else:
                        lines.append(line)
                file_path.write_text("\n".join(lines) + "\n")
            else:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(f"[DEFAULT]\ntoken = {token}\n")

            # Ensure secure permissions
            os.chmod(file_path, SECURE_FILE_MODE)
            return True
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        """Return current file content as backup (in-memory, not written to disk)."""
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


class TerraformCredentialsHandler(LocationHandler):
    def __init__(self):
        super().__init__("terraform-credentials")

    def read_token(self, path: str, **kwargs) -> str | None:
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text())
            hostname = kwargs.get("hostname", "app.terraform.io")
            return data.get("credentials", {}).get(hostname, {}).get("token")
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        file_path = Path(path).expanduser()
        hostname = kwargs.get("hostname", "app.terraform.io")

        try:
            if file_path.exists():
                data = json.loads(file_path.read_text())
            else:
                data = {"credentials": {}}

            if "credentials" not in data:
                data["credentials"] = {}

            data["credentials"][hostname] = {"token": token}

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(json.dumps(data, indent=2) + "\n")

            # Ensure secure permissions
            os.chmod(file_path, SECURE_FILE_MODE)
            return True
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        """Return current file content as backup (in-memory, not written to disk)."""
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

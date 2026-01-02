"""Doppler backend for metadata storage and multi-laptop sync."""

import json
import subprocess
from datetime import datetime

from tokn.core.token import TokenRegistry


class DopplerBackend:
    METADATA_SECRET = "TOKN_METADATA"

    def __init__(self, project: str = "tokn", config: str = "dev"):
        self.project = project
        self.config = config

    def _run_doppler(self, args: list[str]) -> str:
        cmd = ["doppler", "secrets"] + args + [
            "--project", self.project,
            "--config", self.config,
            "--plain"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    def load_registry(self) -> TokenRegistry:
        try:
            data = self._run_doppler(["get", self.METADATA_SECRET])
            if not data:
                return TokenRegistry()

            registry_dict = json.loads(data)
            return TokenRegistry.model_validate(registry_dict)
        except subprocess.CalledProcessError:
            return TokenRegistry()
        except json.JSONDecodeError:
            return TokenRegistry()

    def save_registry(self, registry: TokenRegistry) -> None:
        registry.last_sync = datetime.now()
        data = registry.model_dump_json(indent=2)

        self._run_doppler([
            "set",
            f"{self.METADATA_SECRET}={data}"
        ])

    def sync(self) -> TokenRegistry:
        return self.load_registry()

    def get_secret(
        self, name: str, project: str | None = None, config: str | None = None
    ) -> str:
        args = ["get", name]
        if project:
            args.extend(["--project", project])
        if config:
            args.extend(["--config", config])

        cmd = ["doppler", "secrets"] + args + ["--plain"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    def set_secret(
        self,
        name: str,
        value: str,
        project: str | None = None,
        config: str | None = None,
    ) -> None:
        args = ["set", f"{name}={value}"]
        if project:
            args.extend(["--project", project])
        if config:
            args.extend(["--config", config])

        cmd = ["doppler", "secrets"] + args
        subprocess.run(cmd, check=True, capture_output=True)

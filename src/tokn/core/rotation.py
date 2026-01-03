"""Batch rotation orchestrator with rollback support."""

import subprocess
from datetime import datetime
from typing import Any

import httpx

from tokn.core.backend import DopplerBackend
from tokn.core.token import RotationType, TokenMetadata
from tokn.locations.base import LocationHandler
from tokn.locations.doppler import DopplerLocationHandler
from tokn.locations.local_files import (
    GitCredentialsHandler,
    LinodeCLIHandler,
    TerraformCredentialsHandler,
)
from tokn.providers.base import TokenProvider
from tokn.providers.cloudflare import CloudflareProvider
from tokn.providers.github import GitHubProvider
from tokn.providers.linode import LinodeProvider
from tokn.providers.terraform import TerraformAccountProvider


class RotationOrchestrator:
    def __init__(self):
        self.backend = DopplerBackend()
        self.providers: dict[str, TokenProvider] = {
            "github": GitHubProvider(),
            "cloudflare": CloudflareProvider(),
            "linode-cli": LinodeProvider("CLI"),
            "linode-doppler": LinodeProvider("Doppler"),
            "terraform-account": TerraformAccountProvider(),
        }
        self.location_handlers: dict[str, LocationHandler] = {
            "doppler": DopplerLocationHandler(),
            "git-credentials": GitCredentialsHandler(),
            "linode-cli": LinodeCLIHandler(),
            "terraform-credentials": TerraformCredentialsHandler(),
        }

    def rotate_token(
        self,
        token_metadata: TokenMetadata,
    ) -> tuple[bool, str, list[str]]:
        provider = self.providers.get(token_metadata.service)
        if not provider:
            return False, f"Unknown provider: {token_metadata.service}", []

        if token_metadata.rotation_type == RotationType.MANUAL:
            instructions = provider.get_manual_instructions()
            return False, instructions, []

        if not provider.supports_auto_rotation:
            return False, "Provider does not support auto-rotation", []

        backups: dict[str, str] = {}
        updated_locations: list[str] = []

        try:
            current_token = self._read_current_token(token_metadata)
            if not current_token:
                return False, "Could not read current token", []

            for location in token_metadata.locations:
                backup = self._backup_location(
                    location.type, location.path, location.metadata
                )
                if backup:
                    backups[f"{location.type}:{location.path}"] = backup

            rotation_kwargs = self._get_rotation_kwargs(token_metadata)
            result = provider.rotate(current_token, **rotation_kwargs)

            if not result.success:
                return False, f"Rotation failed: {result.error}", []

            if not result.new_token:
                return False, "Rotation succeeded but no token returned", []

            for location in token_metadata.locations:
                success = self._update_location(
                    location.type, location.path, result.new_token, location.metadata
                )
                if success:
                    updated_locations.append(f"{location.type}:{location.path}")
                else:
                    self._rollback_all(backups)
                    loc_str = f"{location.type}:{location.path}"
                    return False, f"Failed to update location: {loc_str}", []

            token_metadata.last_rotated = datetime.now()
            if result.rotated_at:
                token_metadata.last_rotated = result.rotated_at

            if result.expires_at:
                token_metadata.expires_at = result.expires_at

            registry = self.backend.load_registry()
            registry.add_token(token_metadata)
            self.backend.save_registry(registry)

            return True, "Token rotated successfully", updated_locations

        except httpx.HTTPError as e:
            self._rollback_all(backups)
            return False, f"API error during rotation: {str(e)}", []
        except subprocess.CalledProcessError as e:
            self._rollback_all(backups)
            return False, f"Doppler CLI error: {e.stderr or str(e)}", []
        except FileNotFoundError as e:
            self._rollback_all(backups)
            return False, f"File not found: {str(e)}", []
        except Exception as e:
            self._rollback_all(backups)
            return False, f"Unexpected error: {str(e)}", []

    def rotate_all(self, auto_only: bool = True) -> dict[str, Any]:
        registry = self.backend.load_registry()
        results = {"success": [], "failed": [], "manual": [], "skipped": []}

        for token in registry.list_tokens():
            if auto_only and token.rotation_type == RotationType.MANUAL:
                instructions = self.providers[token.service].get_manual_instructions()
                results["manual"].append(
                    {"name": token.name, "instructions": instructions}
                )
                continue

            success, message, locations = self.rotate_token(token)

            if success:
                results["success"].append(
                    {"name": token.name, "message": message, "locations": locations}
                )
            else:
                if "does not support auto-rotation" in message:
                    results["manual"].append(
                        {"name": token.name, "instructions": message}
                    )
                else:
                    results["failed"].append({"name": token.name, "error": message})

        return results

    def _read_current_token(self, token_metadata: TokenMetadata) -> str | None:
        for location in token_metadata.locations:
            handler = self.location_handlers.get(location.type)
            if handler:
                token = handler.read_token(location.path, **location.metadata)
                if token:
                    return token
        return None

    def _backup_location(
        self, location_type: str, path: str, metadata: dict
    ) -> str | None:
        handler = self.location_handlers.get(location_type)
        if handler:
            return handler.backup_token(path, **metadata)
        return None

    def _update_location(
        self, location_type: str, path: str, token: str, metadata: dict
    ) -> bool:
        handler = self.location_handlers.get(location_type)
        if handler:
            return handler.write_token(path, token, **metadata)
        return False

    def _rollback_all(self, backups: dict[str, str]) -> None:
        for location_key, backup_content in backups.items():
            location_type, path = location_key.split(":", 1)
            handler = self.location_handlers.get(location_type)
            if handler:
                handler.rollback_token(path, backup_content)

    def _get_rotation_kwargs(self, token_metadata: TokenMetadata) -> dict[str, Any]:
        kwargs = {}

        if token_metadata.service == "github":
            kwargs["scopes"] = ["repo"]
            kwargs["note"] = f"tokn-{token_metadata.name}"
        elif token_metadata.service == "cloudflare":
            kwargs["name"] = f"tokn-{token_metadata.name}"
            for location in token_metadata.locations:
                if "account_id" in location.metadata:
                    kwargs["account_id"] = location.metadata["account_id"]
                    break
        elif token_metadata.service in ["linode-cli", "linode-doppler"]:
            kwargs["label"] = f"tokn-{token_metadata.name}"

        return kwargs

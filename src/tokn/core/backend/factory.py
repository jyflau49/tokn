"""Backend factory and configuration management."""

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w

from tokn.core.backend.base import MetadataBackend

CONFIG_DIR = Path("~/.config/tokn").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG: dict[str, Any] = {
    "backend": "local",
    "local": {
        "data_dir": "~/.config/tokn",
    },
    "doppler": {
        "project": "tokn",
        "config": "dev",
    },
}


def get_config() -> dict[str, Any]:
    """Load configuration from config file.

    Returns default config if file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "rb") as f:
            config = tomllib.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(config)
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

    os.chmod(CONFIG_FILE, 0o600)


def get_backend(backend_type: str | None = None) -> MetadataBackend:
    """Get the configured metadata backend.

    Args:
        backend_type: Override backend type. If None, uses config file.

    Returns:
        MetadataBackend instance.

    Raises:
        ValueError: If backend type is unknown.
    """
    from tokn.core.backend.doppler import DopplerBackend
    from tokn.core.backend.local import LocalBackend

    config = get_config()

    if backend_type is None:
        backend_type = config.get("backend", "local")

    if backend_type == "local":
        local_config = config.get("local", {})
        data_dir = local_config.get("data_dir", "~/.config/tokn")
        return LocalBackend(data_dir=data_dir)

    elif backend_type == "doppler":
        doppler_config = config.get("doppler", {})
        project = doppler_config.get("project", "tokn")
        doppler_env = doppler_config.get("config", "dev")
        return DopplerBackend(project=project, config=doppler_env)

    else:
        raise ValueError(
            f"Unknown backend type: {backend_type}. Supported backends: local, doppler"
        )


def migrate_backend(from_type: str, to_type: str) -> tuple[bool, str, int]:
    """Migrate metadata from one backend to another.

    Args:
        from_type: Source backend type ('local' or 'doppler').
        to_type: Destination backend type ('local' or 'doppler').

    Returns:
        Tuple of (success, message, token_count).
    """
    if from_type == to_type:
        return False, f"Source and destination are the same: {from_type}", 0

    try:
        source = get_backend(from_type)
        dest = get_backend(to_type)

        registry = source.load_registry()
        token_count = len(registry.tokens)

        if token_count == 0:
            return False, f"No tokens found in {from_type} backend", 0

        dest.save_registry(registry)

        config = get_config()
        config["backend"] = to_type
        save_config(config)

        msg = f"Migrated {token_count} token(s) from {from_type} to {to_type}"
        return True, msg, token_count

    except Exception as e:
        return False, f"Migration failed: {str(e)}", 0

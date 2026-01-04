"""Local file-based backend for metadata storage."""

import json
import os
import stat
from datetime import datetime
from pathlib import Path

from tokn.core.backend.base import MetadataBackend
from tokn.core.token import TokenRegistry

SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600


class LocalBackend(MetadataBackend):
    """Local file-based metadata storage.

    Stores token registry as JSON in ~/.config/tokn/registry.json.
    Ideal for solo developers - works offline with no external dependencies.
    """

    DEFAULT_DATA_DIR = Path("~/.config/tokn")
    REGISTRY_FILENAME = "registry.json"

    def __init__(self, data_dir: Path | str | None = None):
        if data_dir is None:
            data_dir = self.DEFAULT_DATA_DIR
        self.data_dir = Path(data_dir).expanduser()
        self.registry_file = self.data_dir / self.REGISTRY_FILENAME

    @property
    def backend_type(self) -> str:
        return "local"

    def load_registry(self) -> TokenRegistry:
        if not self.registry_file.exists():
            return TokenRegistry()

        try:
            data = json.loads(self.registry_file.read_text())
            return TokenRegistry.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return TokenRegistry()

    def save_registry(self, registry: TokenRegistry) -> None:
        registry.last_sync = datetime.now()

        self.data_dir.mkdir(parents=True, exist_ok=True)

        data = registry.model_dump_json(indent=2)
        self.registry_file.write_text(data)

        os.chmod(self.registry_file, SECURE_FILE_MODE)

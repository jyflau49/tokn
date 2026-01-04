"""Doppler secret location handler."""

from tokn.core.backend.doppler import DopplerBackend
from tokn.locations.base import LocationHandler


class DopplerLocationHandler(LocationHandler):
    """Handler for Doppler secret locations.

    Note: This always uses DopplerBackend directly (not the configured backend)
    because it's a location handler for reading/writing actual token values
    stored in Doppler secrets, not metadata storage.
    """

    def __init__(self):
        super().__init__("doppler")
        self.backend = DopplerBackend()

    def read_token(self, path: str, **kwargs) -> str | None:
        project = kwargs.get("project")
        config = kwargs.get("config")

        try:
            return self.backend.get_secret(path, project, config)
        except Exception:
            return None

    def write_token(self, path: str, token: str, **kwargs) -> bool:
        project = kwargs.get("project")
        config = kwargs.get("config")

        try:
            self.backend.set_secret(path, token, project, config)
            return True
        except Exception:
            return False

    def backup_token(self, path: str, **kwargs) -> str | None:
        return self.read_token(path, **kwargs)

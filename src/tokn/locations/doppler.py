"""Doppler secret location handler."""

from tokn.core.backend import DopplerBackend
from tokn.locations.base import LocationHandler


class DopplerLocationHandler(LocationHandler):
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

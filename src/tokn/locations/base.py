"""Abstract base class for location handlers."""

from abc import ABC, abstractmethod


class LocationHandler(ABC):
    def __init__(self, location_type: str):
        self.location_type = location_type

    @abstractmethod
    def read_token(self, path: str, **kwargs) -> str | None:
        pass

    @abstractmethod
    def write_token(self, path: str, token: str, **kwargs) -> bool:
        pass

    @abstractmethod
    def backup_token(self, path: str, **kwargs) -> str | None:
        pass

    def rollback_token(self, path: str, backup: str, **kwargs) -> bool:
        return self.write_token(path, backup, **kwargs)

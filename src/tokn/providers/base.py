"""Abstract base class for token rotation providers."""

from abc import ABC, abstractmethod
from datetime import datetime


class RotationResult:
    def __init__(
        self,
        success: bool,
        new_token: str | None = None,
        error: str | None = None,
        expires_at: datetime | None = None,
    ):
        self.success = success
        self.new_token = new_token
        self.error = error
        self.rotated_at = datetime.now()
        self.expires_at = expires_at


class TokenProvider(ABC):
    def __init__(self, name: str):
        self.name = name

    @property
    @abstractmethod
    def supports_auto_rotation(self) -> bool:
        pass

    @abstractmethod
    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        pass

    def get_manual_instructions(self) -> str:
        return f"Manual rotation required for {self.name}. Please rotate via web UI."

    def validate_token(self, token: str) -> bool:
        return bool(token and len(token) > 0)

    def get_new_client_token(self, **kwargs) -> str | None:
        """Get new client token after rotation (Akamai-specific)."""
        return None

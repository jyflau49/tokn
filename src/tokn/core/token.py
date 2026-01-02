"""Token metadata models and data structures."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RotationType(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class TokenStatus(str, Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


class TokenLocation(BaseModel):
    type: str
    path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenMetadata(BaseModel):
    name: str
    service: str
    rotation_type: RotationType
    locations: list[TokenLocation]
    expires_at: datetime | None = None
    last_rotated: datetime | None = None
    rotation_day: int = 1
    notes: str = ""

    @property
    def status(self) -> TokenStatus:
        if not self.expires_at:
            return TokenStatus.ACTIVE

        days_until_expiry = (self.expires_at - datetime.now()).days

        if days_until_expiry < 0:
            return TokenStatus.EXPIRED
        elif days_until_expiry <= 7:
            return TokenStatus.EXPIRING_SOON
        return TokenStatus.ACTIVE

    @property
    def days_until_expiry(self) -> int | None:
        if not self.expires_at:
            return None
        return (self.expires_at - datetime.now()).days


class TokenRegistry(BaseModel):
    tokens: dict[str, TokenMetadata] = Field(default_factory=dict)
    last_sync: datetime | None = None

    def add_token(self, token: TokenMetadata) -> None:
        self.tokens[token.name] = token

    def get_token(self, name: str) -> TokenMetadata | None:
        return self.tokens.get(name)

    def list_tokens(self) -> list[TokenMetadata]:
        return list(self.tokens.values())

    def remove_token(self, name: str) -> bool:
        if name in self.tokens:
            del self.tokens[name]
            return True
        return False

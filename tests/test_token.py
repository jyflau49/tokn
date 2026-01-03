"""Tests for token metadata models."""

from datetime import datetime, timedelta

from tokn.core.token import (
    RotationType,
    TokenMetadata,
    TokenRegistry,
    TokenStatus,
)


def test_token_status_active():
    token = TokenMetadata(
        name="test",
        service="github",
        rotation_type=RotationType.AUTO,
        locations=[],
        expires_at=datetime.now() + timedelta(days=30)
    )
    assert token.status == TokenStatus.ACTIVE


def test_token_status_expiring_soon():
    token = TokenMetadata(
        name="test",
        service="github",
        rotation_type=RotationType.AUTO,
        locations=[],
        expires_at=datetime.now() + timedelta(days=5)
    )
    assert token.status == TokenStatus.EXPIRING_SOON


def test_token_status_expired():
    token = TokenMetadata(
        name="test",
        service="github",
        rotation_type=RotationType.AUTO,
        locations=[],
        expires_at=datetime.now() - timedelta(days=1)
    )
    assert token.status == TokenStatus.EXPIRED


def test_token_registry_operations():
    registry = TokenRegistry()

    token = TokenMetadata(
        name="test",
        service="github",
        rotation_type=RotationType.AUTO,
        locations=[]
    )

    registry.add_token(token)
    assert registry.get_token("test") == token
    assert len(registry.list_tokens()) == 1

    assert registry.remove_token("test") is True
    assert registry.get_token("test") is None
    assert len(registry.list_tokens()) == 0

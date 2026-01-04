"""Abstract base class for metadata backends."""

from abc import ABC, abstractmethod

from tokn.core.token import TokenRegistry


class MetadataBackend(ABC):
    """Abstract interface for token metadata storage backends.

    Backends store TokenRegistry metadata only - never actual token values.
    Token values are stored in locations (Doppler secrets, local files, etc.).

    Use cases:
    - LocalBackend: Solo developer, offline-capable, no external dependencies
    - DopplerBackend: Multi-device sync, team collaboration via cloud
    """

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return the backend type identifier (e.g., 'local', 'doppler')."""
        ...

    @abstractmethod
    def load_registry(self) -> TokenRegistry:
        """Load the token registry from storage.

        Returns:
            TokenRegistry: The loaded registry, or empty registry if not found.
        """
        ...

    @abstractmethod
    def save_registry(self, registry: TokenRegistry) -> None:
        """Save the token registry to storage.

        Args:
            registry: The registry to save.
        """
        ...

    def sync(self) -> TokenRegistry:
        """Sync and return the latest registry.

        Default implementation just loads. Remote backends may fetch from cloud.
        """
        return self.load_registry()

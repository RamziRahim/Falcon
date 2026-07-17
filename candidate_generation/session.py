"""
Falcon - Candidate Generation
Module: session.py
Version: 1.1.0

Defines a provider-agnostic session object used by all
candidate sources (Screener, CSV, NSE, AI, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from config import FALCON_VERSION


@dataclass
class SourceSession:
    """
    Generic session shared across Falcon.

    The engine should depend on this object instead of
    directly depending on Playwright.
    """

    provider: str
    browser: Optional[Any] = None
    page: Optional[Any] = None
    client: Optional[Any] = None
    username: Optional[str] = None
    cookies: Optional[Any] = None

    authenticated: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_authenticated(self) -> bool:
        """Return current authentication status."""
        return self.authenticated

    def set_authenticated(self, value: bool = True) -> None:
        """Update authentication status."""
        self.authenticated = value

    def add_metadata(self, key: str, value: Any) -> None:
        """Attach provider-specific metadata."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Read provider-specific metadata."""
        return self.metadata.get(key, default)

    def clear(self) -> None:
        """
        Reset transient state.

        The provider may reuse the same SourceSession
        object across multiple candidate generations.
        """
        self.page = None
        self.browser = None
        self.client = None
        self.cookies = None
        self.authenticated = False
        self.metadata.clear()


def create_session(provider: str, **kwargs) -> SourceSession:
    """
    Factory function used by authentication modules.
    """
    return SourceSession(provider=provider, **kwargs)

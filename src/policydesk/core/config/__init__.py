"""Config package: the cached ``get_settings()`` entry point."""

from functools import lru_cache

from policydesk.core.config.base import Settings

__all__ = ["Settings", "get_settings"]


@lru_cache
def get_settings() -> Settings:
    """Build ``Settings`` once, then return the same object every call.

    This is our Singleton. ``lru_cache`` remembers the result of the
    first call (no arguments -> nothing to hash -> safe) and reuses it, so the
    ``.env`` file is read only once per process. Tests can reset it with
    ``get_settings.cache_clear()``.
    """
    return Settings()

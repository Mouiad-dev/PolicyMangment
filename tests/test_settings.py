import pytest
from pydantic import ValidationError

from policydesk.core.config import Settings, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no env set, safe defaults load."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DB__POOL__SIZE", raising=False)
    s = Settings()
    assert s.environment == "local"
    assert s.db.pool.size == 3


def test_env_var_overrides_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nested env var (DB__POOL__SIZE) reaches settings.db.pool.size."""
    monkeypatch.setenv("DB__POOL__SIZE", "9")
    s = Settings()
    assert s.db.pool.size == 9


def test_password_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secrets never print, but can still be read on purpose."""
    monkeypatch.setenv("DB__PASSWORD", "super-secret")
    s = Settings()
    assert "super-secret" not in repr(s.db.password)
    assert s.db.password.get_secret_value() == "super-secret"


def test_live_stripe_refused_outside_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """sk_live_ is refused when ENVIRONMENT is not prod."""
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("STRIPE__SECRET_KEY", "sk_live_abc")
    with pytest.raises(ValidationError):
        Settings()


def test_live_stripe_allowed_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same live key is allowed when ENVIRONMENT is prod."""
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("STRIPE__SECRET_KEY", "sk_live_abc")
    s = Settings()
    assert s.stripe.secret_key.get_secret_value() == "sk_live_abc"


def test_cors_origins_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """A comma string becomes a clean list."""
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    s = Settings()
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]


def test_get_settings_is_cached() -> None:
    """get_settings() returns the very same object every call (Singleton)."""
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()

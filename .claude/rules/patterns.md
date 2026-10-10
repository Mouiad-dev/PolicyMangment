---
paths:
  - "src/**/*.py"
---

# Design patterns (SRS section 22) — only when they add clarity

- **Repository** — one per aggregate, on a small `BaseRepository[ModelT]`. The only code that builds SQL
  for that aggregate. Money tables have no `delete`.
- **Strategy** — raters (`CarRater`, `HomeRater`), refund rules, referral rules, PDF renderers, payment
  gateways. Each family has a `Protocol` and shared tests.
- **Factory** — `create_app()`, `RaterFactory`, `PaymentGatewayFactory`, `EmailSenderFactory`, test data
  factories. An unknown key raises a clear error, never returns `None`.
- **Singleton only when needed** — `get_settings()` (lru_cache), the engine in lifespan state, the Stripe
  client. Never for `AsyncSession`, Unit of Work or repositories. No `__new__` tricks; tests must be able
  to override it (dependency_overrides or an argument).
- **Mixins always** for shared columns and helpers: `TableNameMixin`, `IntIdMixin`, `UuidIdMixin`,
  `TimestampMixin`, `ActivatorMixin`, `VersionMixin`, `AuditMixin` (+ repository, DTO and test mixins).
  One job per mixin, no `__init__`, `declared_attr` for FK columns, mixins before `Base`.
- No god objects, no pattern for its own sake. If a pattern does not remove an if/else chain, a copy, or a
  hard link to the outside world, do not use it — and tell Mouiad why.

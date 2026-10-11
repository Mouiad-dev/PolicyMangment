import json
from datetime import UTC, date, datetime
from decimal import Decimal

from policydesk.core.db.snapshot import to_snapshot
from policydesk.modules.quotes.models import Quote, QuoteStatus


def test_snapshot_is_json_safe_and_exact() -> None:
    quote = Quote(
        id=10,
        number="QTE-2026-000001",
        plan_id=1,
        status=QuoteStatus.PRICED,
        start_date=date(2026, 11, 1),
        net_premium=Decimal("1234.50"),
        risk_details={"car_value": Decimal("85000.00"), "made": date(2020, 1, 1)},
        expires_at=datetime(2026, 11, 10, 8, 0, tzinfo=UTC),
    )

    snapshot = to_snapshot(quote)

    json.dumps(snapshot)  # raises if any value is not JSON-safe
    assert snapshot["net_premium"] == "1234.50"
    assert snapshot["start_date"] == "2026-11-01"
    assert snapshot["expires_at"] == "2026-11-10T08:00:00+00:00"
    assert snapshot["status"] == "PRICED"
    assert snapshot["risk_details"] == {"car_value": "85000.00", "made": "2020-01-01"}

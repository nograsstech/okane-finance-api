import pytest
from pydantic import ValidationError

from app.signals.dto import Signal


def test_signal_market_fields_are_required():
    required_fields = {name for name, field in Signal.model_fields.items() if field.is_required()}

    assert required_fields == {
        "gmtTime",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "TotalSignal",
    }

    with pytest.raises(ValidationError):
        Signal.model_validate({"gmtTime": "2024-01-01T00:00:00Z"})

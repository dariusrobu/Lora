from datetime import datetime, date, time
import decimal
from typing import Any


def serialize(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    return obj


def clean_dict(d: dict) -> dict:
    return {k: serialize(v) for k, v in d.items()}

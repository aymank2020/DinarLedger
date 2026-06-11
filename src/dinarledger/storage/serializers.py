"""
dinarledger.storage.serializers — JSON serialization adapters for domain types.

Provides individual adapters for Money, Decimal, date, and Enum values, plus
an :class:`EntitySerializer` that composes them to handle full domain entities.
All adapters preserve Decimal precision by serialising to string.
"""

from __future__ import annotations

import enum
import json
from datetime import date
from decimal import Decimal
from typing import Any, Type

from dinarledger.core.enums import BillingCycle, InvoiceStatus, LineItemType, SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    TaxRate,
)
from dinarledger.fx.rates import FXRate


# ---------------------------------------------------------------------------
# Individual adapters
# ---------------------------------------------------------------------------

class MoneyAdapter:
    """Serialize / deserialize :class:`Money` objects."""

    @staticmethod
    def serialize(obj: Money) -> dict[str, str]:
        return {"_type": "Money", "amount": str(obj.amount), "currency": obj.currency}

    @staticmethod
    def deserialize(data: dict[str, str]) -> Money:
        return Money(amount=Decimal(data["amount"]), currency=data["currency"])


class DecimalAdapter:
    """Serialize / deserialize :class:`Decimal` values.

    Serialized as a plain string to preserve full precision.
    """

    @staticmethod
    def serialize(obj: Decimal) -> dict[str, str]:
        return {"_type": "Decimal", "value": str(obj)}

    @staticmethod
    def deserialize(data: dict[str, str]) -> Decimal:
        return Decimal(data["value"])


class DateAdapter:
    """Serialize / deserialize :class:`datetime.date` objects."""

    @staticmethod
    def serialize(obj: date) -> dict[str, str]:
        return {"_type": "Date", "value": obj.isoformat()}

    @staticmethod
    def deserialize(data: dict[str, str]) -> date:
        return date.fromisoformat(data["value"])


class EnumAdapter:
    """Serialize / deserialize enum values."""

    @staticmethod
    def serialize(obj: enum.Enum) -> dict[str, str]:
        return {
            "_type": "Enum",
            "enum_class": type(obj).__qualname__,
            "value": obj.value,
        }

    @staticmethod
    def deserialize(data: dict[str, str]) -> enum.Enum:
        cls = _ENUM_MAP.get(data["enum_class"])
        if cls is None:
            raise ValueError(f"Unknown enum class: {data['enum_class']}")
        return cls(data["value"])


# ---------------------------------------------------------------------------
# Enum lookup map
# ---------------------------------------------------------------------------

_ENUM_MAP: dict[str, Type[enum.Enum]] = {
    "InvoiceStatus": InvoiceStatus,
    "SubscriptionStatus": SubscriptionStatus,
    "LineItemType": LineItemType,
    "BillingCycle": BillingCycle,
    "PaymentStatus": PaymentStatus,
}


# ---------------------------------------------------------------------------
# Entity type map (qualified name -> class) — extensible at runtime
# ---------------------------------------------------------------------------

_ENTITY_MAP: dict[str, Type] = {
    "BillingPeriod": BillingPeriod,
    "Plan": Plan,
    "Subscription": Subscription,
    "LineItem": LineItem,
    "Invoice": Invoice,
    "Payment": Payment,
    "Customer": Customer,
    "TaxRate": TaxRate,
    "FXRate": FXRate,
}


def register_entity(entity_type: Type) -> None:
    """Register a dataclass type so the serializer can deserialize it by name.

    This is needed for custom entity types that aren't part of the core
    domain (e.g. test fixtures or extension types).
    """
    name = entity_type.__qualname__
    _ENTITY_MAP[name] = entity_type


# ---------------------------------------------------------------------------
# EntitySerializer
# ---------------------------------------------------------------------------

class EntitySerializer:
    """Round-trip serializer for DinarLedger domain entities.

    Handles nested structures (e.g. ``Plan.base_price: Money``,
    ``Invoice.line_items: list[LineItem]``) by dispatching to the
    appropriate adapter based on type.
    """

    _ADAPTERS = {
        Money: MoneyAdapter,
        Decimal: DecimalAdapter,
        date: DateAdapter,
    }

    @classmethod
    def serialize(cls, obj: Any) -> Any:
        """Recursively serialize *obj* to a JSON-compatible structure."""
        if obj is None:
            return None

        # Primitive types pass through
        if isinstance(obj, (str, int, float, bool)):
            return obj

        # Enum
        if isinstance(obj, enum.Enum):
            return EnumAdapter.serialize(obj)

        # Check registered adapters — order matters (Money before Decimal because
        # Money attributes are also objects we may encounter at the top level)
        for typ, adapter in cls._ADAPTERS.items():
            if isinstance(obj, typ):
                return adapter.serialize(obj)

        # List / tuple
        if isinstance(obj, (list, tuple)):
            return [cls.serialize(item) for item in obj]

        # Dict
        if isinstance(obj, dict):
            return {k: cls.serialize(v) for k, v in obj.items()}

        # dataclass-like entity
        if hasattr(obj, "__dataclass_fields__"):
            result: dict[str, Any] = {"_type": type(obj).__qualname__}
            for field_name in obj.__dataclass_fields__:
                result[field_name] = cls.serialize(getattr(obj, field_name))
            return result

        # Fallback — use repr
        return repr(obj)

    @classmethod
    def deserialize(cls, data: Any) -> Any:
        """Recursively deserialize *data* back into domain objects."""
        if data is None:
            return None

        if isinstance(data, (str, int, float, bool)):
            return data

        if isinstance(data, list):
            return [cls.deserialize(item) for item in data]

        if isinstance(data, dict):
            type_tag = data.get("_type")

            # Primitive adapters
            if type_tag == "Money":
                return MoneyAdapter.deserialize(data)
            if type_tag == "Decimal":
                return DecimalAdapter.deserialize(data)
            if type_tag == "Date":
                return DateAdapter.deserialize(data)
            if type_tag == "Enum":
                return EnumAdapter.deserialize(data)

            # Entity types
            entity_cls = _ENTITY_MAP.get(type_tag)
            if entity_cls is not None:
                kwargs = {
                    k: cls.deserialize(v)
                    for k, v in data.items()
                    if k != "_type"
                }
                return entity_cls(**kwargs)

            # Generic dict
            return {k: cls.deserialize(v) for k, v in data.items()}

        return data


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def to_json(obj: Any, **kwargs: Any) -> str:
    """Serialize *obj* to a JSON string."""
    return json.dumps(EntitySerializer.serialize(obj), **kwargs)


def from_json(text: str) -> Any:
    """Deserialize a JSON string back into domain objects."""
    return EntitySerializer.deserialize(json.loads(text))

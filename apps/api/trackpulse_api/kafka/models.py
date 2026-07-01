from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .topics import RAW_OPENF1_TOPICS


class InvalidRawOpenF1EventError(ValueError):
    """Raised when a Kafka payload cannot be parsed as RawOpenF1Event."""


class RawOpenF1Event(BaseModel):
    """Canonical raw OpenF1 event envelope used on Kafka topics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    fixture_id: str
    source: str
    topic: str
    event_type: str
    payload: dict[str, Any]
    schema_version: int = 1
    session_key: int | None = None
    meeting_key: int | None = None
    driver_number: int | None = None
    occurred_at: str | None = None
    ingested_at: str | None = None

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        if value not in RAW_OPENF1_TOPICS:
            supported = ", ".join(sorted(RAW_OPENF1_TOPICS))
            raise ValueError(f"Unsupported raw topic: {value}. Supported topics: {supported}")
        return value

    def to_message_bytes(self) -> bytes:
        return self.model_dump_json(exclude_none=True).encode("utf-8")

    @classmethod
    def from_message_bytes(cls, value: bytes) -> "RawOpenF1Event":
        try:
            payload = json.loads(value.decode("utf-8"))
            return cls.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise InvalidRawOpenF1EventError("Invalid raw OpenF1 event payload") from exc

"""Kafka/Redpanda ingestion primitives for raw OpenF1 events."""

from .consumer import KafkaRawEventConsumer
from .models import InvalidRawOpenF1EventError, RawOpenF1Event
from .producer import InMemoryRawEventProducer, KafkaRawEventProducer, RawEventProducer
from .topics import (
    RAW_OPENF1_CAR_DATA_TOPIC,
    RAW_OPENF1_LAPS_TOPIC,
    RAW_OPENF1_LOCATION_TOPIC,
    RAW_OPENF1_RACE_CONTROL_TOPIC,
    RAW_OPENF1_TOPICS,
    RAW_OPENF1_WEATHER_TOPIC,
)

__all__ = [
    "InvalidRawOpenF1EventError",
    "InMemoryRawEventProducer",
    "KafkaRawEventConsumer",
    "KafkaRawEventProducer",
    "RawEventProducer",
    "RawOpenF1Event",
    "RAW_OPENF1_CAR_DATA_TOPIC",
    "RAW_OPENF1_LAPS_TOPIC",
    "RAW_OPENF1_LOCATION_TOPIC",
    "RAW_OPENF1_RACE_CONTROL_TOPIC",
    "RAW_OPENF1_TOPICS",
    "RAW_OPENF1_WEATHER_TOPIC",
]

"""Raw OpenF1 Kafka topic names for ingestion."""

RAW_OPENF1_WEATHER_TOPIC = "raw.openf1.weather.v1"
RAW_OPENF1_LOCATION_TOPIC = "raw.openf1.location.v1"
RAW_OPENF1_CAR_DATA_TOPIC = "raw.openf1.car_data.v1"
RAW_OPENF1_LAPS_TOPIC = "raw.openf1.laps.v1"
RAW_OPENF1_RACE_CONTROL_TOPIC = "raw.openf1.race_control.v1"

RAW_OPENF1_TOPICS: frozenset[str] = frozenset(
    {
        RAW_OPENF1_WEATHER_TOPIC,
        RAW_OPENF1_LOCATION_TOPIC,
        RAW_OPENF1_CAR_DATA_TOPIC,
        RAW_OPENF1_LAPS_TOPIC,
        RAW_OPENF1_RACE_CONTROL_TOPIC,
    }
)

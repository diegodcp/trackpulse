import enum


class SessionType(str, enum.Enum):
    PRACTICE = "Practice"
    QUALIFYING = "Qualifying"
    SPRINT = "Sprint"
    RACE = "Race"


class TyreCompound(str, enum.Enum):
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"


class FlagType(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    RED = "RED"
    CHEQUERED = "CHEQUERED"
    BLACK_AND_WHITE = "BLACK_AND_WHITE"
    BLUE = "BLUE"
    VSC = "VSC"


class RaceControlCategory(str, enum.Enum):
    FLAG = "Flag"
    SAFETY_CAR = "SafetyCar"
    DRS = "Drs"
    CAR_EVENT = "CarEvent"
    SESSION_STATUS = "SessionStatus"
    OTHER = "Other"


class ConditionLevel(str, enum.Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EvolutionTrend(str, enum.Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
    INSUFFICIENT_DATA = "insufficient_data"


class InsightSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DataLabel(str, enum.Enum):
    MEASURED = "measured"
    DERIVED = "derived"
    INFERRED = "inferred"

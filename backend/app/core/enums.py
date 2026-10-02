import enum


class PreferenceType(str, enum.Enum):
    DEAL_BREAKER = "DEAL_BREAKER"
    HARD = "HARD"
    SOFT = "SOFT"


class Decision(str, enum.Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class ConflictKind(str, enum.Enum):
    VIOLATION = "VIOLATION"
    MISSING_DATA = "MISSING_DATA"
    INVALID_PREFERENCE = "INVALID_PREFERENCE"
    UNSUPPORTED_ATTRIBUTE = "UNSUPPORTED_ATTRIBUTE"

class SessionNotFoundError(Exception):
    """OpenF1 returned empty result for session_key."""


class InsufficientDataError(Exception):
    """Not enough location data to extract a circuit."""

"""State machine states for calls."""

from enum import Enum


class CallState(str, Enum):
    IDLE = "IDLE"
    CALLING = "CALLING"
    RINGING = "RINGING"
    IN_CALL = "IN_CALL"
    ENDED = "ENDED"
    ERROR = "ERROR"

from __future__ import annotations

import time
from dataclasses import dataclass


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None
    half_open: bool = False


class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_seconds: float) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._state = CircuitState()

    def allow(self) -> None:
        state = self._state
        if state.opened_at is None:
            return
        elapsed = time.monotonic() - state.opened_at
        if elapsed < self.recovery_seconds:
            raise CircuitOpenError("backend circuit is open")
        if not state.half_open:
            state.half_open = True

    def success(self) -> None:
        self._state = CircuitState()

    def failure(self) -> None:
        state = self._state
        if state.half_open:
            state.opened_at = time.monotonic()
            state.half_open = False
            return
        state.failures += 1
        if state.failures >= self.failure_threshold:
            state.opened_at = time.monotonic()

    def status(self) -> dict[str, object]:
        state = self._state
        return {
            "state": "open" if state.opened_at is not None else "closed",
            "failures": state.failures,
            "half_open": state.half_open,
            "opened_at": state.opened_at,
        }

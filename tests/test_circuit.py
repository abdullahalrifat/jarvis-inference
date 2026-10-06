import time

import pytest

from inference.circuit import CircuitBreaker, CircuitOpenError


def test_circuit_opens_and_recovers(monkeypatch) -> None:
    now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    circuit = CircuitBreaker(2, 10)

    circuit.allow()
    circuit.failure()
    circuit.allow()
    circuit.failure()

    with pytest.raises(CircuitOpenError):
        circuit.allow()

    now[0] += 11
    circuit.allow()
    assert circuit.status()["half_open"] is True
    circuit.success()
    assert circuit.status()["state"] == "closed"

from __future__ import annotations

from pathlib import Path

import psutil

from .config import settings
from .errors import InferenceError


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _cgroup_stats() -> tuple[int | None, int | None]:
    """Return the active cgroup memory limit and current usage."""
    for limit_path, current_path in (
        (Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory.current")),
        (
            Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
            Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
        ),
    ):
        limit = _read_int(limit_path)
        if limit is not None and limit < 1 << 60:
            return limit, _read_int(current_path)
    return None, None


def memory_limit_bytes() -> int | None:
    return _cgroup_stats()[0]


def memory_current_bytes() -> int | None:
    return _cgroup_stats()[1]


def container_memory_available_gb() -> float:
    """Return memory left inside this API container, for diagnostics only."""
    limit, current = _cgroup_stats()
    if limit is None:
        return psutil.virtual_memory().available / 1024**3
    if current is None:
        return 0.0
    return max(0.0, (limit - current) / 1024**3)


def memory_available_gb() -> float:
    """Return memory available to the model runtime admission policy.

    Model execution happens in the sibling Ollama container, so the gateway
    cgroup is not the model's capacity. Use host availability bounded by the
    explicitly configured gateway admission budget instead.
    """
    host_available = psutil.virtual_memory().available / 1024**3
    return max(0.0, min(host_available, settings.memory_budget_gb))


def admit_request() -> None:
    available = memory_available_gb()
    if available < settings.memory_headroom_gb:
        raise InferenceError(
            "RESOURCE_PRESSURE",
            f"Insufficient memory headroom: {available:.2f} GiB available",
            True,
            503,
        )


def status() -> dict[str, float | int | None]:
    vm = psutil.virtual_memory()
    limit, current = _cgroup_stats()
    return {
        "host_memory_total_gb": round(vm.total / 1024**3, 2),
        "host_memory_available_gb": round(vm.available / 1024**3, 2),
        "memory_budget_gb": round(settings.memory_budget_gb, 2),
        "memory_headroom_gb": round(settings.memory_headroom_gb, 2),
        "admission_memory_available_gb": round(memory_available_gb(), 2),
        "container_memory_limit_gb": round(limit / 1024**3, 2) if limit else None,
        "container_memory_current_gb": (
            round(current / 1024**3, 2) if current is not None else None
        ),
        "container_memory_available_gb": round(container_memory_available_gb(), 2),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(logical=True) or 1,
    }

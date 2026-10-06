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


def memory_limit_bytes() -> int | None:
    for path in (Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")):
        value = _read_int(path)
        if value is not None and value < 1 << 60:
            return value
    return None


def memory_available_gb() -> float:
    limit = memory_limit_bytes()
    if limit is None:
        return psutil.virtual_memory().available / 1024**3
    current = _read_int(Path("/sys/fs/cgroup/memory.current"))
    if current is None:
        return limit / 1024**3
    return max(0.0, (limit - current) / 1024**3)


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
    limit = memory_limit_bytes()
    return {
        "host_memory_total_gb": round(vm.total / 1024**3, 2),
        "host_memory_available_gb": round(vm.available / 1024**3, 2),
        "container_memory_limit_gb": round(limit / 1024**3, 2) if limit else None,
        "container_memory_available_gb": round(memory_available_gb(), 2),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(logical=True) or 1,
    }

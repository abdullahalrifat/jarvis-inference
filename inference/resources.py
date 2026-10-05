import psutil
from .config import settings
from .errors import InferenceError

def memory_available_gb() -> float:
    return psutil.virtual_memory().available / (1024**3)

def admit_request() -> None:
    available = memory_available_gb()
    if available < settings.memory_headroom_gb:
        raise InferenceError(
            "RESOURCE_PRESSURE",
            f"Insufficient memory headroom: {available:.2f} GiB available",
            True,
            503,
        )

def status() -> dict:
    vm = psutil.virtual_memory()
    return {
        "memory_total_gb": round(vm.total / 1024**3, 2),
        "memory_available_gb": round(vm.available / 1024**3, 2),
        "memory_used_percent": vm.percent,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(logical=True),
    }

from collections import Counter
from threading import Lock

class Metrics:
    def __init__(self):
        self._lock = Lock()
        self.requests = Counter()
        self.model_switches = 0

    def request(self, model: str, ok: bool) -> None:
        with self._lock:
            self.requests[(model, "success" if ok else "error")] += 1

    def render(self) -> str:
        lines = [
            "# HELP inference_requests_total Total inference requests.",
            "# TYPE inference_requests_total counter",
        ]
        with self._lock:
            for (model, status), value in self.requests.items():
                lines.append(
                    f'inference_requests_total{{model="{model}",status="{status}"}} {value}'
                )
            lines += [
                "# HELP inference_model_switches_total Model switches.",
                "# TYPE inference_model_switches_total counter",
                f"inference_model_switches_total {self.model_switches}",
            ]
        return "\n".join(lines) + "\n"

metrics = Metrics()

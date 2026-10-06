from inference.metrics import render


def test_metrics_render_contains_runtime_metrics() -> None:
    output = render().decode()
    assert "inference_requests_total" in output
    assert "inference_host_cpu_percent" in output
    assert "inference_model_warm" in output

from inference.resources import memory_available_gb, status


def test_resource_status_has_expected_fields() -> None:
    result = status()
    assert "container_memory_available_gb" in result
    assert result["cpu_count"]


def test_memory_is_non_negative() -> None:
    assert memory_available_gb() >= 0

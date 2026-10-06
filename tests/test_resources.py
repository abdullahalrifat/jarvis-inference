from inference.resources import status


def test_resource_status_has_expected_fields():
    result = status()
    assert "memory_available_gb" in result
    assert "cpu_count" in result

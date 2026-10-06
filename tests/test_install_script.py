from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.sh"

def test_install_script_removes_only_stale_application_containers() -> None:
    content = INSTALL.read_text(encoding="utf-8")
    assert "for container in jarvis-inference jarvis-ollama; do" in content
    assert 'docker container inspect "$container"' in content
    assert 'docker rm -f "$container"' in content
    assert "docker compose down -v" not in content

def test_install_script_pulls_all_configured_models() -> None:
    content = INSTALL.read_text(encoding="utf-8")
    assert "ollama pull \"$model\"" in content
    assert "ollama show \"$model\"" in content
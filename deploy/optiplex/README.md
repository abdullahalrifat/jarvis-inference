# OptiPlex deployment

Targets the Dell OptiPlex 7040 SFF class machine with Intel i5 CPU, 16 GB RAM and no GPU.

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
./scripts/install-optiplex.sh
```

Recommended model policy:

- `qwen3:1.7b` — default.
- `qwen3:4b` — heavier reasoning.
- Keep one model loaded at a time.

Ollama model files persist in the Docker volume; the gateway is stateless.

If AI Stack runs in another Compose project, create a shared network and attach both projects. Use `http://jarvis-inference:8080/v1` from AI Stack. Never publish port 11434.

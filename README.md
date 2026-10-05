# Jarvis Inference

Dedicated local inference gateway for Jarvis.

## Architecture

Jarvis -> AI Stack -> jarvis-inference -> llama.cpp or Ollama

The service owns model execution, scheduling, model admission, resource
guardrails, and inference metrics. AI Stack owns orchestration and agent
policy.

## Current MVP

- OpenAI-compatible /v1/chat/completions
- concrete /v1/models
- health and runtime status
- bounded concurrent inference
- one active model policy
- Ollama backend
- llama.cpp HTTP backend
- memory-aware admission
- Prometheus-compatible metrics
- structured errors rather than partial fallback text

The runtime intentionally contains no agent, Git, filesystem, search, or
business logic.

## Local setup

pip install -e '.[dev]'
uvicorn inference.main:app --host 0.0.0.0 --port 8080

Copy .env.example to .env before running.

## Integration contract

AI Stack will use:

http://jarvis-inference:8080/v1

Jarvis continues to use AI Stack as its public endpoint. Model IDs remain
concrete: qwen3-1.7b, qwen3-4b, qwen3-7b.

## Resource policy

The runtime is designed for CPU-only machines. It serializes generation by
default and applies memory admission before starting inference. Resource
limits are safety boundaries; they are not a reason to intentionally produce
low-quality or truncated answers.

4B and 7B suitability must be established by benchmark results on the target
CPU and RAM configuration.

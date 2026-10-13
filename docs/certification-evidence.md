# Inference gateway certification evidence

Tie every certification artifact to the gateway Git SHA, image digest, model manifest digest and target hardware profile.

Record:

- unit/integration/security CI workflow URLs and outcomes;
- API authentication checks, including startup failure with no key and the explicit development-only override;
- health/readiness results after clean start and VM reboot;
- model catalog, capabilities, embeddings, non-streaming chat and SSE conformance;
- bounded queue/concurrency, queue-full responses, cancellation and shutdown behavior;
- timeout tests proving one backend admission does not cause automatic duplicate generation;
- benchmark latency/throughput/resource data per configured model;
- 24h/72h target-host soak reports, restart/recovery behavior and disk/RAM measurements;
- backup/restore or volume-preservation checks for the Ollama model volume.

Never expose Ollama port 11434. Keep gateway port 8080 private and authenticated. CI smoke tests do not replace target-VM evidence.

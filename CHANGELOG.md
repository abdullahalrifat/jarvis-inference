# Changelog

## 0.3.2

### Performance and reliability

- Batch embedding inputs into one Ollama `/api/embed` request, preserving input order and rejecting incomplete batches.
- Return immediately for an empty embedding batch without waking the backend.

### Tests

- Cover batching, response ordering, empty input, and incomplete backend responses.


## 0.3.1

### Security

- Fail startup when `INFERENCE_API_KEY` is missing unless the explicit development-only `INFERENCE_ALLOW_INSECURE_NO_AUTH=true` override is set.
- Return 503 when authentication is not configured and 401 when configured credentials are missing or invalid.

### Reliability

- Add regression coverage ensuring ambiguous backend generation timeouts are not automatically replayed.
- Add security configuration and authentication tests.

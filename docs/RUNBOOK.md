# Runbook

## Health

From the inference VM:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

From a client VM:

```bash
curl http://<INFERENCE_IP>:8080/ready
```

## Restart

Restart only the gateway when the application is unhealthy:

```bash
docker compose restart jarvis-inference
```

Restart the full stack when Ollama itself is unhealthy:

```bash
docker compose restart ollama jarvis-inference
```

## Update

```bash
git pull --ff-only
bash scripts/install.sh
```

The installer rebuilds the gateway and preserves the Ollama model volume.

## Networking

If clients receive connection refused, verify:

```bash
docker ps
hostname -I
```

The gateway must publish 8080 as `0.0.0.0:8080->8080/tcp` for cross-VM access. Set `INFERENCE_BIND_ADDRESS=0.0.0.0` in `.env`.

Keep the host firewall restricted to trusted private-network clients.

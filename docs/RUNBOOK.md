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

## Standard lifecycle

### Deploy from scratch

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
cp .env.example .env
chmod 600 .env
# edit .env; for cross-VM access set INFERENCE_BIND_ADDRESS=0.0.0.0 and a real INFERENCE_API_KEY
bash scripts/install.sh
```

### Update and redeploy

```bash
cd ~/docker/jarvis-inference
git status
git pull --ff-only
bash scripts/install.sh
```

The installer is the canonical redeployment path. It preserves the Ollama named volume.

### Stop / start

```bash
docker compose stop
docker compose start
```

### Shutdown

```bash
docker compose down
```

This removes containers and the Compose network but keeps model data.

### Destructive cleanup

```bash
docker compose down -v
```

This also removes the Ollama model volume. Models must be downloaded again on the next deployment.

### Complete application removal

```bash
docker compose down -v
cd ..
rm -rf jarvis-inference
```

Only do this when retiring the VM/application. Preserve the production `.env` securely if recovery is required.

### Verify after reboot

```bash
docker compose ps
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/ready
```

If services did not start automatically:

```bash
docker compose up -d
```

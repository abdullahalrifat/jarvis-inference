# Disaster recovery

The repository is the deployment source of truth and Ollama models are stored in the named Docker volume `ollama`.

## Rebuild the VM

1. Install Docker and Compose.
2. Clone the repository.
3. Restore the production `.env`.
4. Set the required `INFERENCE_BIND_ADDRESS` and API key.
5. Run:

```bash
bash scripts/install.sh
```

The installer recreates the containers and downloads the configured models.

## Verify

```bash
docker compose ps
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

For a remote client, also verify the private-network address and API-key authentication.

## Important

Back up `.env` separately and keep it out of Git. It contains the inference API key.

Model digests in `models/manifest.yaml` should be reviewed before accepting a different model artifact during recovery.

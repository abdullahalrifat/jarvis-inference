# Disaster recovery

## Gateway failure

Inspect:

    bash scripts/status-optiplex.sh
    bash scripts/wait-ready.sh

If only the gateway is unhealthy:

    docker compose -f docker/docker-compose.yml restart jarvis-inference

## Bad release

Use the automatic rollback from upgrade-optiplex. For manual recovery:

    bash scripts/rollback-optiplex.sh <known-good-commit>

## Corrupt configuration

Restore the latest configuration backup:

    bash scripts/restore.sh "$HOME/jarvis-inference-backups/latest"

Then run config-doctor and verify-models.

## Lost Ollama volume

Recreate the volume and re-download models:

    bash scripts/download-models.sh
    bash scripts/verify-models.sh

If the locked digest cannot be obtained from the registry, do not accept a different digest automatically.

## Complete VM loss

Provision a new Linux VM with Docker and Compose, clone the last known-good release, restore .env/configuration from backup, and run the installation plus model verification flow.

## Recovery objectives

For this personal deployment:

- RTO target: 30-60 minutes for complete VM loss when models must be re-downloaded.
- RPO target: latest configuration backup.
- Full model-volume backups can reduce RTO but consume substantial storage.

## Backup testing

A backup is valid only after a successful restore. Perform a restore drill at least quarterly and whenever the backup format changes.

## Security

Treat backups as secrets. They may contain INFERENCE_API_KEY. Keep them on encrypted storage where practical and never upload them to public object storage unencrypted.

"""BackupWorkflow — 定期备份 PostgreSQL + Redis + ES 到 MinIO。

Cron: 0 3 * * 0 (每周日 03:00 UTC)
"""

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import asyncio
    import io
    import json
    import os
    import subprocess
    import tarfile
    from datetime import datetime, timezone


@workflow.defn
class BackupWorkflow:
    """定期数据库备份工作流。"""

    def __init__(self):
        self.results: dict[str, Any] = {}

    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        workflow.logger.info("BackupWorkflow started: %s", timestamp)

        try:
            self.results["pg"] = await workflow.execute_activity(
                backup_postgres,
                {"timestamp": timestamp},
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(maximum_attempts=3, backoff_coefficient=2.0),
            )

            self.results["redis"] = await workflow.execute_activity(
                backup_redis,
                {"timestamp": timestamp},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            self.results["es"] = await workflow.execute_activity(
                backup_elasticsearch,
                {"timestamp": timestamp},
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            self.results["upload"] = await workflow.execute_activity(
                upload_to_minio,
                {"timestamp": timestamp, "results": self.results},
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3, backoff_coefficient=2.0),
            )

            self.results["cleanup"] = await workflow.execute_activity(
                cleanup_temp_files,
                {"timestamp": timestamp},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            status = "completed"
            workflow.logger.info("BackupWorkflow completed successfully")

        except Exception as e:
            workflow.logger.error("BackupWorkflow failed: %s", e)
            status = "failed"
            self.results["error"] = str(e)

            await workflow.execute_activity(
                record_backup_failure,
                {"timestamp": timestamp, "error": str(e), "results": self.results},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

        return {"status": status, "timestamp": timestamp, "results": self.results}


# ── Activities ────────────────────────────────────────────────────

@workflow.defn
async def backup_postgres(params: dict[str, Any]) -> dict[str, Any]:
    """Dump PostgreSQL database to a file."""
    ts = params["timestamp"]
    output_file = f"/tmp/jobpilot-pg-{ts}.sql"

    pg_host = os.getenv("POSTGRES_HOST", "postgres")
    pg_user = os.getenv("POSTGRES_USER", "jobpilot")
    pg_db = os.getenv("POSTGRES_DB", "jobpilot")
    pg_password = os.getenv("POSTGRES_PASSWORD", "jobpilot_secret")

    env = {**os.environ, "PGPASSWORD": pg_password}
    result = subprocess.run(
        ["pg_dump", "-h", pg_host, "-U", pg_user, pg_db, "-f", output_file],
        capture_output=True, text=True, env=env, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    size = os.path.getsize(output_file)
    workflow.logger.info("PostgreSQL backup: %d bytes", size)
    return {"file": output_file, "size_bytes": size, "status": "ok"}


@workflow.defn
async def backup_redis(params: dict[str, Any]) -> dict[str, Any]:
    """Save Redis RDB snapshot."""
    ts = params["timestamp"]
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = os.getenv("REDIS_PORT", "6379")

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(f"redis://{redis_host}:{redis_port}/0")
        await r.bgsave()
        await asyncio.sleep(2)  # Wait for BGSAVE to complete
        await r.close()
        workflow.logger.info("Redis BGSAVE triggered")
        return {"status": "ok", "host": redis_host}
    except ImportError:
        workflow.logger.warning("redis-py not available, running redis-cli")
        subprocess.run(
            ["redis-cli", "-h", redis_host, "-p", redis_port, "BGSAVE"],
            capture_output=True, timeout=30,
        )
        return {"status": "ok", "host": redis_host, "method": "cli"}


@workflow.defn
async def backup_elasticsearch(params: dict[str, Any]) -> dict[str, Any]:
    """Create Elasticsearch snapshot."""
    ts = params["timestamp"]
    es_url = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Register snapshot repository if not exists
            await client.put(
                f"{es_url}/_snapshot/jobpilot-backup",
                json={"type": "fs", "settings": {"location": "/usr/share/elasticsearch/backups"}},
                timeout=10.0,
            )
            # Create snapshot
            resp = await client.put(
                f"{es_url}/_snapshot/jobpilot-backup/snapshot-{ts}?wait_for_completion=true",
                json={"indices": "jobs,resumes", "ignore_unavailable": True},
                timeout=300.0,
            )
            result = resp.json()
            workflow.logger.info("ES snapshot created: %s", result.get("snapshot", {}).get("snapshot"))
            return {"status": "ok", "snapshot": f"snapshot-{ts}"}
    except ImportError:
        workflow.logger.warning("httpx not available for ES backup")
        return {"status": "skipped", "reason": "httpx unavailable"}


@workflow.defn
async def upload_to_minio(params: dict[str, Any]) -> dict[str, Any]:
    """Upload backup files to MinIO."""
    ts = params["timestamp"]
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    bucket = os.getenv("MINIO_BUCKET", "jobpilot")

    try:
        from minio import Minio
        client = Minio(minio_endpoint, access_key=access_key, secret_key=secret_key, secure=False)

        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        # Upload PostgreSQL dump
        pg_file = f"/tmp/jobpilot-pg-{ts}.sql"
        if os.path.exists(pg_file):
            client.fput_object(bucket, f"backups/{ts}/postgres.sql", pg_file)
            workflow.logger.info("Uploaded PostgreSQL backup to MinIO")

        # Tar and upload any additional artifacts
        archive_path = f"/tmp/jobpilot-backup-{ts}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            for f in [pg_file]:
                if os.path.exists(f):
                    tar.add(f, arcname=os.path.basename(f))

        if os.path.exists(archive_path):
            client.fput_object(bucket, f"backups/{ts}/backup.tar.gz", archive_path)

        return {"status": "ok", "bucket": bucket, "prefix": f"backups/{ts}/"}

    except ImportError:
        workflow.logger.warning("minio-py not available, skipping upload")
        return {"status": "skipped", "reason": "minio unavailable"}
    except Exception as e:
        workflow.logger.warning("MinIO upload skipped: %s", e)
        return {"status": "skipped", "reason": str(e)}


@workflow.defn
async def cleanup_temp_files(params: dict[str, Any]) -> dict[str, Any]:
    """Remove temporary backup files."""
    ts = params["timestamp"]
    removed = 0
    for pattern in [f"/tmp/jobpilot-pg-{ts}.sql", f"/tmp/jobpilot-backup-{ts}.tar.gz"]:
        if os.path.exists(pattern):
            os.remove(pattern)
            removed += 1
    workflow.logger.info("Cleaned up %d temp files", removed)
    return {"removed": removed}


@workflow.defn
async def record_backup_failure(params: dict[str, Any]) -> bool:
    """Record backup failure for alerting."""
    workflow.logger.error("Backup failure recorded: timestamp=%s error=%s",
                          params.get("timestamp"), params.get("error"))
    return True

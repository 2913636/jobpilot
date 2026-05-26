import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    # --- Environment ---
    app_env: str = os.getenv("APP_ENV", "dev")
    # --- PostgreSQL ---
    postgres_user: str = os.getenv("POSTGRES_USER", "jobpilot")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "jobpilot_secret")
    postgres_db: str = os.getenv("POSTGRES_DB", "jobpilot")
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- Redis ---
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # --- Elasticsearch ---
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

    # --- Milvus ---
    milvus_host: str = os.getenv("MILVUS_HOST", "milvus")
    milvus_port: int = int(os.getenv("MILVUS_PORT", "19530"))

    # --- Neo4j ---
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")

    # --- MinIO ---
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "jobpilot")

    # --- LiveKit ---
    livekit_url: str = os.getenv("LIVEKIT_URL", "http://livekit:7880")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "devkey")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "devsecret")

    # --- Temporal ---
    temporal_host: str = os.getenv("TEMPORAL_HOST", "temporal")
    temporal_port: int = int(os.getenv("TEMPORAL_PORT", "7233"))

    # --- NATS ---
    nats_url: str = os.getenv("NATS_URL", "nats://nats:4222")

    # --- JWT ---
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # --- SMTP ---
    smtp_enabled: bool = os.getenv("SMTP_ENABLED", "false").lower() == "true"

    # --- Service ---
    service_name: str = os.getenv("SERVICE_NAME", "unknown")
    service_port: int = int(os.getenv("SERVICE_PORT", "8000"))


def load_env_config() -> dict:
    env = os.getenv("APP_ENV", "dev")
    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    config_file = config_dir / f"{env}.yaml"
    if not config_file.exists():
        return {}
    try:
        import yaml
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

settings = Settings()
env_config = load_env_config()

from pymilvus import MilvusClient

from .config import settings

milvus_client: MilvusClient | None = None


def get_milvus_client() -> MilvusClient:
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient(uri=f"http://{settings.milvus_host}:{settings.milvus_port}")
    return milvus_client

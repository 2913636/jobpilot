from elasticsearch import AsyncElasticsearch

from .config import settings

es_client: AsyncElasticsearch | None = None


async def get_es_client() -> AsyncElasticsearch:
    global es_client
    if es_client is None:
        es_client = AsyncElasticsearch(
            settings.elasticsearch_url,
            max_retries=3,
            retry_on_timeout=True,
            request_timeout=30,
            connections_per_node=10,
            http_compress=True,
        )
    return es_client


async def close_es_client() -> None:
    global es_client
    if es_client:
        await es_client.close()
        es_client = None

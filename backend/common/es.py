from elasticsearch import AsyncElasticsearch

from .config import settings

es_client: AsyncElasticsearch | None = None


async def get_es_client() -> AsyncElasticsearch:
    global es_client
    if es_client is None:
        es_client = AsyncElasticsearch(settings.elasticsearch_url)
    return es_client


async def close_es_client() -> None:
    global es_client
    if es_client:
        await es_client.close()
        es_client = None

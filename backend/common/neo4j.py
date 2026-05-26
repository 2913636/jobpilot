from neo4j import AsyncGraphDatabase

from .config import settings

_driver = None


def get_neo4j_driver():
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password) if settings.neo4j_password else None,
        )
    return _driver


async def close_neo4j_driver() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None

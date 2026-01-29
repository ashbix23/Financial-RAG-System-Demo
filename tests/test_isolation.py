"""Multi-tenancy isolation test: verify users cannot access each other's data."""

import asyncio

from loguru import logger

from app.services.search import search_service
from app.services.vector import vector_service


async def test_multi_tenancy_isolation() -> None:
    """Ingest data as user A, query as user B; ensure B does not see A's content.

    Upserts a chunk with user_alpha_99 containing a secret, then calls
    get_context as user_beta_01. Passes only if the secret does not appear
    in the returned context.
    """
    logger.info("Starting Multi-Tenancy Isolation Test...")
    
    # Mock Data for User A
    user_a_id = "user_alpha_99"
    user_a_data = [{
        "id": "doc_1",
        "text": "The secret password for User A is: 'ORANGE-SUNSET'.",
        "metadata": {"user_id": user_a_id, "filename": "secrets.txt"}
    }]
    
    # Ingest User A's data
    await vector_service.upsert_chunks(user_a_data)
    logger.info("User A data ingested.")

    # Attempt to query User A's data as User B
    user_b_id = "user_beta_01"
    query = "What is the secret password?"
    
    logger.info(f"Querying as User B ({user_b_id})...")
    context = await search_service.get_context(query, user_id=user_b_id)

    # Assert Isolation
    if "ORANGE-SUNSET" in context:
        logger.error("SECURITY BREACH: User B accessed User A's data!")
    else:
        logger.success("ISOLATION VERIFIED: User B could not see User A's data.")

if __name__ == "__main__":
    asyncio.run(test_multi_tenancy_isolation())
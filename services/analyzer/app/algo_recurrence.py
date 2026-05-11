import logging

from .config import settings
from . import embeddings
from database.queries import dao

logger = logging.getLogger(__name__)


async def check_and_handle(issue_text: str, entity_id: int, review_id: int) -> bool:
    """
    Returns True if a recurrence was detected (entity belongs to an open cluster).
    Adds entity to existing cluster or creates a new one.
    """
    vec = await embeddings.get_embedding(issue_text)
    neighbors = embeddings.search_similar(vec, k=5)

    for neighbor_entity_id, score in neighbors:
        if score < settings.RECURRENCE_THRESHOLD:
            continue

        cluster_id = await dao.get_entity_cluster(neighbor_entity_id)
        if not cluster_id:
            continue

        status = await dao.get_cluster_status(cluster_id)
        if status == "open":
            await dao.update_entity_cluster(entity_id, cluster_id)
            await dao.touch_cluster(cluster_id)
            logger.info("Recurrence detected: cluster_id=%s score=%.3f", cluster_id, score)
            return True

    # No open cluster matched — create new
    cluster_id = await dao.insert_cluster(issue_text[:200])
    await dao.update_entity_cluster(entity_id, cluster_id)
    embeddings.add_to_index(entity_id, vec)
    logger.info("New cluster created: id=%s label=%.40s", cluster_id, issue_text)
    return False


async def close_stale_clusters() -> None:
    """Closes open clusters older than 3 days if last 5 reviews are 70%+ positive."""
    cluster_ids = await dao.get_stale_open_clusters()
    for cid in cluster_ids:
        sentiments = await dao.get_last_cluster_sentiments(cid, n=5)
        if len(sentiments) < 5:
            continue
        positive_ratio = sentiments.count("positive") / len(sentiments)
        if positive_ratio >= 0.7:
            await dao.close_cluster(cid)
            logger.info("Cluster %s closed (positive ratio=%.2f)", cid, positive_ratio)

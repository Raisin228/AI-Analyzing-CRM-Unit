import logging

from ..database import DAO

logger = logging.getLogger(__name__)


async def check_and_handle(category: str, entity_id: int) -> bool:
    """
    Returns True if a recurrence was detected (open cluster exists for this category).
    Adds entity to existing cluster or creates a new one.
    """
    cluster_id = await DAO.get_open_cluster_by_category(category)
    if cluster_id:
        await DAO.update_entity_cluster(entity_id, cluster_id)
        await DAO.touch_cluster(cluster_id)
        logger.info("Recurrence detected: category=%s cluster_id=%s", category, cluster_id)
        return True

    cluster_id = await DAO.insert_cluster(category)
    await DAO.update_entity_cluster(entity_id, cluster_id)
    logger.info("New cluster created: id=%s category=%s", cluster_id, category)
    return False


async def close_stale_clusters() -> None:
    """Closes open clusters older than 3 days if last 5 reviews are 70%+ positive."""
    cluster_ids = await DAO.get_stale_open_clusters()
    for cid in cluster_ids:
        sentiments = await DAO.get_last_cluster_sentiments(cid, n=5)
        if len(sentiments) < 5:
            continue
        positive_ratio = sentiments.count("positive") / len(sentiments)
        if positive_ratio >= 0.7:
            await DAO.close_cluster(cid)
            logger.info("Cluster %s closed (positive_ratio=%.2f)", cid, positive_ratio)

import logging

import numpy as np

from .config import settings
from . import dispatcher
import redis_service
from database.queries import dao

logger = logging.getLogger(__name__)

_VOLUME_COOLDOWN_KEY = "anomaly:volume:cooldown"
_TOPIC_COOLDOWN_KEY = "anomaly:topic:cooldown"
_COOLDOWN_SEC = 4 * 3600


async def _cooldown_active(key: str) -> bool:
    redis = redis_service.client()
    if redis is None:
        return False
    return bool(await redis.get(key))


async def _set_cooldown(key: str) -> None:
    redis = redis_service.client()
    if redis:
        await redis.setex(key, _COOLDOWN_SEC, "1")


async def check_volume_anomaly() -> None:
    if await _cooldown_active(_VOLUME_COOLDOWN_KEY):
        return

    current = await dao.count_negative_last_24h()
    baseline = await dao.count_negative_by_day_7d()

    if len(baseline) < 2:
        return

    mean = float(np.mean(baseline))
    std = float(np.std(baseline))

    if std == 0:
        return

    z_score = (current - mean) / std
    logger.debug("Volume anomaly check: current=%d mean=%.1f std=%.1f z=%.2f", current, mean, std, z_score)

    if z_score >= settings.ANOMALY_ZSCORE_THRESHOLD:
        await dispatcher.send_event(
            event_type="volume_anomaly",
            review_id=None,
            description=f"Аномальный рост негативных отзывов: z-score={z_score:.2f}",
            metadata={"z_score": round(z_score, 3), "current_count": current, "baseline_mean": round(mean, 1)},
        )
        await _set_cooldown(_VOLUME_COOLDOWN_KEY)


async def check_topic_shift() -> None:
    if await _cooldown_active(_TOPIC_COOLDOWN_KEY):
        return

    current = await dao.issue_entity_counts_24h()
    baseline = await dao.issue_entity_counts_7d()

    if not current or not baseline:
        return

    all_topics = set(current) | set(baseline)
    eps = 1e-10

    p_cur = np.array([current.get(t, 0) + eps for t in all_topics], dtype=float)
    p_bas = np.array([baseline.get(t, 0) + eps for t in all_topics], dtype=float)
    p_cur /= p_cur.sum()
    p_bas /= p_bas.sum()

    kl = float(np.sum(p_cur * np.log(p_cur / p_bas)))
    logger.debug("Topic shift KL=%.4f threshold=%.2f", kl, settings.ANOMALY_KL_THRESHOLD)

    if kl >= settings.ANOMALY_KL_THRESHOLD:
        topics_list = list(all_topics)
        deltas = p_cur - p_bas
        shifted_topic = topics_list[int(np.argmax(deltas))]

        await dispatcher.send_event(
            event_type="topic_shift",
            review_id=None,
            description=f"Смещение тематики жалоб (KL={kl:.3f}): рост по теме «{shifted_topic}»",
            metadata={"kl_divergence": round(kl, 4), "shifted_topic": shifted_topic},
        )
        await _set_cooldown(_TOPIC_COOLDOWN_KEY)

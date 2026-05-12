import logging

import numpy as np

from analyzer.app.config import settings
from analyzer.app import dispatcher
from analyzer.redis_service import RedisManager
from analyzer.database import DAO

logger = logging.getLogger(__name__)

# Один ключ т.к мы ищем общий всплеск негатива, а не по конкретным товарам.
_VOLUME_COOLDOWN_KEY = "anomaly:volume:cooldown"
_TOPIC_COOLDOWN_KEY = "anomaly:topic:cooldown"


class AnomalyDetector:
    """Обнаруживает Аномальное поведение пользователей."""

    @staticmethod
    async def check_topic_shift() -> None:
        """
        Вычисление KL-дивергенции.
        [Насколько текущее распределение отличается от обычного?]

        :return:
        """

        if await AnomalyDetector._cooldown_active(_TOPIC_COOLDOWN_KEY):
            return

        current = await DAO.issue_category_counts_24h()
        baseline = await DAO.issue_category_counts_7d()

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
            await AnomalyDetector._set_cooldown(_TOPIC_COOLDOWN_KEY)

    @staticmethod
    async def check_volume_anomaly() -> None:
        """Вычисляю Z-score и определяю насколько текущее значение необычно по сравнению с нормой."""

        if await AnomalyDetector._cooldown_active(_VOLUME_COOLDOWN_KEY):
            return

        current = await DAO.count_negative_last_24h()
        baseline = await DAO.count_negative_by_day_7d()

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
            await AnomalyDetector._set_cooldown(_VOLUME_COOLDOWN_KEY)

    @staticmethod
    async def _cooldown_active(key: str) -> bool:
        """
        А был ли уже выброшен alert на эту категорию?

        :param key: ключ [возросшее кол-во негатива | на какой-то конкретный товар]
        :return:
        """

        if RedisManager.get().client is None:
            return False
        return bool(await RedisManager.get().client.get(key))

    @staticmethod
    async def _set_cooldown(key: str) -> None:
        """
        После выброшеного alert. На протяжении n-го времени. Не будут создаваться такие же alert.

        :param key: ключ для события.
        :return:
        """

        if RedisManager.get().client:
            await RedisManager.get().client.setex(key, settings.COOLDOWN_SEC, "1")

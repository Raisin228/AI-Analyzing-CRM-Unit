"""Консьюмер. Атрошенко Б. С."""
import json
import logging

from aiokafka import AIOKafkaConsumer

from analyzer.app.config import settings
from ..agent import AIAnalyzerAgent

logger = logging.getLogger(__name__)


class Consumer:
    """Стаскивает отзывы из CRMки"""

    @classmethod
    async def loop_consume(cls) -> None:
        """Забирает сообщение из Kafka и запускает обработку"""

        consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id="analyzer",
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("Kafka consumer started, topic=%s", settings.KAFKA_TOPIC)
        try:
            async for msg in consumer:
                try:
                    data = json.loads(msg.value)
                    await AIAnalyzerAgent.process_review(data)
                except Exception as exc:
                    logger.error("Error processing review offset=%d: %s", msg.offset, exc)
        finally:
            await consumer.stop()

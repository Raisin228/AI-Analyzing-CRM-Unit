"""Агент. Атрошенко Б. С."""

import json
import logging
import re
from datetime import datetime, timezone

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from tenacity import retry, stop_after_attempt, wait_fixed

from .state import ReviewState, CategoryItem
from ..app.config import settings
from ..utils import load_prompt
from ..database import DAO

from ..dispatch import Notifier

logger = logging.getLogger(__name__)

CATEGORIES = ("delivery", "courier", "payment", "product_quality", "support", "app", "other")


class AIAnalyzerAgent:
    """Синглтон логики агента."""

    _agent, _graph = None, None

    def __new__(cls, *args, **kwargs):
        """Конструктор. Объявляю Ollama и LangFuse"""

        if cls._agent is None:
            cls._agent = super().__new__(cls)
            cls._agent.llm = ChatOllama(
                base_url=settings.OLLAMA_URL,
                model=settings.OLLAMA_MODEL,
                format="json",
                temperature=0,
            )

            cls._agent.langfuse_handler = None
            if settings.LANGFUSE_PUBLIC_KEY and not settings.LANGFUSE_PUBLIC_KEY.startswith("pk-lf-placeholder"):
                try:
                    cls._agent.langfuse_handler = CallbackHandler()
                    logger.info("LangFuse tracing enabled")
                except Exception as exc:
                    logger.warning("LangFuse init failed (tracing disabled): %s", exc)

        return cls._agent

    @classmethod
    def _build_graph(cls) -> CompiledStateGraph:
        """
        Собираю узлы для графа состояний LangGraph.

        :return: скомпилированный граф состояний.
        """

        wf = StateGraph(ReviewState)
        wf.add_node("classify_categories", cls.classify_categories)
        wf.add_node("classify_sentiment", cls.classify_sentiment)
        wf.add_node("detect_mismatch", cls.detect_mismatch)
        wf.add_node("save_results", cls.save_results)
        wf.set_entry_point("classify_categories")
        wf.add_edge("classify_categories", "classify_sentiment")
        wf.add_edge("classify_sentiment", "detect_mismatch")
        wf.add_edge("detect_mismatch", "save_results")
        wf.add_edge("save_results", END)
        return wf.compile()

    @classmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _call_llm(cls, prompt: str) -> str:
        """
        Вызов LLM.

        :param prompt: промпт для генерации.
        :return: ответ модельки.
        """

        resp = await cls._agent.llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"callbacks": [cls._agent.langfuse_handler]} if cls._agent.langfuse_handler else {},
        )
        return resp.content

    @classmethod
    def _extract_json(cls, text: str) -> dict:
        """
        Извлечь

        :param text: JSON ответ от LLMки.
        :return: словарик с ответом.
        """

        match = re.search(r"\{.*}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON in LLM response: {text[:200]}")

    @classmethod
    async def classify_categories(cls, state: ReviewState) -> dict:
        """
        Классификатор категорий. По отзыву определяет группу категорий.

        :param state: состояние графа.
        :return: словарик со списком категорий для одного пункта.
        """

        prompt = load_prompt(
            "classify_categories.txt",
            categories=", ".join(CATEGORIES),
            text=state["text"],
        )
        try:
            raw = await cls._call_llm(prompt)
            data = cls._extract_json(raw)
            items: list[CategoryItem] = [
                item for item in data.get("categories", [])
                if isinstance(item, dict) and item.get("name") in CATEGORIES
            ]
            return {"categories": items}
        except Exception as exc:
            logger.error("classify_categories failed: %s", exc)
            return {"categories": []}

    @classmethod
    async def classify_sentiment(cls, state: ReviewState) -> dict:
        """
        Определить характер отзыва.

        :param state:
        :return: словарь типа намерение: уверенность от 0 .. 1
        """

        issues = [c["name"] for c in state["categories"] if c.get("is_issue")]
        prompt = load_prompt(
            "classify_sentiment.txt",
            text=state["text"],
            issues=", ".join(issues),
        )
        try:
            raw = await cls._call_llm(prompt)
            data = cls._extract_json(raw)
            sentiment = data.get("sentiment", "neutral")
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            return {
                "sentiment": sentiment,
                "confidence": float(data.get("confidence", 0.5)),
            }
        except Exception as exc:
            logger.error("classify_sentiment failed: %s", exc)
            return {"sentiment": "neutral", "confidence": 0.0}

    @classmethod
    def detect_mismatch(cls, state: ReviewState) -> dict:
        """
        Обнаружить несоответствие между рейтингом и текстовым описание отзыва.

        :param state: состояние графа.
        :return: словарик с флагом несоответствия.
        """

        rating = state["rating"]
        sentiment = state["sentiment"]
        mismatch = (rating >= 4 and sentiment == "negative") or (rating <= 2 and sentiment == "positive")
        return {"mismatch": mismatch}

    @classmethod
    def get_graph(cls) -> CompiledStateGraph:
        """
        Получить данные LangGraph и создать его если нужно.

        :return: скомпилированный граф состояний.
        """

        if cls._graph is None:
            cls._graph = cls._build_graph()
        return cls._graph

    @classmethod
    async def process_review(cls, review_data: dict) -> None:
        """
        Обработать отзыв.

        :param review_data: данные отзыва.
        :return:
        """

        crm_review_uuid = str(review_data["id"])

        state = ReviewState(
            **{
                "external_id": crm_review_uuid,
                "text": review_data["text"],
                "rating": review_data["rating"],
                "customer_name": review_data.get("customer_name", ""),
                "product_id": str(review_data.get("product_id", "")),
                "created_at": str(review_data.get("created_at", "")),
                "categories": [],
                "sentiment": "neutral",
                "confidence": 0.0,
                "mismatch": False,
                "review_db_id": None,
                "issue_entity_ids": {},
            }
        )

        result = await cls.get_graph().ainvoke(state)
        review_db_id = result.get("review_db_id")

        if review_db_id is None:
            return

        if result["mismatch"]:
            await Notifier.send_event(
                "sentiment_mismatch",
                crm_review_uuid,
                f"Рейтинг {result['rating']} не совпадает с тональностью «{result['sentiment']}»",
            )

        if result["sentiment"] == "negative" and result["confidence"] >= 0.9:
            await Notifier.send_event(
                "critical_negative",
                crm_review_uuid,
                f"Критически негативный отзыв (уверенность {result['confidence']:.0%})",
                metadata={"confidence": result["confidence"]},
            )

        for category, entity_id in result.get("issue_entity_ids", {}).items():
            is_recurring = await algo_recurrence.check_and_handle(category, entity_id)
            if is_recurring:
                await Notifier.send_event(
                    "recurring_issue",
                    crm_review_uuid,
                    f"Рецидив проблемы в категории «{category}»",
                    metadata={"category": category},
                )
                break

    @classmethod
    async def save_results(cls, state: ReviewState) -> dict:
        """
        Сохранить результаты обработки в БД.

        :param state: состояние графа.
        :return: словарь с сущностями БД.
        """

        now = datetime.now(timezone.utc)
        try:
            created_at = datetime.fromisoformat(state["created_at"].replace("Z", "+00:00"))
        except Exception:
            created_at = now

        review_db_id = await DAO.insert_review(
            external_id=state["external_id"],
            customer_name=state["customer_name"],
            text=state["text"],
            rating=state["rating"],
            created_at=created_at,
            product_id=state["product_id"],
            sentiment=state["sentiment"],
            rating_mismatch=state["mismatch"],
            processed_at=now,
        )
        if review_db_id is None:
            return {"review_db_id": None, "issue_entity_ids": {}}

        issue_entity_ids: dict[str, int] = {}
        for item in state["categories"]:
            category = item["name"]
            is_issue = bool(item.get("is_issue", False))
            eid = await DAO.insert_entity(review_db_id, category, is_issue)
            if is_issue:
                issue_entity_ids[category] = eid

        return {"review_db_id": review_db_id, "issue_entity_ids": issue_entity_ids}

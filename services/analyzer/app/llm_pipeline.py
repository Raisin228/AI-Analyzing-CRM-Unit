import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, TypedDict

from aiokafka import AIOKafkaConsumer
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from tenacity import retry, stop_after_attempt, wait_fixed

from .config import settings
from . import dispatcher, algo_recurrence
from ..database import DAO

logger = logging.getLogger(__name__)

_llm: Optional[ChatOllama] = None
_langfuse_handler = None

CATEGORIES = ("delivery", "courier", "payment", "product_quality", "support", "app", "other")


def init_llm() -> None:
    global _llm, _langfuse_handler
    _llm = ChatOllama(
        base_url=settings.OLLAMA_URL,
        model=settings.OLLAMA_MODEL,
        format="json",
        temperature=0,
    )
    if settings.LANGFUSE_PUBLIC_KEY and not settings.LANGFUSE_PUBLIC_KEY.startswith("pk-lf-placeholder"):
        try:
            from langfuse.callback import CallbackHandler
            _langfuse_handler = CallbackHandler(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            logger.info("LangFuse tracing enabled")
        except Exception as exc:
            logger.warning("LangFuse init failed (tracing disabled): %s", exc)


# ── state ─────────────────────────────────────────────────────────────────────

class CategoryItem(TypedDict):
    name: str
    is_issue: bool


class ReviewState(TypedDict):
    external_id: str
    text: str
    rating: int
    customer_name: str
    product_id: str
    created_at: str
    categories: list[CategoryItem]   # [{"name": "courier", "is_issue": True}, ...]
    sentiment: str
    confidence: float
    mismatch: bool
    review_db_id: Optional[int]
    issue_entity_ids: dict[str, int]  # category → entity DB id


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON in LLM response: {text[:200]}")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def _call_llm(prompt: str) -> str:
    resp = await _llm.ainvoke(
        [HumanMessage(content=prompt)],
        config={"callbacks": [_langfuse_handler]} if _langfuse_handler else {},
    )
    return resp.content


# ── graph nodes ───────────────────────────────────────────────────────────────

async def classify_categories(state: ReviewState) -> dict:
    prompt = (
        "Проанализируй отзыв клиента и определи какие из следующих категорий в нём упомянуты.\n"
        "Для каждой найденной категории укажи, является ли она проблемой (жалобой клиента).\n\n"
        f"Доступные категории: {', '.join(CATEGORIES)}\n\n"
        f"Отзыв: {state['text']}\n\n"
        'Ответ строго в JSON: {"categories": [{"name": "courier", "is_issue": true}, ...]}\n'
        "Включай только категории, реально упомянутые в отзыве."
    )
    try:
        raw = await _call_llm(prompt)
        data = _extract_json(raw)
        items: list[CategoryItem] = [
            item for item in data.get("categories", [])
            if isinstance(item, dict) and item.get("name") in CATEGORIES
        ]
        return {"categories": items}
    except Exception as exc:
        logger.error("classify_categories failed: %s", exc)
        return {"categories": []}


async def classify_sentiment(state: ReviewState) -> dict:
    issues = [c["name"] for c in state["categories"] if c.get("is_issue")]
    prompt = (
        "Определи тональность отзыва клиента.\n"
        f"Отзыв: {state['text']}\n"
        f"Проблемные категории: {issues}\n\n"
        'Ответ строго в JSON: {"sentiment": "positive" | "negative" | "neutral", "confidence": 0.0..1.0}'
    )
    try:
        raw = await _call_llm(prompt)
        data = _extract_json(raw)
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


def detect_mismatch(state: ReviewState) -> dict:
    rating = state["rating"]
    sentiment = state["sentiment"]
    mismatch = (rating >= 4 and sentiment == "negative") or (rating <= 2 and sentiment == "positive")
    return {"mismatch": mismatch}


async def save_results(state: ReviewState) -> dict:
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


# ── graph ─────────────────────────────────────────────────────────────────────

def _build_graph():
    wf = StateGraph(ReviewState)
    wf.add_node("classify_categories", classify_categories)
    wf.add_node("classify_sentiment", classify_sentiment)
    wf.add_node("detect_mismatch", detect_mismatch)
    wf.add_node("save_results", save_results)
    wf.set_entry_point("classify_categories")
    wf.add_edge("classify_categories", "classify_sentiment")
    wf.add_edge("classify_sentiment", "detect_mismatch")
    wf.add_edge("detect_mismatch", "save_results")
    wf.add_edge("save_results", END)
    return wf.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── main entry ────────────────────────────────────────────────────────────────

async def process_review(review_data: dict) -> None:
    crm_review_uuid = str(review_data["id"])

    state: ReviewState = {
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

    result = await get_graph().ainvoke(state)
    review_db_id = result.get("review_db_id")

    if review_db_id is None:
        return

    if result["mismatch"]:
        await dispatcher.send_event(
            "sentiment_mismatch",
            crm_review_uuid,
            f"Рейтинг {result['rating']} не совпадает с тональностью «{result['sentiment']}»",
        )

    if result["sentiment"] == "negative" and result["confidence"] >= 0.9:
        await dispatcher.send_event(
            "critical_negative",
            crm_review_uuid,
            f"Критически негативный отзыв (уверенность {result['confidence']:.0%})",
            metadata={"confidence": result["confidence"]},
        )

    for category, entity_id in result.get("issue_entity_ids", {}).items():
        is_recurring = await algo_recurrence.check_and_handle(category, entity_id)
        if is_recurring:
            await dispatcher.send_event(
                "recurring_issue",
                crm_review_uuid,
                f"Рецидив проблемы в категории «{category}»",
                metadata={"category": category},
            )
            break


# ── Kafka consumer loop ───────────────────────────────────────────────────────

async def consume_loop() -> None:
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
                await process_review(data)
            except Exception as exc:
                logger.error("Error processing review offset=%d: %s", msg.offset, exc)
    finally:
        await consumer.stop()

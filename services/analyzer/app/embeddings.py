import base64
import hashlib
import logging
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from ..database.queries import dao
from ..redis_service import RedisManager

logger = logging.getLogger(__name__)

_model: Optional[SentenceTransformer] = None
_index: Optional[faiss.IndexFlatIP] = None
_id_map: list[int] = []  # maps FAISS position → entity DB id

EMBEDDING_DIM = 1024
CACHE_TTL = 7 * 24 * 3600  # 7 days


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading multilingual-e5-large model…")
        _model = SentenceTransformer("intfloat/multilingual-e5-large")
        logger.info("Model loaded")
    return _model


async def get_embedding(text: str) -> np.ndarray:
    key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"

    if RedisManager.get().client:
        cached = await RedisManager.get().client.get(key)
        if cached:
            return np.frombuffer(base64.b64decode(cached), dtype=np.float32)

    vec = _get_model().encode(
        "passage: " + text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    if RedisManager.get().client:
        await RedisManager.get().client.setex(key, CACHE_TTL, base64.b64encode(vec.tobytes()))

    return vec


def search_similar(vector: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
    """Returns [(entity_id, score), ...]"""
    global _index, _id_map
    if _index is None or _index.ntotal == 0:
        return []

    k = min(k, _index.ntotal)
    q = vector.reshape(1, -1).astype(np.float32)
    distances, indices = _index.search(q, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if 0 <= idx < len(_id_map):
            results.append((_id_map[idx], float(dist)))
    return results


def add_to_index(entity_id: int, vector: np.ndarray) -> None:
    global _index, _id_map
    if _index is None:
        _index = faiss.IndexFlatIP(EMBEDDING_DIM)
    v = vector.reshape(1, -1).astype(np.float32)
    _index.add(v)
    _id_map.append(entity_id)


async def rebuild_index() -> None:
    global _index, _id_map
    logger.info("Building FAISS index from DB…")
    _index = faiss.IndexFlatIP(EMBEDDING_DIM)
    _id_map = []

    rows = await dao.get_all_issue_embeddings()
    for entity_id, emb_bytes in rows:
        vec = np.frombuffer(emb_bytes, dtype=np.float32).reshape(1, -1)
        _index.add(vec)
        _id_map.append(entity_id)

    logger.info("FAISS index built: %d vectors", _index.ntotal)

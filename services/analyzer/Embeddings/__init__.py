import base64
import hashlib
import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from redis_service import client as redis_client

logger = logging.getLogger(__name__)

_model: Optional[SentenceTransformer] = None
CACHE_TTL = 7 * 24 * 3600  # 7 days


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("intfloat/multilingual-e5-large")
    return _model


async def get_embedding(text: str) -> np.ndarray:
    key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
    redis = redis_client()

    if redis:
        cached = await redis.get(key)
        if cached:
            return np.frombuffer(base64.b64decode(cached), dtype=np.float32)

    vec = _get_model().encode(
        "passage: " + text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    if redis:
        await redis.setex(key, CACHE_TTL, base64.b64encode(vec.tobytes()))

    return vec

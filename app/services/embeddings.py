"""Embedding service for entity, event, and relationship embeddings."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmbeddingRecord
from app.services.openrouter import generate_embeddings, validate_embedding_dimension, OpenRouterError


def _now():
    return datetime.now(timezone.utc)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def embed_texts(
    texts: list[str],
    record_type: str,
    record_ids: list[str],
    db: Session,
) -> list[EmbeddingRecord]:
    """Generate embeddings for texts and store them."""
    settings = get_settings()
    model = settings.openrouter_embedding_model

    vectors = await generate_embeddings(model, texts)

    records = []
    for i, vector in enumerate(vectors):
        if not vector:
            continue

        dimension = len(vector)
        if not validate_embedding_dimension(dimension):
            raise ValueError(
                f"Embedding dimension {dimension} is below minimum {settings.min_embedding_dimension}"
            )

        record = EmbeddingRecord(
            id=str(uuid.uuid4()),
            target_record_type=record_type,
            target_record_id=record_ids[i] if i < len(record_ids) else str(uuid.uuid4()),
            model_name=model,
            dimension_count=dimension,
            vector_data=json.dumps(vector),
            content_hash=_content_hash(texts[i]),
            version_ref=1,
            created_at=_now(),
        )
        db.add(record)
        records.append(record)

    db.commit()
    return records


async def refresh_entity_embeddings(
    db: Session,
    entity_type: str,
    summaries: list[dict[str, str]],
) -> list[EmbeddingRecord]:
    """Refresh embeddings for entities of a given type."""
    texts = [s["summary"] for s in summaries]
    ids = [s["id"] for s in summaries]

    db.query(EmbeddingRecord).filter(
        EmbeddingRecord.target_record_type == entity_type,
    ).delete()
    db.commit()

    return await embed_texts(texts, entity_type, ids, db)


def build_entity_summary(entity: object) -> str:
    """Build a text summary of an entity for embedding."""
    parts = []
    for attr in dir(entity):
        if attr.startswith("_") or attr in ("metadata", "registry"):
            continue
        val = getattr(entity, attr, None)
        if val is not None and isinstance(val, (str, int, float, bool)):
            parts.append(f"{attr}: {val}")
    return " | ".join(parts)

"""The vector index over policy clauses (RAG stage 1, vector index).

Qdrant in local mode: ``location=":memory:"`` for tests, or a directory, with no
server to run. `ingest.py` builds a persisted index offline, as the
architecture's corpus-preparation stage; runtime retrieval opens it with
`attach` and never embeds the corpus. Whether a stored index still matches the
corpus is `ingest.open_index`'s check, not this module's.

Local mode holds a lock on its directory, so only one process can have an index
open at a time. `close` releases it; a second open while it is held raises an
`IndexError_` saying so rather than Qdrant's storage error.

Every point carries the whole clause as its payload. A search result is
therefore a complete, citable `Clause`, not an ID that has to be looked up
again, and what the model is shown is exactly what was indexed.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from typing import Any, Sequence

from .corpus import Clause
from .embedder import Embedder, clause_passage

DEFAULT_COLLECTION = "policy_clauses"

# Fixed namespace so a clause keeps the same point ID across rebuilds.
_POINT_NAMESPACE = uuid.UUID("6f1c9a52-3d7e-4b8a-9c21-5e0f4a7b8d13")


class IndexError_(RuntimeError):
    """Raised when the index is used before it is built or with the wrong model."""


@dataclass(frozen=True)
class ScoredClause:
    """A clause returned by search, with its cosine similarity to the query."""

    clause: Clause
    score: float


class PolicyIndex:
    """Build and search the clause index."""

    def __init__(
        self,
        location: str = ":memory:",
        collection: str = DEFAULT_COLLECTION,
        client: Any | None = None,
    ) -> None:
        self.collection = collection
        self.model_name: str | None = None
        self._size = 0
        if client is not None:
            self._client = client
            return
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise IndexError_(
                "qdrant-client is not installed. Install it with "
                '`pip install -e ".[rag]"`.'
            ) from exc
        if location == ":memory:":
            self._client = QdrantClient(location=":memory:")
            return
        try:
            self._client = QdrantClient(path=str(location))
        except RuntimeError as exc:
            if "already accessed" in str(exc):
                raise IndexError_(
                    f"the policy index at {location} is open in another process. "
                    "Close it (or wait for ingestion to finish) and retry."
                ) from exc
            raise

    def attach(self, model_name: str) -> None:
        """Use a collection that already exists, built with `model_name`."""
        if not self._client.collection_exists(self.collection):
            raise IndexError_(f"collection {self.collection!r} does not exist")
        self.model_name = model_name
        self._size = self._client.count(self.collection).count

    def close(self) -> None:
        """Release the directory lock held by local mode."""
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def __enter__(self) -> "PolicyIndex":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def build(self, clauses: Sequence[Clause], embedder: Embedder) -> None:
        """Replace the collection with `clauses`, embedded by `embedder`."""
        from qdrant_client import models  # type: ignore[import-not-found]

        if not clauses:
            raise IndexError_("refusing to build an empty index")

        vectors = embedder.embed_passages([clause_passage(c) for c in clauses])
        if len(vectors) != len(clauses):
            raise IndexError_(
                f"embedder returned {len(vectors)} vectors for {len(clauses)} clauses"
            )

        if self._client.collection_exists(self.collection):
            self._client.delete_collection(self.collection)
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=len(vectors[0]), distance=models.Distance.COSINE
            ),
        )
        self._client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid5(_POINT_NAMESPACE, clause.clause_id)),
                    vector=vector,
                    payload=dataclasses.asdict(clause),
                )
                for clause, vector in zip(clauses, vectors)
            ],
        )
        self.model_name = embedder.model_name
        self._size = len(clauses)

    def search(
        self,
        query_vector: Sequence[float],
        top_k: int,
        categories: Sequence[str] | None = None,
    ) -> list[ScoredClause]:
        """The `top_k` closest clauses, best first. No cutoff is applied here.

        `categories` restricts the search to clauses whose front-matter
        category is one of those given. The filter runs inside Qdrant, so
        `top_k` counts only matching clauses rather than being filled first and
        filtered after.
        """
        from qdrant_client import models  # type: ignore[import-not-found]

        if self.model_name is None:
            raise IndexError_("the index has not been built")

        query_filter = None
        if categories is not None:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category", match=models.MatchAny(any=list(categories))
                    )
                ]
            )
        response = self._client.query_points(
            collection_name=self.collection,
            query=list(query_vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [
            ScoredClause(clause=Clause(**point.payload), score=float(point.score))
            for point in response.points
        ]

    def __len__(self) -> int:
        return self._size

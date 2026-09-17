"""Turn clauses and queries into vectors (RAG stage 1, embedding model).

`Embedder` is the seam, the same shape of decision as `client.Backend`: the
index and the retriever only ever see this protocol, so tests inject a fake and
never download a model, and a different embedding model is one new class.

FastEmbed is imported lazily inside `FastEmbedEmbedder`, so importing this
package, and running the test suite, needs neither FastEmbed nor network.

Passages and queries are embedded differently on purpose. The default model,
BAAI/bge-small-en-v1.5, is trained with an instruction prefix on queries and
none on passages; FastEmbed's `query_embed` and `passage_embed` apply that
asymmetry. Embedding a query as a passage measurably lowers match quality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Sequence

from .corpus import Clause

# Named exactly, never "latest", for the reason config.PINNED_MODEL is: a
# different model produces different scores, and the retrieval cutoff was
# measured against this one.
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Inside the git-ignored .cache directory, beside the extraction cache. FastEmbed
# otherwise caches under the system temp directory, which gets cleared and
# forces the ~70 MB model to download again.
DEFAULT_MODEL_CACHE_DIR = Path(".cache") / "fastembed"


class EmbedderUnavailable(RuntimeError):
    """Raised when the embedding library or model cannot be loaded."""


class Embedder(Protocol):
    """The embedding seam. Implemented by FastEmbedEmbedder and by test fakes."""

    model_name: str

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Vectors for documents being indexed, in input order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """The vector for one search query."""
        ...


def clause_passage(clause: Clause) -> str:
    """The text embedded for a clause.

    The document title and clause heading are included because a bare clause
    body often never names its subject: SPEC-001-C01 says "stocked by 50 kg
    bag" and only its heading says "Cement".
    """
    return f"{clause.title}. {clause.heading}. {clause.text}"


class FastEmbedEmbedder:
    """Local ONNX embeddings through FastEmbed. No API key, no per-call network.

    The first use downloads the model once into `cache_dir`. After that it runs
    offline.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        cache_dir: str | Path | None = DEFAULT_MODEL_CACHE_DIR,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        if model is not None:
            self._model = model
            return
        try:
            from fastembed import TextEmbedding  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise EmbedderUnavailable(
                "fastembed is not installed. Install it with "
                '`pip install -e ".[rag]"`, or inject an embedder for offline use.'
            ) from exc
        try:
            self._model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(cache_dir) if cache_dir is not None else None,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced with context
            raise EmbedderUnavailable(
                f"could not load embedding model {model_name!r}: {exc}. The first "
                "run needs network access to download it."
            ) from exc

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [_as_list(vector) for vector in self._model.passage_embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        vectors = list(self._model.query_embed([text]))
        return _as_list(vectors[0])


def _as_list(vector: Any) -> list[float]:
    """FastEmbed yields numpy arrays; Qdrant and JSON traces want plain floats."""
    return [float(value) for value in vector]

"""Offline stand-ins for the RAG tests. No model download, no network.

`WordOverlapEmbedder` hashes each word into a fixed-size vector, so cosine
similarity reflects shared vocabulary. That is far cruder than a real model,
but it is deterministic and it preserves the property the tests rely on: a
query about cement lands nearer a clause about cement than one about
conflicts of interest.

`hashlib`, not the built-in `hash()`, which is salted per process and would
make results differ between runs.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

_WORD = re.compile(r"[a-z0-9]+")
DIMENSIONS = 512

# Without these, words every query and clause share ("of", "the", "purchase")
# dominate the overlap and the fake ranks by filler rather than by subject.
# A trained model learns to discount them; this fake has to be told.
_STOPWORDS = frozenset(
    "a an and are as at be by for from in is it must of on or the to with "
    "purchase purchases category estimated total ugx usd".split()
)


class WordOverlapEmbedder:
    def __init__(self, model_name: str = "test/word-overlap") -> None:
        self.model_name = model_name
        self.passage_calls = 0
        self.query_calls = 0

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        self.passage_calls += 1
        return [_embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return _embed(text)


_ITEM_BLOCK = re.compile(r'<item ref="(?P<ref>[^"]+)">(?P<body>.*?)</item>', re.S)
_SUPPLIED_CLAUSE = re.compile(
    r'<policy_clause source_id="(?P<source_id>[^"]+)" version="(?P<version>[^"]+)" '
    r'clause_id="(?P<clause_id>[^"]+)"'
)


class GroundedStubBackend:
    """A scripted Gemini that answers each item from the clauses sent for that item.

    By default every item cites the first clause supplied *for that item*,
    correctly, so a happy-path test cannot pass by citing something retrieval
    never returned. `summary` and `citations` override every item's answer;
    `per_item` overrides chosen items by ref, e.g. ``{"1": {"citations": [...]}}``.
    `raw` replaces the whole response body; `error` is raised instead.
    """

    def __init__(self, summary=None, citations=None, per_item=None, raw=None, error=None):
        self.summary = summary
        self.citations = citations
        self.per_item = per_item or {}
        self.raw = raw
        self.error = error
        self.calls = []

    def generate(self, system_instruction, user_message, config):
        import json

        self.calls.append({"system_instruction": system_instruction,
                           "user_message": user_message, "config": config})
        if self.error is not None:
            raise self.error
        if self.raw is not None:
            return self.raw

        items = []
        for block in _ITEM_BLOCK.finditer(user_message):
            ref = block.group("ref")
            first = _SUPPLIED_CLAUSE.search(block.group("body")).groupdict()
            override = self.per_item.get(ref, {})
            citations = override.get("citations", self.citations)
            if citations is None:
                citations = [{**first, "reason": "It applies to this purchase."}]
            summary = (override.get("summary") or self.summary
                       or f"The supplied rule applies [{first['clause_id']}].")
            items.append({"ref": ref, "summary": summary, "applicable_clauses": citations})
        return json.dumps({"items": items})

    def supplied_for(self, ref):
        """Clause IDs the last call supplied for item `ref`."""
        for block in _ITEM_BLOCK.finditer(self.calls[-1]["user_message"]):
            if block.group("ref") == ref:
                return {m.group("clause_id") for m in _SUPPLIED_CLAUSE.finditer(block.group("body"))}
        return set()


def _embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for word in _WORD.findall(text.lower()):
        if word in _STOPWORDS:
            continue
        bucket = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
        vector[bucket % DIMENSIONS] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]

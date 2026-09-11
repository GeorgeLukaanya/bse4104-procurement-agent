"""Cache keying. The configuration fingerprint is part of the key, not just the doc."""

from __future__ import annotations

import dataclasses
import json

from conftest import StubBackend, conforming_payload

from procurement_agent.cache import cache_key, document_digest
from procurement_agent.config import ExtractionConfig

MARKDOWN = "# Quotation\n\n| Item | Price |\n|---|---|\n| Cement | 34,500 |\n"


def test_identical_document_makes_no_second_api_call(make_extractor):
    backend = StubBackend()
    extractor = make_extractor(backend)

    first = extractor.extract(MARKDOWN, source="q.md")
    second = extractor.extract(MARKDOWN, source="q.md")

    assert backend.call_count == 1, "second extraction must be served from cache"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.attempts == 0
    assert second.record_dict == first.record_dict


def test_changing_the_model_invalidates_the_cache(make_extractor):
    backend = StubBackend()
    make_extractor(backend).extract(MARKDOWN, source="q.md")

    other = ExtractionConfig(model="gemini-3.1-flash")
    result = make_extractor(backend, config=other).extract(MARKDOWN, source="q.md")

    assert backend.call_count == 2
    assert result.cache_hit is False


def test_changing_the_prompt_version_invalidates_the_cache(make_extractor):
    """The defect this prevents: serving a v1.0 result as though it were v1.1.

    Keyed on the document alone, the second extraction below would return the
    record produced under prompt version 1.0 and report it against 1.1, and
    every accuracy figure computed from the cache would attribute one prompt's
    behaviour to another with nothing in the output to show it.
    """
    backend = StubBackend()
    make_extractor(backend).extract(MARKDOWN, source="q.md")

    bumped = ExtractionConfig(prompt_version="1.1")
    result = make_extractor(backend, config=bumped).extract(MARKDOWN, source="q.md")

    assert backend.call_count == 2
    assert result.cache_hit is False
    assert result.config_fingerprint["prompt_version"] == "1.1"


def test_every_fingerprint_field_changes_the_key():
    base = ExtractionConfig()
    variants = [
        dataclasses.replace(base, model="gemini-3.1-flash"),
        dataclasses.replace(base, max_output_tokens=1024),
        dataclasses.replace(base, thinking_budget=128),
        dataclasses.replace(base, prompt_version="2.0"),
        dataclasses.replace(base, response_mime_type="text/plain"),
    ]
    keys = {cache_key(MARKDOWN, base)}
    for variant in variants:
        key = cache_key(MARKDOWN, variant)
        assert key not in keys, f"{variant} produced a colliding cache key"
        keys.add(key)


def test_different_documents_under_one_config_differ():
    config = ExtractionConfig()
    assert cache_key(MARKDOWN, config) != cache_key(MARKDOWN + " ", config)


def test_document_digest_is_stable():
    assert document_digest(MARKDOWN) == document_digest(MARKDOWN)
    assert len(document_digest(MARKDOWN)) == 64


def test_no_cache_mode_skips_lookup_and_store(make_extractor, extraction_cache):
    backend = StubBackend()
    extractor = make_extractor(backend, use_cache=False)
    extractor.extract(MARKDOWN, source="q.md")
    extractor.extract(MARKDOWN, source="q.md")

    assert backend.call_count == 2
    key = extraction_cache.key_for(MARKDOWN, extractor.config)
    assert extraction_cache.get(key) is None


def test_cache_entry_records_the_configuration_that_produced_it(
    make_extractor, extraction_cache
):
    backend = StubBackend()
    extractor = make_extractor(backend)
    result = extractor.extract(MARKDOWN, source="q.md")

    entry = extraction_cache.get(result.cache_key)
    assert entry is not None
    assert entry.config_fingerprint == extractor.config.fingerprint()
    assert entry.document_sha256 == document_digest(MARKDOWN)


def test_corrupt_cache_entry_is_treated_as_a_miss(make_extractor, extraction_cache):
    backend = StubBackend()
    extractor = make_extractor(backend)
    result = extractor.extract(MARKDOWN, source="q.md")

    path = extraction_cache.directory / f"{result.cache_key}.json"
    path.write_text("{ not json", encoding="utf-8")

    again = extractor.extract(MARKDOWN, source="q.md")
    assert again.cache_hit is False
    assert backend.call_count == 2


def test_cached_payload_is_the_record_not_the_raw_response(
    make_extractor, extraction_cache
):
    backend = StubBackend([json.dumps(conforming_payload())])
    extractor = make_extractor(backend)
    result = extractor.extract(MARKDOWN, source="q.md")
    entry = extraction_cache.get(result.cache_key)
    assert set(entry.record) == {
        "supplier_name", "currency", "vat_treatment", "vat_rate_percent",
        "delivery_cost", "lead_time_days", "validity_date", "items",
        "missing_fields",
    }

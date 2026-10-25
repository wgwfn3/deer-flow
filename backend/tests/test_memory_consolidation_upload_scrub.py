"""Regression: a consolidation whose merged content the upload scrub drops must not consume its sources."""

import copy

from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig
from deerflow.agents.memory.backends.deermem.deermem.core import updater as U

_GATE = {"scope": "user", "durability": "durable", "authority": "descriptive"}
_OLD = "2020-01-01T00:00:00Z"


def _fact(fid: str, content: str) -> dict:
    return {"id": fid, "content": content, "category": "context", "confidence": 0.9, "createdAt": _OLD, "source": "t0"}


def _memory(facts: list[dict]) -> dict:
    return {
        "user": {k: {"summary": "", "updatedAt": ""} for k in ("workContext", "personalContext", "topOfMind", "cognitiveStyle")},
        "history": {k: {"summary": "", "updatedAt": ""} for k in ("recentMonths", "earlierContext", "longTermBackground")},
        "facts": facts,
    }


def _consolidate(merged_content: str) -> dict:
    config = DeerMemConfig()
    config.max_facts = 100
    config.fact_confidence_threshold = 0.7
    config.consolidation_enabled = True
    config.consolidation_min_facts = 3
    sources = [_fact("fact_0", "User works at Acme"), _fact("fact_1", "User is a backend engineer"), _fact("fact_2", "User uses Go at work")]
    raw_update = {
        "factsToConsolidate": [
            {
                "sourceIds": ["fact_0", "fact_1"],
                "consolidated": {"content": merged_content, "category": "context", "confidence": 0.9, **_GATE},
            }
        ]
    }
    updater = U.MemoryUpdater(config, None, None)
    normalized = U._normalize_memory_update_data(copy.deepcopy(raw_update))
    return updater._apply_updates(_memory(sources), normalized, "thread-1", metrics={})


def test_consolidation_keeps_sources_when_merged_content_is_an_upload_mention():
    result = _consolidate("User is a backend engineer at Acme (per uploaded resume document)")

    # The merged content describes an upload event, so the finalization scrub
    # would drop it. The merge must be skipped instead of consuming both sources
    # and leaving nothing in their place.
    assert [f["id"] for f in result["facts"]] == ["fact_0", "fact_1", "fact_2"]


def test_ordinary_consolidation_still_merges():
    result = _consolidate("User is a backend engineer at Acme")

    contents = [f["content"] for f in result["facts"]]
    assert "User is a backend engineer at Acme" in contents
    assert {f["id"] for f in result["facts"]}.isdisjoint({"fact_0", "fact_1"})

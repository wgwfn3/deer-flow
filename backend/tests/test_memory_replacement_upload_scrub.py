"""Regression: a paired replacement that the upload scrub drops must not delete its target."""

import copy

from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig
from deerflow.agents.memory.backends.deermem.deermem.core.updater import MemoryUpdater


def _gated(content: str) -> dict:
    return {"content": content, "scope": "user", "durability": "durable", "authority": "descriptive", "confidence": 0.9}


def _apply(current_memory: dict, update_data: dict) -> dict:
    updater = MemoryUpdater(DeerMemConfig(), None)
    return updater._apply_updates(copy.deepcopy(current_memory), update_data, user_id="test", thread_id="thread1")


def test_paired_removal_rejected_when_replacement_is_an_upload_mention():
    current_memory = {"facts": [{"id": "fact_a", "content": "User's resume lists Java as primary language"}]}
    update_data = {
        "factsToRemove": [{"id": "fact_a", "replacementFactIndex": 0, "scope": "user", "reason": "Corrected primary language"}],
        "newFacts": [_gated("User uploaded a resume file listing Go as primary language")],
    }

    result = _apply(current_memory, update_data)

    # The replacement describes an upload event, so the finalization scrub would
    # drop it. The paired removal must therefore be rejected instead of leaving
    # neither the old fact nor its replacement behind.
    assert [(f["id"], f["content"]) for f in result["facts"]] == [("fact_a", "User's resume lists Java as primary language")]


def test_paired_removal_still_succeeds_for_ordinary_replacement():
    current_memory = {"facts": [{"id": "fact_a", "content": "User's resume lists Java as primary language"}]}
    update_data = {
        "factsToRemove": [{"id": "fact_a", "replacementFactIndex": 0, "scope": "user", "reason": "Corrected primary language"}],
        "newFacts": [_gated("User's primary language is Go")],
    }

    result = _apply(current_memory, update_data)

    assert [f["content"] for f in result["facts"]] == ["User's primary language is Go"]

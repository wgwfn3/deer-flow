"""Regression test: paired replacement should not succeed when the replacement fact is also deleted in the same batch."""

import copy


def test_paired_removal_both_deleted_same_batch():
    """When both the old fact and its replacement are deleted in the same batch, the paired removal must be rejected."""
    from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig
    from deerflow.agents.memory.backends.deermem.deermem.core.updater import MemoryUpdater

    config = DeerMemConfig()
    updater = MemoryUpdater(config, None)

    # fact_a will be replaced by fact_b (already exists), and fact_b will also be deleted
    current_memory = {
        "facts": [
            {"id": "fact_a", "content": "User prefers tabs", "scope": "user"},
            {"id": "fact_b", "content": "User prefers spaces", "scope": "user"},
        ]
    }

    # replacementFactIndex: the index in newFacts that contains the replacement content.
    # Here we provide a newFact with the same content as fact_b. fact_a's replacement
    # points to this newFact, but fact_b is also being deleted unconditionally.
    update_data = {
        "factsToRemove": [
            {"id": "fact_a", "replacementFactIndex": 0, "scope": "user", "reason": "Replaced by updated preference"},
            {"id": "fact_b", "scope": "user", "reason": "Obsolete"},
        ],
        "newFacts": [{"content": "User prefers spaces", "scope": "user", "durability": "durable", "authority": "descriptive", "confidence": 0.8}],
    }

    result_memory = updater._apply_updates(copy.deepcopy(current_memory), update_data, user_id="test", thread_id="thread1")

    # fact_b is deleted unconditionally, so newFacts[0] is no longer a duplicate
    # and is appended. The replacement content therefore survives under a new ID,
    # which makes the paired removal of fact_a safe. Before the fix both facts were
    # deleted and the replacement content was lost entirely.
    facts = result_memory.get("facts", [])
    assert [f["content"] for f in facts] == ["User prefers spaces"]
    fact_ids = {f["id"] for f in facts}
    assert "fact_a" not in fact_ids
    assert "fact_b" not in fact_ids


def test_paired_removal_replacement_stays():
    """When the replacement fact is not deleted, the paired removal should succeed."""
    from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig
    from deerflow.agents.memory.backends.deermem.deermem.core.updater import MemoryUpdater

    config = DeerMemConfig()
    updater = MemoryUpdater(config, None)

    current_memory = {"facts": [{"id": "fact_a", "content": "User prefers tabs", "scope": "user"}, {"id": "fact_b", "content": "User prefers spaces", "scope": "user"}]}

    # Delete fact_a (paired with newFacts[0] as replacement), but do NOT delete fact_b
    update_data = {
        "factsToRemove": [
            {"id": "fact_a", "replacementFactIndex": 0, "scope": "user", "reason": "Replaced by updated preference"},
        ],
        "newFacts": [{"content": "User prefers spaces", "scope": "user", "durability": "durable", "authority": "descriptive", "confidence": 0.8}],
    }

    result_memory = updater._apply_updates(copy.deepcopy(current_memory), update_data, user_id="test", thread_id="thread1")

    # Expected: fact_a is removed, fact_b stays
    assert len(result_memory.get("facts", [])) == 1
    assert result_memory["facts"][0]["id"] == "fact_b"

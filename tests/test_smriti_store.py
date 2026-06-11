from pathlib import Path

import pytest

from smriti_mcp.store import MemoryStore


def test_create_memory_uses_title_filename_and_markdown_frontmatter(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    result = store.create_memory(
        {
            "title": "Agent Runtime Decision",
            "category": "Project Notes",
            "tags": ["runtime"],
        },
        "Use durable memory for decisions.",
    )

    assert result["id"] == "Project Notes/Agent Runtime Decision"
    assert (tmp_path / "Project Notes" / "Agent Runtime Decision.md").exists()
    markdown = store.get_memory(result["id"])
    assert "title: Agent Runtime Decision" in markdown
    assert "Use durable memory for decisions." in markdown


def test_create_memory_blocks_path_traversal(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    with pytest.raises(ValueError):
        store.create_memory(
            {"title": "Secret", "category": "notes"},
            "Body",
            id="../../secret",
        )


def test_search_memory_can_omit_full_content(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory(
        {"title": "Memory Search", "category": "notes", "tags": ["search"]},
        "Need relevance scoring for durable notes.",
    )

    results = store.search_memory("relevance", include_content=False)

    assert results[0]["id"] == "notes/Memory Search"
    assert "content" not in results[0]
    assert results[0]["snippets"]


def test_archive_and_delete_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    created = store.create_memory({"title": "Old Note", "category": "notes"}, "Body")

    store.archive_memory(created["id"])
    archived = store.list_memories(status="archived")
    assert [item["id"] for item in archived] == [created["id"]]

    store.delete_memory(created["id"])
    assert store.list_memories() == []


def test_build_and_load_memory_index(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory(
        {"title": "Alpha", "category": "notes", "short_description": "first"},
        "Body",
    )

    result = store.build_memory_index()

    assert result["indexed_notes"] == 1
    assert "# Memory Index" in store.load_memory_index()
    assert "[[Alpha]] - first" in store.load_memory_index()


def test_wikilinks_resolve_to_title_preserving_filenames(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    target = store.create_memory(
        {"title": "Content Intelligence", "category": "notes"},
        "Reusable content strategy memory.",
    )
    source = store.create_memory(
        {"title": "Agent Writing Workflow", "category": "notes"},
        "Use [[Content Intelligence]] when drafting posts.",
    )

    index = store._build_machine_index(include_content=False)

    assert target["id"] == "notes/Content Intelligence"
    assert (tmp_path / "notes" / "Content Intelligence.md").exists()
    assert index["links"][source["id"]] == [target["id"]]
    assert index["backlinks"][target["id"]] == [source["id"]]


def test_apply_wikilinks_uses_longest_match_and_word_boundaries(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory(
        {"title": "Durable Memory", "category": "notes", "aliases": ["durable"]},
        "Target.",
    )
    note = store.create_memory(
        {"title": "Writing Note", "category": "notes"},
        "Durable memory matters. Endurable systems are different. Able alone is not the same.",
    )

    stats = store.apply_wikilinks()
    markdown = store.get_memory(note["id"])

    assert stats["links_added"] == 1
    assert "[[Durable Memory|Durable memory]] matters." in markdown
    assert "Endurable systems" in markdown
    assert "Able alone" in markdown


def test_apply_wikilinks_normalizes_aliases_and_skips_protected_text(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory(
        {"title": "Content Intelligence", "category": "notes", "aliases": ["CI"]},
        "Target.",
    )
    note = store.create_memory(
        {"title": "Protected Note", "category": "notes"},
        (
            "Use [[CI]] in prose.\n"
            "Keep [CI](https://example.com) as a markdown link.\n"
            "Keep `CI` in code.\n"
        ),
    )

    stats = store.apply_wikilinks()
    markdown = store.get_memory(note["id"])

    assert stats["links_normalized"] == 1
    assert stats["links_added"] == 0
    assert "[[Content Intelligence|CI]] in prose" in markdown
    assert "[CI](https://example.com)" in markdown
    assert "`CI`" in markdown


def test_rebuild_memory_fixes_frontmatter_applies_wikilinks_and_indexes(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory(
        {"title": "Content Intelligence", "category": "notes"},
        "Target.",
    )
    raw = tmp_path / "notes" / "Needs Frontmatter.md"
    raw.write_text("Talk about Content Intelligence here.\n", encoding="utf-8")

    result = store.rebuild_memory()
    markdown = raw.read_text(encoding="utf-8")

    assert result["frontmatter"]["fixed"] == 1
    assert result["wikilinks"]["links_added"] == 1
    assert result["index"]["indexed_notes"] == 2
    assert "title: Needs Frontmatter" in markdown
    assert "[[Content Intelligence]] here" in markdown


def test_search_and_index_preserve_existing_obsidian_paths(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    clipping = tmp_path / "Clippings" / "The biggest 𝗔𝗴𝗲𝗻𝘁𝗶𝗰 AI decision isn't model selection.md"
    clipping.parent.mkdir()
    clipping.write_text(
        """---
title: "The biggest 𝗔𝗴𝗲𝗻𝘁𝗶𝗰 AI decision isn't model selection"
tags:
  - clippings
---

Agentic AI decisions depend on access, memory, and governance.
""",
        encoding="utf-8",
    )

    results = store.search_memory("governance", include_content=False)
    indexed = store.build_memory_index()
    loaded = store.load_memory_index()

    assert results[0]["id"] == "Clippings/The biggest 𝗔𝗴𝗲𝗻𝘁𝗶𝗰 AI decision isn't model selection"
    assert indexed["indexed_notes"] == 1
    assert "[[The biggest 𝗔𝗴𝗲𝗻𝘁𝗶𝗰 AI decision isn't model selection]]" in loaded


def test_human_memory_metadata_round_trips_and_filters(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    created = store.create_memory(
        {
            "title": "No LLM Dependency",
            "category": "preferences",
            "memory_type": "preference",
            "confidence": "high",
            "source_agent": "codex",
            "visibility": "shared",
            "salience": 0.9,
            "scope": {"project": "smriti-mcp"},
        },
        "The memory system should not depend on an LLM.",
    )

    results = store.search_memory(
        "dependency",
        filters={"memory_type": "preference", "scope": {"project": "smriti-mcp"}},
        include_content=False,
    )
    markdown = store.get_memory(created["id"])

    assert results[0]["id"] == created["id"]
    assert "memory_type: preference" in markdown
    assert "source_agent: codex" in markdown


def test_record_trace_and_suggest_consolidation(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    first = store.record_trace(
        "User prefers shared memory across Codex and Claude.",
        agent="codex",
        scope={"project": "smriti-mcp"},
        salience=0.8,
    )
    store.record_trace(
        "Shared memory should preserve provenance.",
        agent="codex",
        scope={"project": "smriti-mcp"},
    )

    suggestions = store.suggest_consolidation(scope={"project": "smriti-mcp"}, agent="codex")

    assert first["path"].startswith(".smriti/traces/")
    assert suggestions["trace_count"] == 2
    assert suggestions["groups"]


def test_remember_creates_trace_and_appends_to_strong_match(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    created = store.remember(
        "User prefers Smriti to stay dependency-light and markdown-first.",
        meta={
            "title": "Memory System Preference",
            "category": "preferences",
            "short_description": "Preference for a light markdown-first memory system.",
            "memory_type": "preference",
            "source_agent": "codex",
            "confidence": "high",
        },
    )
    appended = store.remember(
        "Memory System Preference: avoid mandatory vector databases.",
        title="Memory System Preference",
        category="preferences",
        memory_type="preference",
        source_agent="claude",
    )
    markdown = store.get_memory(created["id"])

    assert created["action"] == "create"
    assert appended["action"] == "append"
    assert appended["id"] == created["id"]
    assert "avoid mandatory vector databases" in markdown
    assert "short_description: Preference for a light markdown-first memory system." in markdown


def test_remember_honors_explicit_id_in_create_mode(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    created = store.remember(
        "Explicit IDs should be stable when agents provide them.",
        id="project/Explicit Remember ID",
        meta={
            "title": "Remember ID Behavior",
            "category": "project",
            "short_description": "Remember honors explicit create IDs.",
        },
        mode="create",
    )

    assert created["action"] == "create"
    assert created["id"] == "project/Explicit Remember ID"
    assert "Remember honors explicit create IDs." in store.get_memory(created["id"])


def test_remember_auto_mode_does_not_append_on_weak_metadata_match(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    first = store.remember(
        "Project Alpha uses deterministic markdown memory.",
        meta={"title": "Project Alpha", "category": "project", "memory_type": "semantic"},
    )
    second = store.remember(
        "Project Beta also mentions deterministic markdown memory.",
        meta={"title": "Project Beta", "category": "project", "memory_type": "semantic"},
    )

    assert first["action"] == "create"
    assert second["action"] == "create"
    assert second["id"] != first["id"]


def test_remember_explicit_append_requires_target_id(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    with pytest.raises(ValueError):
        store.remember("Append this somewhere.", mode="append")


def test_recall_context_follows_links_and_marks_accessed(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    target = store.create_memory(
        {
            "title": "Shared Memory Design",
            "category": "project",
            "memory_type": "semantic",
            "salience": 0.7,
        },
        "Shared memory uses traces, provenance, and consolidation.",
    )
    store.create_memory(
        {"title": "Agent Handoff", "category": "project", "memory_type": "episodic"},
        "Continue from [[Shared Memory Design]] when implementing recall.",
    )

    recalled = store.recall_context("handoff recall", follow_links=True, mark_accessed=True)
    target_markdown = store.get_memory(target["id"])

    assert recalled["count"] >= 2
    assert "Shared Memory Design" in recalled["context"]
    assert "access_count: 1" in target_markdown


def test_recall_context_can_include_exact_archived_body_match(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    archived = store.create_memory(
        {"title": "Archived Audit Note", "category": "audit", "status": "archived"},
        "The exact archived phrase cobalt-lantern recall sentinel should be found.",
    )
    store.create_memory(
        {"title": "Active Recall Note", "category": "audit", "salience": 1.0},
        "This active note discusses recall generally.",
    )

    excluded = store.recall_context(
        "cobalt-lantern recall sentinel",
        include_archived=False,
        mark_accessed=False,
    )
    included = store.recall_context(
        "cobalt-lantern recall sentinel",
        include_archived=True,
        mark_accessed=False,
    )

    assert archived["id"] not in {memory["id"] for memory in excluded["memories"]}
    assert included["memories"][0]["id"] == archived["id"]


def test_consolidate_and_supersede_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    trace = store.record_trace("Old approach was replaced.", agent="codex")
    old = store.create_memory({"title": "Old Approach", "category": "project"}, "Use the old approach.")
    new = store.consolidate_memory(
        "Use the new shared-memory approach.",
        {
            "title": "New Approach",
            "category": "project",
            "memory_type": "decision",
            "source_agent": "codex",
        },
        trace_ids=[trace["id"]],
    )

    result = store.supersede_memory(old["id"], new["id"], reason="New design replaces the old one.")
    old_markdown = store.get_memory(old["id"])
    new_markdown = store.get_memory(new["id"])

    assert result["status"] == "superseded"
    assert "status: superseded" in old_markdown
    assert f"superseded_by: {new['id']}" in old_markdown
    assert old["id"] in new_markdown


def test_review_memory_health_reports_unresolved_links_and_oversized_notes(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.create_memory({"title": "Health Note", "category": "notes"}, "See [[Missing Note]].")
    store.create_memory({"title": "Large Note", "category": "notes"}, "word " * 2501)

    health = store.review_memory_health()

    assert health["counts"]["unresolved_links"] == 1
    assert health["counts"]["oversized"] == 1

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from smriti_mcp.store import DEFAULT_MEMORY_ROOT, MemoryStore


class MemoryMetaInput(BaseModel):
    title: str = Field(
        description="Human-readable memory title, for example 'Preferred deployment workflow'."
    )
    category: str = Field(
        description="Broad namespace used to group memories, for example 'project', 'user', or 'architecture'."
    )
    short_description: str | None = Field(
        default=None,
        description="One-sentence summary shown in search results and generated indexes.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names or phrases that should resolve to this memory.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Specific labels for filtering and retrieval, such as 'decision' or 'preference'.",
    )
    author: str | None = Field(
        default=None,
        description="Optional author or agent identity that created or owns the memory.",
    )
    status: str = Field(
        default="active",
        description="Lifecycle state for the memory. Use 'active' for current notes and 'archived' for retained historical notes.",
    )
    memory_type: str | None = Field(
        default=None,
        description="Human-memory class such as episodic, semantic, procedural, preference, decision, handoff, or error_pattern.",
    )
    subtype: str | None = Field(
        default=None,
        description="Optional finer-grained memory subtype, for example handoff, project_context, or research_note.",
    )
    salience: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Optional recall strength from 0 to 1; frequently used memories can become more salient.",
    )
    confidence: str | None = Field(
        default=None,
        description="Optional confidence label such as high, medium, low, inferred, or user-stated.",
    )
    source_agent: str | None = Field(
        default=None,
        description="Agent identity that created or last consolidated this memory, for example codex or claude.",
    )
    visibility: str | None = Field(
        default=None,
        description="Optional sharing scope such as private, project, shared, or archived.",
    )
    scope: dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible structured scope, for example project, repository, client, or workspace identifiers.",
    )
    related: list[str] = Field(
        default_factory=list,
        description="Related memory ids used as explicit associations beyond wikilinks.",
    )
    supersedes: list[str] = Field(
        default_factory=list,
        description="Memory ids this memory replaces or makes less current.",
    )
    superseded_by: str | None = Field(
        default=None,
        description="Memory id that supersedes this memory when it is no longer current.",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Trace ids, memory ids, or external references that support this memory.",
    )
    observed_at: str | None = Field(default=None, description="ISO timestamp for when the fact or event was observed.")
    last_verified_at: str | None = Field(default=None, description="ISO timestamp for when this memory was last checked.")
    expires_at: str | None = Field(default=None, description="ISO timestamp after which this memory should be downranked.")


class RememberMetaInput(BaseModel):
    title: str | None = Field(
        default=None,
        description="Optional human-readable memory title; falls back to the first content line when omitted.",
    )
    category: str | None = Field(
        default=None,
        description="Optional broad namespace used to group memories; defaults to 'memory' when omitted.",
    )
    short_description: str | None = Field(
        default=None,
        description="Optional agent-supplied one-sentence summary; Smriti does not derive this from content.",
    )
    aliases: list[str] | None = Field(
        default=None,
        description="Optional alternative names or phrases that should resolve to this memory.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Optional labels for filtering and retrieval, such as 'decision' or 'preference'.",
    )
    author: str | None = Field(default=None, description="Optional author or owner.")
    status: str | None = Field(default=None, description="Optional lifecycle state for the memory.")
    memory_type: str | None = Field(default=None, description="Optional human-memory class.")
    subtype: str | None = Field(default=None, description="Optional finer-grained memory subtype.")
    salience: float | None = Field(default=None, ge=0, le=1, description="Optional recall strength from 0 to 1.")
    confidence: str | None = Field(default=None, description="Optional confidence label.")
    source_agent: str | None = Field(default=None, description="Optional agent identity writing the memory.")
    visibility: str | None = Field(default=None, description="Optional sharing scope.")
    scope: dict[str, Any] | None = Field(default=None, description="Optional structured scope object.")
    related: list[str] | None = Field(default=None, description="Optional related memory ids.")
    supersedes: list[str] | None = Field(default=None, description="Optional ids this memory replaces.")
    superseded_by: str | None = Field(default=None, description="Optional id that supersedes this memory.")
    sources: list[str] | None = Field(default=None, description="Optional provenance source references.")
    observed_at: str | None = Field(default=None, description="Optional observation timestamp.")
    last_verified_at: str | None = Field(default=None, description="Optional verification timestamp.")
    expires_at: str | None = Field(default=None, description="Optional expiry timestamp.")


class MemoryMetaPatch(BaseModel):
    title: str | None = Field(default=None, description="Replacement human-readable title.")
    category: str | None = Field(default=None, description="Replacement memory category.")
    short_description: str | None = Field(
        default=None,
        description="Replacement one-sentence summary for search results and indexes.",
    )
    aliases: list[str] | None = Field(
        default=None,
        description="Replacement list of aliases. Pass an empty list to clear aliases.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Replacement list of tags. Pass an empty list to clear tags.",
    )
    author: str | None = Field(default=None, description="Replacement author or owner.")
    status: str | None = Field(
        default=None,
        description="Replacement lifecycle state, commonly 'active' or 'archived'.",
    )
    memory_type: str | None = Field(default=None, description="Replacement human-memory class or semantic type.")
    subtype: str | None = Field(default=None, description="Replacement finer-grained memory subtype.")
    salience: float | None = Field(default=None, ge=0, le=1, description="Replacement recall strength from 0 to 1.")
    confidence: str | None = Field(default=None, description="Replacement confidence label.")
    source_agent: str | None = Field(default=None, description="Replacement source agent identity.")
    visibility: str | None = Field(default=None, description="Replacement sharing scope.")
    scope: dict[str, Any] | None = Field(default=None, description="Replacement structured scope object.")
    related: list[str] | None = Field(default=None, description="Replacement related memory ids.")
    supersedes: list[str] | None = Field(default=None, description="Replacement superseded memory ids.")
    superseded_by: str | None = Field(default=None, description="Replacement superseding memory id.")
    sources: list[str] | None = Field(default=None, description="Replacement provenance source references.")
    observed_at: str | None = Field(default=None, description="Replacement observation timestamp.")
    last_verified_at: str | None = Field(default=None, description="Replacement verification timestamp.")
    last_accessed_at: str | None = Field(default=None, description="Replacement access timestamp.")
    access_count: int | None = Field(default=None, ge=0, description="Replacement access count.")
    expires_at: str | None = Field(default=None, description="Replacement expiry timestamp.")


class SearchFilters(BaseModel):
    category: str | None = Field(default=None, description="Only return memories in this category.")
    author: str | None = Field(default=None, description="Only return memories by this author or owner.")
    status: str | None = Field(default=None, description="Only return memories with this lifecycle state.")
    tags: list[str] | None = Field(
        default=None,
        description="Only return memories containing all of these tags.",
    )
    memory_type: str | None = Field(default=None, description="Only return memories with this human-memory class.")
    subtype: str | None = Field(default=None, description="Only return memories with this subtype.")
    source_agent: str | None = Field(default=None, description="Only return memories written or consolidated by this agent.")
    visibility: str | None = Field(default=None, description="Only return memories with this visibility.")
    scope: dict[str, Any] | None = Field(default=None, description="Only return memories whose scope contains these exact key values.")


def create_server(memory_root: str | Path = DEFAULT_MEMORY_ROOT) -> FastMCP:
    store = MemoryStore(memory_root)
    server = FastMCP(
        "Smriti",
        instructions=(
            "Smriti gives agents durable markdown memory. Store facts, decisions, "
            "preferences, project context, and reusable notes that should survive "
            "beyond the current chat."
        ),
    )

    @server.tool(
        description=(
            "Create a durable markdown memory for facts, decisions, preferences, "
            "or project context that should survive beyond the current chat."
        )
    )
    def create_memory(
        meta: Annotated[
            MemoryMetaInput,
            Field(description="Structured metadata used for naming, grouping, filtering, and retrieval."),
        ],
        content: Annotated[
            str,
            Field(description="Markdown body of the memory. Use wikilinks like [[Other Memory]] to relate notes."),
        ],
        id: Annotated[
            str | None,
            Field(
                description=(
                    "Optional stable memory id such as 'project/Deploy Workflow'. "
                    "If omitted, Smriti creates one from category and title."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        return store.create_memory(
            meta=meta.model_dump(exclude_none=True),
            content=content,
            id=id,
        )

    @server.tool(description="Retrieve a memory note by id and return its complete markdown with YAML frontmatter.")
    def get_memory(
        id: Annotated[str, Field(description="Memory id returned by create_memory, for example 'project/Deploy Workflow'.")]
    ) -> str:
        return store.get_memory(id)

    @server.tool(
        description=(
            "Append new markdown to an existing memory while preserving its current "
            "content and updating the modified timestamp."
        )
    )
    def append_memory(
        id: Annotated[str, Field(description="Memory id to append to.")],
        content: Annotated[str, Field(description="Markdown content to append to the end of the memory.")],
    ) -> dict[str, Any]:
        return store.append_memory(id=id, content=content)

    @server.tool(
        description=(
            "Patch memory metadata and optionally replace the full markdown body. "
            "Use append_memory when adding incremental observations."
        )
    )
    def update_memory(
        id: Annotated[str, Field(description="Memory id to update.")],
        meta: Annotated[
            MemoryMetaPatch | None,
            Field(description="Partial metadata changes. Omitted fields keep their existing values."),
        ] = None,
        content: Annotated[
            str | None,
            Field(description="Replacement markdown body. Leave null to preserve existing content."),
        ] = None,
    ) -> dict[str, Any]:
        patch = meta.model_dump(exclude_none=True) if meta is not None else None
        return store.update_memory(id=id, meta=patch, content=content)

    @server.tool(description="Mark a memory as archived without deleting its markdown file.")
    def archive_memory(
        id: Annotated[str, Field(description="Memory id to mark as archived.")]
    ) -> dict[str, Any]:
        return store.archive_memory(id)

    @server.tool(description="Permanently delete a memory note by id.")
    def delete_memory(
        id: Annotated[str, Field(description="Memory id to permanently delete.")]
    ) -> dict[str, Any]:
        return store.delete_memory(id)

    @server.tool(
        description=(
            "List memory metadata for browsing or filtering without returning full "
            "note bodies. Use search_memory when you need relevance ranking."
        )
    )
    def list_memories(
        category: Annotated[str | None, Field(description="Optional category filter.")] = None,
        status: Annotated[str | None, Field(description="Optional lifecycle status filter, such as 'active' or 'archived'.")] = None,
        tags: Annotated[list[str] | None, Field(description="Optional tags that every returned memory must contain.")] = None,
        limit: Annotated[int, Field(description="Maximum number of memories to return.", ge=1, le=500)] = 50,
    ) -> dict[str, Any]:
        results = store.list_memories(category=category, status=status, tags=tags, limit=limit)
        return {"results": results, "count": len(results)}

    @server.tool(
        description=(
            "Search durable memories with relevance ranking over title, aliases, "
            "tags, path, description, and body terms."
        )
    )
    def search_memory(
        query: Annotated[str, Field(description="Search terms, phrase, or topic to retrieve relevant memories for.")],
        limit: Annotated[int, Field(description="Maximum number of ranked results to return.", ge=1, le=50)] = 10,
        filters: Annotated[
            SearchFilters | None,
            Field(description="Optional exact-match metadata filters applied before ranking."),
        ] = None,
        include_content: Annotated[
            bool,
            Field(description="When true, include full markdown content in each result; set false to save context."),
        ] = True,
    ) -> dict[str, Any]:
        results = store.search_memory(
            query=query,
            limit=limit,
            filters=filters.model_dump(exclude_none=True) if filters is not None else None,
            include_content=include_content,
        )
        return {"results": results, "count": len(results)}

    @server.tool(
        description=(
            "Record an append-only memory trace for shared agent experience. "
            "Traces are raw observations that agents can later consolidate into durable memories."
        )
    )
    def record_trace(
        content: Annotated[str, Field(description="Raw trace content or observation to preserve.")],
        type: Annotated[str, Field(description="Trace event type such as observed, recalled, remembered, or consolidated.")] = "observed",
        agent: Annotated[str | None, Field(description="Agent identity writing the trace, for example codex or claude.")] = None,
        scope: Annotated[dict[str, Any] | None, Field(description="Structured scope for the trace, such as project or repository.")] = None,
        memory_id: Annotated[str | None, Field(description="Related memory id, if this trace concerns an existing memory.")] = None,
        salience: Annotated[float | None, Field(description="Optional importance from 0 to 1.", ge=0, le=1)] = None,
        metadata: Annotated[dict[str, Any] | None, Field(description="Additional structured trace metadata.")] = None,
    ) -> dict[str, Any]:
        return store.record_trace(
            content=content,
            type=type,
            agent=agent,
            scope=scope,
            memory_id=memory_id,
            salience=salience,
            metadata=metadata,
        )

    @server.tool(
        description=(
            "Agent-friendly write API that records a trace and deterministically chooses "
            "whether to create a new memory or append to a strongly matching existing memory."
        )
    )
    def remember(
        content: Annotated[str, Field(description="Memory content the agent believes should persist.")],
        meta: Annotated[RememberMetaInput | None, Field(description="Optional metadata for precise memory creation; supplied fields are authoritative.")] = None,
        id: Annotated[str | None, Field(description="Target memory id required for explicit append or update modes.")] = None,
        title: Annotated[str | None, Field(description="Optional title for a new memory or matching existing memories.")] = None,
        category: Annotated[str, Field(description="Category to use when a new memory is created.")] = "memory",
        memory_type: Annotated[str | None, Field(description="Optional human-memory class such as episodic, semantic, procedural, or preference.")] = None,
        tags: Annotated[list[str] | None, Field(description="Optional tags for a new memory.")] = None,
        scope: Annotated[dict[str, Any] | None, Field(description="Optional structured scope used for matching and new metadata.")] = None,
        source_agent: Annotated[str | None, Field(description="Agent identity writing the memory.")] = None,
        confidence: Annotated[str | None, Field(description="Optional confidence label for a new memory.")] = None,
        salience: Annotated[float | None, Field(description="Optional importance from 0 to 1.", ge=0, le=1)] = None,
        mode: Annotated[str, Field(description="Write mode: auto, create, append, or update.")] = "auto",
    ) -> dict[str, Any]:
        return store.remember(
            content=content,
            meta=meta.model_dump(exclude_none=True) if meta is not None else None,
            id=id,
            title=title,
            category=category,
            memory_type=memory_type,
            tags=tags,
            scope=scope,
            source_agent=source_agent,
            confidence=confidence,
            salience=salience,
            mode=mode,
        )

    @server.tool(
        description=(
            "Return a compact, deterministic recall bundle for an agent task using lexical match, "
            "metadata, salience, access history, status, and optional wikilink traversal."
        )
    )
    def recall_context(
        query: Annotated[str, Field(description="Task, question, or situation to recall memory for.")],
        limit: Annotated[int, Field(description="Maximum number of memories to include.", ge=1, le=50)] = 10,
        filters: Annotated[SearchFilters | None, Field(description="Optional metadata filters for recall.")] = None,
        token_budget: Annotated[int, Field(description="Approximate maximum recall context token budget.", ge=100, le=20000)] = 3000,
        follow_links: Annotated[bool, Field(description="When true, include nearby wikilink and backlink memories.")] = True,
        include_archived: Annotated[bool, Field(description="When true, archived and superseded memories may be included.")] = False,
        mark_accessed: Annotated[bool, Field(description="When true, update access metadata for recalled memories.")] = True,
    ) -> dict[str, Any]:
        return store.recall_context(
            query=query,
            limit=limit,
            filters=filters.model_dump(exclude_none=True) if filters is not None else None,
            token_budget=token_budget,
            follow_links=follow_links,
            include_archived=include_archived,
            mark_accessed=mark_accessed,
        )

    @server.tool(description="Mark a memory as accessed, updating last_accessed_at, access_count, and salience.")
    def mark_accessed(
        id: Annotated[str, Field(description="Memory id to reinforce as recently accessed.")]
    ) -> dict[str, Any]:
        return store.mark_accessed(id)

    @server.tool(
        description=(
            "Suggest groups of raw traces that may deserve consolidation. "
            "Smriti does not summarize them; the agent decides the final memory content."
        )
    )
    def suggest_consolidation(
        scope: Annotated[dict[str, Any] | None, Field(description="Optional scope filter for trace grouping.")] = None,
        since: Annotated[str | None, Field(description="Optional ISO timestamp; ignore traces older than this.")] = None,
        agent: Annotated[str | None, Field(description="Optional agent identity to filter trace files.")] = None,
        limit: Annotated[int, Field(description="Maximum number of consolidation groups to return.", ge=1, le=50)] = 10,
    ) -> dict[str, Any]:
        return store.suggest_consolidation(scope=scope, since=since, agent=agent, limit=limit)

    @server.tool(
        description=(
            "Create, append, or update a durable memory from agent-supplied consolidated content. "
            "Use after reviewing traces; Smriti records provenance but does not summarize content itself."
        )
    )
    def consolidate_memory(
        content: Annotated[str, Field(description="Final markdown memory content supplied by the agent.")],
        meta: Annotated[MemoryMetaInput, Field(description="Metadata for the consolidated memory.")],
        id: Annotated[str | None, Field(description="Optional target memory id for create, append, or update.")] = None,
        trace_ids: Annotated[list[str] | None, Field(description="Trace ids that support this consolidation.")] = None,
        mode: Annotated[str, Field(description="Consolidation mode: create, append, or update.")] = "create",
    ) -> dict[str, Any]:
        return store.consolidate_memory(
            content=content,
            meta=meta.model_dump(exclude_none=True),
            id=id,
            trace_ids=trace_ids,
            mode=mode,
        )

    @server.tool(description="Mark one memory as superseded by another while preserving both markdown files.")
    def supersede_memory(
        old_id: Annotated[str, Field(description="Memory id that is no longer current.")],
        new_id: Annotated[str, Field(description="Memory id that replaces or supersedes the old memory.")],
        reason: Annotated[str | None, Field(description="Optional explanation appended to the superseded memory.")] = None,
    ) -> dict[str, Any]:
        return store.supersede_memory(old_id=old_id, new_id=new_id, reason=reason)

    @server.tool(
        description=(
            "Review memory store health by reporting duplicate titles, stale active memories, "
            "oversized notes, and unresolved wikilinks without modifying files."
        )
    )
    def review_memory_health() -> dict[str, Any]:
        return store.review_memory_health()

    @server.tool(description="Build or refresh the human-readable markdown memory index at index.md.")
    def build_memory_index(
        group_by_category: Annotated[
            bool,
            Field(description="When true, group index entries under category headings."),
        ] = True
    ) -> dict[str, Any]:
        return store.build_memory_index(group_by_category=group_by_category)

    @server.tool(
        description=(
            "Repair and rebuild the memory store: optionally fix frontmatter, "
            "apply or normalize wikilinks from memory titles and aliases using "
            "longest matches first, then rebuild index.md and index.yaml."
        )
    )
    def rebuild_memory(
        apply_wikilinks: Annotated[
            bool,
            Field(description="When true, add and normalize wikilinks based on memory titles and aliases."),
        ] = True,
        fix_frontmatter: Annotated[
            bool,
            Field(description="When true, repair missing or malformed required frontmatter fields before indexing."),
        ] = True,
        group_by_category: Annotated[
            bool,
            Field(description="When true, group generated index.md entries under category headings."),
        ] = True,
        dry_run: Annotated[
            bool,
            Field(description="When true, report proposed frontmatter and wikilink changes without writing files or indexes."),
        ] = False,
    ) -> dict[str, Any]:
        return store.rebuild_memory(
            apply_wikilinks=apply_wikilinks,
            fix_frontmatter=fix_frontmatter,
            group_by_category=group_by_category,
            dry_run=dry_run,
        )

    @server.tool(description="Load the generated markdown memory index, optionally refreshing it first.")
    def load_memory_index(
        refresh: Annotated[
            bool,
            Field(description="When true, rebuild index.md before returning it."),
        ] = False
    ) -> str:
        return store.load_memory_index(refresh=refresh)

    return server

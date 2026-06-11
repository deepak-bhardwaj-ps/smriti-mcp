from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import yaml

from smriti_mcp.frontmatter import MemoryDocument


WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
WIKILINK_FULL_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
CODE_SPAN_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]+\]\([^)]+\)")
DEFAULT_MEMORY_ROOT = Path.home() / ".smriti" / "memory"


@dataclass
class MemoryMeta:
    title: str
    category: str
    short_description: str | None = None
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str | None = None
    status: str = "active"
    memory_type: str | None = None
    subtype: str | None = None
    salience: float | None = None
    confidence: str | None = None
    source_agent: str | None = None
    visibility: str | None = None
    scope: dict[str, Any] = field(default_factory=dict)
    related: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None


def filename_segment(value: str) -> str:
    segment = re.sub(r"[\x00-\x1f:]", "", value).strip()
    segment = segment.replace("\\", "-")
    return segment or "memory"


def normalise_terms(text: str) -> list[str]:
    stopwords = {
        "about",
        "and",
        "for",
        "from",
        "have",
        "into",
        "that",
        "the",
        "this",
        "with",
        "your",
    }
    words = re.findall(r"\b[a-z0-9_\-]+\b", text.lower())
    return [word for word in words if len(word) > 2 and word not in stopwords]


def extract_wikilinks(content: str) -> list[str]:
    return sorted({match.strip() for match in WIKILINK_RE.findall(content)})


def _split_protected(text: str, pattern: re.Pattern[str]) -> list[tuple[str, bool]]:
    chunks: list[tuple[str, bool]] = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            chunks.append((text[cursor : match.start()], False))
        chunks.append((match.group(0), True))
        cursor = match.end()
    if cursor < len(text):
        chunks.append((text[cursor:], False))
    return chunks


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clamp_float(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float | None:
    if value is None or value == "":
        return None
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        raise TypeError("Expected a numeric value.")


class MemoryStore:
    def __init__(self, root: str | Path = DEFAULT_MEMORY_ROOT):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @property
    def index_path(self) -> Path:
        return self.root / "index.yaml"

    @property
    def trace_root(self) -> Path:
        return self.root / ".smriti" / "traces"

    def create_memory(
        self,
        meta: dict[str, Any],
        content: str,
        id: str | None = None,
    ) -> dict[str, Any]:
        clean_meta = self._clean_meta(meta)
        memory_id = self._clean_id(id) if id else self._default_id(clean_meta)
        path = self._path_for_id(memory_id, must_exist=False)
        with self._lock:
            if path.exists():
                raise FileExistsError(memory_id)
            now = _now()
            full_meta = {
                "id": memory_id,
                "created_at": now,
                "updated_at": now,
                **clean_meta,
            }
            self._atomic_save(MemoryDocument(meta=full_meta, body=content, path=path))
        return {"id": memory_id, "path": str(path)}

    def get_memory(self, id: str) -> str:
        return self._load(id).to_markdown()

    def append_memory(self, id: str, content: str) -> dict[str, Any]:
        with self._lock:
            doc = self._load(id)
            doc.body = f"{doc.body.rstrip()}\n\n{content.lstrip()}".rstrip() + "\n"
            doc.meta["updated_at"] = _now()
            self._atomic_save(doc)
        return {"id": id, "status": "updated"}

    def update_memory(
        self,
        id: str,
        meta: dict[str, Any] | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            doc = self._load(id)
            if meta:
                doc.meta.update(self._clean_partial_meta(meta))
            if content is not None:
                doc.body = content
            doc.meta["updated_at"] = _now()
            self._atomic_save(doc)
        return {"id": id, "status": "updated"}

    def archive_memory(self, id: str) -> dict[str, Any]:
        return self.update_memory(id, meta={"status": "archived"})

    def delete_memory(self, id: str) -> dict[str, Any]:
        path = self._path_for_id(id, must_exist=True)
        with self._lock:
            path.unlink()
        return {"id": id, "status": "deleted"}

    def list_memories(
        self,
        category: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        notes = []
        for note_id, note in self._scan_notes().items():
            if category and note.get("category") != category:
                continue
            if status and note.get("status") != status:
                continue
            if tags and not set(tags).issubset(set(note.get("tags") or [])):
                continue
            notes.append({"id": note_id, **note})
        notes.sort(key=lambda item: (item.get("category") or "", item.get("title") or ""))
        return notes[: max(1, min(limit, 500))]

    def search_memory(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        include_content: bool = True,
    ) -> list[dict[str, Any]]:
        query_terms = normalise_terms(query)
        index = self._build_machine_index(include_content=False)
        results = []
        for note_id, note in index["notes"].items():
            if not self._matches_filters(note, filters):
                continue
            doc = self._load(note_id)
            score = self._score_note(note_id, note, query_terms, index)
            score += self._exact_content_match_score(doc.to_markdown(), query)
            score += self._memory_affinity_score(note, filters or {})
            if score <= 0 and query_terms:
                continue
            result = {
                "id": note_id,
                "title": note["title"],
                "path": note["path"],
                "score": round(score, 3),
                "category": note.get("category"),
                "tags": note.get("tags", []),
                "memory_type": note.get("memory_type"),
                "status": note.get("status", "active"),
                "snippets": self._snippets(doc.to_markdown(), query_terms, note),
            }
            if include_content:
                result["content"] = doc.to_markdown()
            results.append(result)
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[: max(1, min(limit, 50))]

    def record_trace(
        self,
        content: str,
        type: str = "observed",
        agent: str | None = None,
        scope: dict[str, Any] | None = None,
        memory_id: str | None = None,
        salience: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now()
        trace_id = hashlib.sha256(
            f"{now}\n{agent or ''}\n{type}\n{content}".encode("utf-8")
        ).hexdigest()[:16]
        event = {
            "id": trace_id,
            "timestamp": now,
            "type": str(type or "observed").strip() or "observed",
            "agent": str(agent).strip() if agent else None,
            "memory_id": memory_id,
            "salience": _clamp_float(salience),
            "scope": scope or {},
            "content": content,
            "metadata": metadata or {},
        }
        path = self.trace_root / now[:10] / f"{event['agent'] or 'shared'}.ndjson"
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return {"id": trace_id, "path": str(path.relative_to(self.root)), "event": event}

    def remember(
        self,
        content: str,
        meta: dict[str, Any] | None = None,
        id: str | None = None,
        title: str | None = None,
        category: str = "memory",
        memory_type: str | None = None,
        tags: list[str] | None = None,
        scope: dict[str, Any] | None = None,
        source_agent: str | None = None,
        confidence: str | None = None,
        salience: float | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        clean_meta = self._remember_meta_from_inputs(
            content=content,
            meta=meta,
            title=title,
            category=category,
            memory_type=memory_type,
            tags=tags,
            scope=scope,
            source_agent=source_agent,
            confidence=confidence,
            salience=salience,
        )
        query = str(clean_meta.get("title") or title or content)
        filters: dict[str, Any] = {}
        if clean_meta.get("memory_type"):
            filters["memory_type"] = clean_meta["memory_type"]
        if clean_meta.get("scope"):
            filters["scope"] = clean_meta["scope"]
        candidates = self.search_memory(query, limit=5, filters=filters or None, include_content=False)
        best = candidates[0] if candidates else None
        action = "create"
        reason = "No sufficiently similar memory found."
        if mode in {"append", "update"} and not id:
            raise ValueError(f"{mode} mode requires a target memory id.")
        if mode not in {"auto", "create", "append", "update"}:
            raise ValueError("mode must be one of: auto, create, append, update.")
        if mode in {"append", "update"}:
            action = mode
        elif mode == "create":
            action = "create"
        elif best and self._remember_should_append(best, clean_meta):
            action = "append"
            reason = "Existing memory had a strong title or metadata match."

        target_id = id or (best["id"] if best else None)
        if action == "append" and target_id:
            result = self.append_memory(target_id, f"## Observation\n\n{content.rstrip()}\n")
            memory_id = result["id"]
        elif action == "update" and target_id:
            result = self.update_memory(target_id, content=content)
            memory_id = result["id"]
        else:
            result = self.create_memory(clean_meta, content, id=id)
            memory_id = result["id"]

        trace = self.record_trace(
            content=content,
            type="remembered",
            agent=clean_meta.get("source_agent"),
            scope=clean_meta.get("scope"),
            memory_id=memory_id,
            salience=clean_meta.get("salience"),
            metadata={
                "action": action,
                "candidate_ids": [item["id"] for item in candidates],
                "mode": mode,
            },
        )
        return {
            "action": action,
            "id": memory_id,
            "reason": reason,
            "matched_candidates": candidates,
            "trace_id": trace["id"],
        }

    def recall_context(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        token_budget: int = 3000,
        follow_links: bool = True,
        include_archived: bool = False,
        mark_accessed: bool = True,
    ) -> dict[str, Any]:
        effective_filters = dict(filters or {})
        if not include_archived and "status" not in effective_filters:
            effective_filters["exclude_statuses"] = ["archived", "superseded"]
        if include_archived:
            effective_filters["_include_archived"] = True

        index = self._build_machine_index(include_content=False)
        query_terms = normalise_terms(query)
        scored: dict[str, float] = {}
        for note_id, note in index["notes"].items():
            if not self._matches_filters(note, effective_filters):
                continue
            doc = self._load(note_id)
            score = self._score_note(note_id, note, query_terms, index)
            score += self._exact_content_match_score(doc.to_markdown(), query)
            score += self._memory_affinity_score(note, effective_filters)
            if score <= 0 and query_terms:
                continue
            scored[note_id] = score

        if follow_links:
            for note_id, score in list(scored.items()):
                neighbors = set(index.get("links", {}).get(note_id, []))
                neighbors.update(index.get("backlinks", {}).get(note_id, []))
                for neighbor in neighbors:
                    note = index["notes"].get(neighbor)
                    if not note or not self._matches_filters(note, effective_filters):
                        continue
                    scored[neighbor] = max(scored.get(neighbor, 0), score * 0.35)

        ranked_ids = [
            note_id
            for note_id, _ in sorted(scored.items(), key=lambda item: item[1], reverse=True)
        ][: max(1, min(limit, 50))]

        sections: dict[str, list[str]] = {}
        memories = []
        budget_words = max(80, int(token_budget * 0.75))
        used_words = 0
        for note_id in ranked_ids:
            doc = self._load(note_id)
            note = index["notes"][note_id]
            summary = self._recall_summary(note_id, note, doc, query_terms)
            words = len(summary.split())
            if used_words + words > budget_words and memories:
                break
            used_words += words
            memory_type = str(note.get("memory_type") or "memory")
            sections.setdefault(memory_type, []).append(summary)
            memories.append(
                {
                    "id": note_id,
                    "title": note.get("title"),
                    "score": round(scored[note_id], 3),
                    "memory_type": note.get("memory_type"),
                    "status": note.get("status", "active"),
                    "path": note.get("path"),
                }
            )
            if mark_accessed:
                self.mark_accessed(note_id)

        markdown_lines = [f"# Recall Context: {query}", ""]
        for section, entries in sections.items():
            markdown_lines.extend([f"## {section}", ""])
            markdown_lines.extend(entries)
            markdown_lines.append("")

        return {
            "query": query,
            "count": len(memories),
            "memories": memories,
            "context": "\n".join(markdown_lines).rstrip() + "\n",
            "token_budget": token_budget,
        }

    def mark_accessed(self, id: str) -> dict[str, Any]:
        with self._lock:
            doc = self._load(id)
            doc.meta["last_accessed_at"] = _now()
            try:
                doc.meta["access_count"] = int(doc.meta.get("access_count") or 0) + 1
            except (TypeError, ValueError):
                doc.meta["access_count"] = 1
            salience = _clamp_float(doc.meta.get("salience"))
            doc.meta["salience"] = min(1.0, (salience if salience is not None else 0.5) + 0.02)
            self._atomic_save(doc)
        return {"id": id, "status": "accessed", "access_count": doc.meta["access_count"]}

    def suggest_consolidation(
        self,
        scope: dict[str, Any] | None = None,
        since: str | None = None,
        agent: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        traces = self._load_traces(scope=scope, since=since, agent=agent)
        groups: dict[str, dict[str, Any]] = {}
        for trace in traces:
            terms = normalise_terms(str(trace.get("content") or ""))
            key = " ".join(terms[:3]) if terms else str(trace.get("type") or "trace")
            group = groups.setdefault(
                key,
                {"topic": key, "traces": [], "related_memories": [], "recommendation": "review"},
            )
            group["traces"].append(trace)

        for group in groups.values():
            query = " ".join(normalise_terms(" ".join(str(t.get("content") or "") for t in group["traces"]))[:8])
            if query:
                group["related_memories"] = self.search_memory(query, limit=5, include_content=False)
            if group["related_memories"]:
                group["recommendation"] = "update_existing"
            elif len(group["traces"]) > 1 or any((t.get("salience") or 0) >= 0.7 for t in group["traces"]):
                group["recommendation"] = "create_memory"

        ordered = sorted(
            groups.values(),
            key=lambda item: (len(item["traces"]), max((t.get("salience") or 0) for t in item["traces"])),
            reverse=True,
        )
        return {"groups": ordered[: max(1, min(limit, 50))], "trace_count": len(traces)}

    def consolidate_memory(
        self,
        content: str,
        meta: dict[str, Any],
        id: str | None = None,
        trace_ids: list[str] | None = None,
        mode: str = "create",
    ) -> dict[str, Any]:
        clean_meta = dict(meta)
        if trace_ids:
            clean_meta["sources"] = [f"trace:{trace_id}" for trace_id in trace_ids]
        if mode == "append":
            if not id:
                raise ValueError("Append consolidation requires an existing memory id.")
            result = self.append_memory(id, content)
        elif mode == "update":
            if not id:
                raise ValueError("Update consolidation requires an existing memory id.")
            result = self.update_memory(id, meta=clean_meta, content=content)
        else:
            result = self.create_memory(clean_meta, content, id=id)
        self.record_trace(
            content=f"Consolidated traces into {result['id']}.",
            type="consolidated",
            agent=clean_meta.get("source_agent"),
            memory_id=result["id"],
            metadata={"trace_ids": trace_ids or [], "mode": mode},
        )
        return result

    def supersede_memory(self, old_id: str, new_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            old_doc = self._load(old_id)
            new_doc = self._load(new_id)
            old_doc.meta["status"] = "superseded"
            old_doc.meta["superseded_by"] = new_id
            old_doc.meta["updated_at"] = _now()
            supersedes = list(new_doc.meta.get("supersedes") or [])
            if old_id not in supersedes:
                supersedes.append(old_id)
            new_doc.meta["supersedes"] = supersedes
            new_doc.meta["updated_at"] = _now()
            if reason:
                old_doc.body = f"{old_doc.body.rstrip()}\n\n## Superseded\n\n{reason.strip()}\n"
            self._atomic_save(old_doc)
            self._atomic_save(new_doc)
        return {"old_id": old_id, "new_id": new_id, "status": "superseded"}

    def review_memory_health(self) -> dict[str, Any]:
        index = self._build_machine_index(include_content=False)
        notes = index["notes"]
        duplicates = []
        stale = []
        oversized = []
        unresolved_links = []
        now = datetime.now(timezone.utc)
        seen_titles: dict[str, str] = {}
        for note_id, note in notes.items():
            title_key = str(note.get("title") or "").strip().lower()
            if title_key in seen_titles:
                duplicates.append({"ids": [seen_titles[title_key], note_id], "reason": "same title"})
            elif title_key:
                seen_titles[title_key] = note_id

            updated = _parse_datetime(note.get("updated_at"))
            accessed = _parse_datetime(note.get("last_accessed_at"))
            reference_time = accessed or updated
            if reference_time and (now - reference_time).days >= 180 and note.get("status", "active") == "active":
                stale.append({"id": note_id, "days_since_activity": (now - reference_time).days})

            if int(note.get("word_count") or 0) > 2500:
                oversized.append({"id": note_id, "word_count": note.get("word_count")})

            for target in note.get("wikilinks") or []:
                target_id = index["aliases"].get(str(target).lower(), target)
                if target_id not in notes:
                    unresolved_links.append({"id": note_id, "target": target})

        return {
            "duplicates": duplicates,
            "stale": stale,
            "oversized": oversized,
            "unresolved_links": unresolved_links,
            "counts": {
                "notes": len(notes),
                "duplicates": len(duplicates),
                "stale": len(stale),
                "oversized": len(oversized),
                "unresolved_links": len(unresolved_links),
            },
        }

    def build_memory_index(self, group_by_category: bool = True) -> dict[str, Any]:
        entries = self.list_memories(limit=10000)
        lines = ["# Memory Index", ""]
        if group_by_category:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for entry in entries:
                grouped.setdefault(entry.get("category") or "uncategorized", []).append(entry)
            for category in sorted(grouped):
                lines.extend([f"## {category}", ""])
                for entry in grouped[category]:
                    lines.append(self._index_line(entry))
                lines.append("")
        else:
            for entry in entries:
                lines.append(self._index_line(entry))
        index_md_path = self.root / "index.md"
        index_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self._write_machine_index()
        return {"indexed_notes": len(entries), "index_path": str(index_md_path)}

    def load_memory_index(self, refresh: bool = False) -> str:
        path = self.root / "index.md"
        if refresh or not path.exists():
            self.build_memory_index()
        return path.read_text(encoding="utf-8")

    def apply_wikilinks(self, dry_run: bool = False) -> dict[str, Any]:
        candidates_by_note = self._wikilink_candidates_by_note()
        stats: dict[str, Any] = {
            "files_scanned": 0,
            "files_modified": 0,
            "links_added": 0,
            "links_normalized": 0,
            "dry_run": dry_run,
            "details": [],
        }

        for note_id in self._scan_notes():
            doc = self._load(note_id)
            candidates = candidates_by_note.get(note_id, [])
            stats["files_scanned"] += 1
            new_body, link_stats = self._apply_wikilinks_to_body(doc.body, candidates)
            if new_body == doc.body:
                continue

            stats["files_modified"] += 1
            stats["links_added"] += link_stats["links_added"]
            stats["links_normalized"] += link_stats["links_normalized"]
            stats["details"].append(
                {
                    "id": note_id,
                    "links_added": link_stats["links_added"],
                    "links_normalized": link_stats["links_normalized"],
                }
            )
            if not dry_run:
                doc.body = new_body
                doc.meta["updated_at"] = _now()
                self._atomic_save(doc)

        return stats

    def rebuild_memory(
        self,
        apply_wikilinks: bool = True,
        fix_frontmatter: bool = True,
        group_by_category: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dry_run": dry_run,
            "frontmatter": None,
            "wikilinks": None,
            "index": None,
        }
        if fix_frontmatter:
            from smriti_mcp.fix_frontmatter import scan_vault

            result["frontmatter"] = scan_vault(self.root, dry_run=dry_run)
        if apply_wikilinks:
            result["wikilinks"] = self.apply_wikilinks(dry_run=dry_run)
        if not dry_run:
            result["index"] = self.build_memory_index(group_by_category=group_by_category)
        return result

    def _scan_notes(self) -> dict[str, dict[str, Any]]:
        notes = {}
        for file_path in sorted(self.root.rglob("*.md")):
            if file_path.name.startswith(".") or file_path.name == "index.md":
                continue
            if ".smriti" in file_path.relative_to(self.root).parts:
                continue
            try:
                doc = MemoryDocument.load(file_path)
            except Exception:
                continue
            note_id = str(file_path.relative_to(self.root)).removesuffix(".md")
            title = doc.meta.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            notes[note_id] = self._summary_for_doc(note_id, file_path, doc)
        return notes

    def _summary_for_doc(
        self, note_id: str, file_path: Path, doc: MemoryDocument
    ) -> dict[str, Any]:
        return {
            "title": doc.meta.get("title"),
            "path": str(file_path.relative_to(self.root)),
            "short_description": doc.meta.get("short_description"),
            "aliases": doc.meta.get("aliases") or [],
            "tags": doc.meta.get("tags") or [],
            "category": doc.meta.get("category"),
            "author": doc.meta.get("author"),
            "status": doc.meta.get("status", "active"),
            "memory_type": doc.meta.get("memory_type"),
            "subtype": doc.meta.get("subtype"),
            "salience": doc.meta.get("salience"),
            "confidence": doc.meta.get("confidence"),
            "source_agent": doc.meta.get("source_agent"),
            "visibility": doc.meta.get("visibility"),
            "scope": doc.meta.get("scope") or {},
            "related": doc.meta.get("related") or [],
            "supersedes": doc.meta.get("supersedes") or [],
            "superseded_by": doc.meta.get("superseded_by"),
            "sources": doc.meta.get("sources") or [],
            "observed_at": doc.meta.get("observed_at"),
            "last_verified_at": doc.meta.get("last_verified_at"),
            "last_accessed_at": doc.meta.get("last_accessed_at"),
            "access_count": doc.meta.get("access_count") or 0,
            "expires_at": doc.meta.get("expires_at"),
            "created_at": doc.meta.get("created_at"),
            "updated_at": doc.meta.get("updated_at"),
            "word_count": len(doc.body.split()),
        }

    def _build_machine_index(self, include_content: bool) -> dict[str, Any]:
        index: dict[str, Any] = {
            "version": 1,
            "updated_at": _now(),
            "notes": {},
            "aliases": {},
            "links": {},
            "backlinks": {},
            "terms": {},
        }
        docs: dict[str, MemoryDocument] = {}
        for note_id in self._scan_notes():
            doc = self._load(note_id)
            docs[note_id] = doc
            path = self._path_for_id(note_id, must_exist=True)
            note = self._summary_for_doc(note_id, path, doc)
            note["wikilinks"] = extract_wikilinks(doc.body)
            if include_content:
                note["content"] = doc.body
            index["aliases"][str(note["title"]).lower()] = note_id
            for alias in note["aliases"]:
                index["aliases"][str(alias).lower()] = note_id
            index["notes"][note_id] = note

        for note_id, doc in docs.items():
            note = index["notes"][note_id]
            for target in note["wikilinks"]:
                target_id = index["aliases"].get(target.lower(), target)
                index["links"].setdefault(note_id, []).append(target_id)
                index["backlinks"].setdefault(target_id, []).append(note_id)
            for term in normalise_terms(doc.body):
                index["terms"].setdefault(term, {}).setdefault(note_id, 0)
                index["terms"][term][note_id] += 1
        return index

    def _wikilink_candidates_by_note(self) -> dict[str, list[dict[str, str]]]:
        phrase_targets: dict[str, dict[str, str] | None] = {}
        for note_id, note in self._scan_notes().items():
            title = str(note.get("title") or "").strip()
            if title:
                self._add_wikilink_candidate(phrase_targets, title, title, note_id)
            for alias in note.get("aliases") or []:
                alias_text = str(alias).strip()
                if alias_text:
                    self._add_wikilink_candidate(phrase_targets, alias_text, title, note_id)

        usable = [
            {"phrase": phrase, **target}
            for phrase, target in phrase_targets.items()
            if target is not None
        ]
        usable.sort(key=lambda item: len(item["phrase"]), reverse=True)

        candidates: dict[str, list[dict[str, str]]] = {}
        for note_id in self._scan_notes():
            candidates[note_id] = [item for item in usable if item["id"] != note_id]
        return candidates

    def _add_wikilink_candidate(
        self,
        phrase_targets: dict[str, dict[str, str] | None],
        phrase: str,
        title: str,
        note_id: str,
    ) -> None:
        key = phrase.lower()
        candidate = {"title": title, "id": note_id}
        existing = phrase_targets.get(key)
        if existing is None and key in phrase_targets:
            return
        if existing and existing != candidate:
            phrase_targets[key] = None
            return
        phrase_targets[key] = candidate

    def _apply_wikilinks_to_body(
        self,
        body: str,
        candidates: list[dict[str, str]],
    ) -> tuple[str, dict[str, int]]:
        stats = {"links_added": 0, "links_normalized": 0}
        chunks = []
        for chunk, protected in _split_protected(body, CODE_SPAN_RE):
            if protected:
                chunks.append(chunk)
                continue
            normalized = self._normalize_existing_wikilinks(chunk, candidates, stats)
            chunks.append(self._add_missing_wikilinks(normalized, candidates, stats))
        return "".join(chunks), stats

    def _normalize_existing_wikilinks(
        self,
        text: str,
        candidates: list[dict[str, str]],
        stats: dict[str, int],
    ) -> str:
        by_phrase = {item["phrase"].lower(): item["title"] for item in candidates}

        def replace(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else None
            canonical = by_phrase.get(target.lower())
            if not canonical or canonical == target:
                return match.group(0)
            stats["links_normalized"] += 1
            display = label or target
            if display == canonical:
                return f"[[{canonical}]]"
            return f"[[{canonical}|{display}]]"

        return WIKILINK_FULL_RE.sub(replace, text)

    def _add_missing_wikilinks(
        self,
        text: str,
        candidates: list[dict[str, str]],
        stats: dict[str, int],
    ) -> str:
        if not candidates:
            return text
        pattern = re.compile(
            "|".join(re.escape(item["phrase"]) for item in candidates),
            re.IGNORECASE,
        )
        by_phrase = {item["phrase"].lower(): item["title"] for item in candidates}
        chunks = []
        for chunk, protected in _split_protected(text, re.compile(f"{WIKILINK_FULL_RE.pattern}|{MARKDOWN_LINK_RE.pattern}")):
            if protected:
                chunks.append(chunk)
                continue

            def replace(match: re.Match[str]) -> str:
                before = chunk[match.start() - 1] if match.start() > 0 else ""
                after = chunk[match.end()] if match.end() < len(chunk) else ""
                if before and (before.isalnum() or before == "_"):
                    return match.group(0)
                if after and (after.isalnum() or after == "_"):
                    return match.group(0)
                display = match.group(0)
                title = by_phrase[display.lower()]
                stats["links_added"] += 1
                if display == title:
                    return f"[[{title}]]"
                return f"[[{title}|{display}]]"

            chunks.append(pattern.sub(replace, chunk))
        return "".join(chunks)

    def _write_machine_index(self) -> None:
        index = self._build_machine_index(include_content=False)
        self.index_path.write_text(
            yaml.safe_dump(index, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _score_note(
        self,
        note_id: str,
        note: dict[str, Any],
        query_terms: list[str],
        index: dict[str, Any],
    ) -> float:
        if not query_terms:
            return 1.0
        score = 0.0
        title = str(note.get("title") or "").lower()
        description = str(note.get("short_description") or "").lower()
        path = str(note.get("path") or "").lower()
        aliases = [str(alias).lower() for alias in note.get("aliases") or []]
        tags = [str(tag).lower() for tag in note.get("tags") or []]
        for term in query_terms:
            if term in title:
                score += 8.0
            if any(term in alias for alias in aliases):
                score += 6.0
            if term in tags:
                score += 5.0
            if term in path or term in note_id.lower():
                score += 4.0
            if term in description:
                score += 3.0
            freq = index.get("terms", {}).get(term, {}).get(note_id, 0)
            if freq:
                score += math.log(freq + 1)
        backlinks = len(index.get("backlinks", {}).get(note_id, []))
        score += min(backlinks * 0.25, 5.0)
        return score

    def _memory_affinity_score(self, note: dict[str, Any], filters: dict[str, Any]) -> float:
        score = 0.0
        salience = _clamp_float(note.get("salience"))
        if salience is not None:
            score += salience * 2.0
        try:
            score += min(int(note.get("access_count") or 0) * 0.05, 2.0)
        except (TypeError, ValueError):
            pass
        confidence = str(note.get("confidence") or "").lower()
        score += {"high": 1.0, "medium": 0.5, "low": -0.5}.get(confidence, 0.0)
        status = str(note.get("status") or "active").lower()
        apply_status_penalty = not (filters.get("status") or filters.get("_include_archived"))
        if apply_status_penalty:
            if status == "archived":
                score -= 3.0
            elif status == "superseded":
                score -= 5.0
        expires_at = _parse_datetime(note.get("expires_at"))
        if expires_at and expires_at < datetime.now(timezone.utc):
            score -= 4.0
        if filters.get("memory_type") and note.get("memory_type") == filters["memory_type"]:
            score += 2.0
        if filters.get("source_agent") and note.get("source_agent") == filters["source_agent"]:
            score += 1.0
        return score

    def _exact_content_match_score(self, markdown: str, query: str) -> float:
        collapsed_query = re.sub(r"\s+", " ", query).strip().lower()
        if len(collapsed_query) < 8:
            return 0.0
        collapsed_markdown = re.sub(r"\s+", " ", markdown).lower()
        return 20.0 if collapsed_query in collapsed_markdown else 0.0

    def _snippets(
        self,
        markdown: str,
        query_terms: list[str],
        note: dict[str, Any],
    ) -> list[str]:
        snippets = []
        lines = markdown.splitlines()
        for index, line in enumerate(lines):
            lower_line = line.lower()
            if any(term in lower_line for term in query_terms):
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                snippets.append("... " + " ".join(l.strip() for l in lines[start:end]) + " ...")
                if len(snippets) == 2:
                    break
        return snippets or [note.get("short_description") or note.get("title") or ""]

    def _matches_filters(
        self, note: dict[str, Any], filters: dict[str, Any] | None
    ) -> bool:
        if not filters:
            return True
        if filters.get("category") and note.get("category") != filters["category"]:
            return False
        if filters.get("author") and note.get("author") != filters["author"]:
            return False
        if filters.get("status") and note.get("status") != filters["status"]:
            return False
        if filters.get("tags") and not set(filters["tags"]).issubset(set(note.get("tags") or [])):
            return False
        if filters.get("memory_type") and note.get("memory_type") != filters["memory_type"]:
            return False
        if filters.get("subtype") and note.get("subtype") != filters["subtype"]:
            return False
        if filters.get("source_agent") and note.get("source_agent") != filters["source_agent"]:
            return False
        if filters.get("visibility") and note.get("visibility") != filters["visibility"]:
            return False
        if filters.get("exclude_statuses") and note.get("status", "active") in filters["exclude_statuses"]:
            return False
        if filters.get("scope"):
            note_scope = note.get("scope") or {}
            for key, value in filters["scope"].items():
                if note_scope.get(key) != value:
                    return False
        return True

    def _remember_meta_from_inputs(
        self,
        content: str,
        meta: dict[str, Any] | None,
        title: str | None,
        category: str,
        memory_type: str | None,
        tags: list[str] | None,
        scope: dict[str, Any] | None,
        source_agent: str | None,
        confidence: str | None,
        salience: float | None,
    ) -> dict[str, Any]:
        clean_meta = dict(meta or {})
        defaults = {
            "title": title,
            "category": category,
            "tags": tags,
            "memory_type": memory_type,
            "scope": scope,
            "source_agent": source_agent,
            "confidence": confidence,
            "salience": salience,
        }
        for key, value in defaults.items():
            if key not in clean_meta or clean_meta[key] is None:
                clean_meta[key] = value
        if not clean_meta.get("title"):
            clean_meta["title"] = self._title_from_content(content)
        if not clean_meta.get("category"):
            clean_meta["category"] = "memory"
        if clean_meta.get("tags") is None:
            clean_meta["tags"] = []
        if clean_meta.get("scope") is None:
            clean_meta["scope"] = {}
        return self._clean_meta(clean_meta)

    def _remember_should_append(self, candidate: dict[str, Any], meta: dict[str, Any]) -> bool:
        if candidate.get("score", 0) < 6:
            return False
        candidate_title = str(candidate.get("title") or "").strip().lower()
        title = str(meta.get("title") or "").strip().lower()
        if title and title == candidate_title:
            return True
        return False

    def _recall_summary(
        self,
        note_id: str,
        note: dict[str, Any],
        doc: MemoryDocument,
        query_terms: list[str],
    ) -> str:
        title = note.get("title") or note_id
        desc = note.get("short_description")
        snippets = self._snippets(doc.body, query_terms, note)
        lines = [f"- [[{title}]] (`{note_id}`)"]
        if desc:
            lines.append(f"  Summary: {desc}")
        if note.get("confidence") or note.get("source_agent") or note.get("status"):
            parts = [
                f"status={note.get('status', 'active')}",
                f"confidence={note.get('confidence')}" if note.get("confidence") else "",
                f"source={note.get('source_agent')}" if note.get("source_agent") else "",
            ]
            lines.append("  " + ", ".join(part for part in parts if part))
        for snippet in snippets[:2]:
            lines.append(f"  {snippet}")
        return "\n".join(lines)

    def _load_traces(
        self,
        scope: dict[str, Any] | None = None,
        since: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        since_dt = _parse_datetime(since) if since else None
        traces = []
        if not self.trace_root.exists():
            return traces
        for path in sorted(self.trace_root.rglob("*.ndjson")):
            if agent and path.stem != agent:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = _parse_datetime(event.get("timestamp"))
                if since_dt and timestamp and timestamp < since_dt:
                    continue
                if scope:
                    event_scope = event.get("scope") or {}
                    if any(event_scope.get(key) != value for key, value in scope.items()):
                        continue
                traces.append(event)
        return traces

    def _title_from_content(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip(" #\t")
            if stripped:
                return stripped[:80]
        return "Memory"

    def _short_description_from_content(self, content: str) -> str:
        collapsed = re.sub(r"\s+", " ", content).strip()
        return collapsed[:160] if collapsed else "Durable memory."

    def _load(self, id: str) -> MemoryDocument:
        return MemoryDocument.load(self._path_for_id(id, must_exist=True))

    def _default_id(self, meta: dict[str, Any]) -> str:
        return self._clean_id(f"{meta['category']}/{meta['title']}")

    def _path_for_id(self, id: str, must_exist: bool) -> Path:
        if must_exist:
            raw_id = id.strip() if isinstance(id, str) else ""
            raw_path = (self.root / f"{raw_id}.md").resolve()
            if not self._is_relative_to(raw_path, self.root):
                raise ValueError(f"Memory id escapes root: {id}")
            if raw_path.exists():
                return raw_path

        clean_id = self._clean_id(id)
        path = (self.root / f"{clean_id}.md").resolve()
        if not self._is_relative_to(path, self.root):
            raise ValueError(f"Memory id escapes root: {id}")
        if must_exist and not path.exists():
            raise FileNotFoundError(id)
        return path

    def _clean_id(self, id: str) -> str:
        if not isinstance(id, str) or not id.strip():
            raise ValueError("Memory id must be a non-empty string.")
        raw_parts = [part.strip() for part in id.strip().split("/") if part.strip()]
        if not raw_parts or any(part in {".", ".."} for part in raw_parts):
            raise ValueError(f"Invalid memory id: {id}")
        parts = [filename_segment(part) for part in raw_parts]
        return "/".join(parts)

    def _clean_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(meta, dict):
            raise TypeError("Memory metadata must be an object.")
        title = str(meta.get("title") or "").strip()
        category = str(meta.get("category") or "").strip()
        if not title:
            raise ValueError("Memory metadata requires title.")
        if not category:
            raise ValueError("Memory metadata requires category.")
        clean = self._clean_partial_meta(meta)
        clean["title"] = title
        clean["category"] = category
        clean.setdefault("aliases", [])
        clean.setdefault("tags", [])
        clean.setdefault("status", "active")
        return clean

    def _clean_partial_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "title",
            "short_description",
            "aliases",
            "tags",
            "category",
            "author",
            "status",
            "memory_type",
            "subtype",
            "salience",
            "confidence",
            "source_agent",
            "visibility",
            "scope",
            "related",
            "supersedes",
            "superseded_by",
            "sources",
            "observed_at",
            "last_verified_at",
            "last_accessed_at",
            "access_count",
            "expires_at",
        }
        clean = {key: value for key, value in meta.items() if key in allowed}
        for list_key in ("aliases", "tags", "related", "supersedes", "sources"):
            if list_key in clean:
                value = clean[list_key]
                if value is None:
                    clean[list_key] = []
                elif not isinstance(value, list):
                    raise TypeError(f"Memory metadata field {list_key} must be a list.")
                else:
                    clean[list_key] = [str(item).strip() for item in value if str(item).strip()]
        for str_key in (
            "title",
            "category",
            "author",
            "status",
            "short_description",
            "memory_type",
            "subtype",
            "confidence",
            "source_agent",
            "visibility",
            "superseded_by",
            "observed_at",
            "last_verified_at",
            "last_accessed_at",
            "expires_at",
        ):
            if str_key in clean and clean[str_key] is not None:
                clean[str_key] = str(clean[str_key]).strip()
        if "scope" in clean:
            if clean["scope"] is None:
                clean["scope"] = {}
            if not isinstance(clean["scope"], dict):
                raise TypeError("Memory metadata field scope must be an object.")
        if "salience" in clean:
            clean["salience"] = _clamp_float(clean["salience"])
        if "access_count" in clean and clean["access_count"] is not None:
            try:
                clean["access_count"] = max(0, int(clean["access_count"]))
            except (TypeError, ValueError):
                raise TypeError("Memory metadata field access_count must be an integer.")
        return clean

    def _atomic_save(self, doc: MemoryDocument) -> None:
        if doc.path is None:
            raise ValueError("Cannot save memory without a path.")
        doc.path.parent.mkdir(parents=True, exist_ok=True)
        text = doc.to_markdown()
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=doc.path.parent,
            delete=False,
            prefix=f".{doc.path.name}.",
            suffix=".tmp",
        ) as handle:
            handle.write(text)
            tmp_name = handle.name
        os.replace(tmp_name, doc.path)

    def _index_line(self, entry: dict[str, Any]) -> str:
        desc = f" - {entry['short_description']}" if entry.get("short_description") else ""
        tags = f" **Tags:** {', '.join(entry['tags'])}" if entry.get("tags") else ""
        link = self._index_link(entry)
        return f"- {link}{desc}{tags}"

    def _index_link(self, entry: dict[str, Any]) -> str:
        title = str(entry.get("title") or entry["id"])
        target = str(entry.get("id") or title)
        filename = Path(str(entry.get("path") or f"{target}.md")).stem
        if "|" in title or "|" in target:
            href = str(entry.get("path") or f"{target}.md").replace(">", "%3E")
            return f"[{title}](<{href}>)"
        if filename == title:
            return f"[[{title}]]"
        if title == target:
            return f"[[{target}]]"
        return f"[[{target}|{title}]]"

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

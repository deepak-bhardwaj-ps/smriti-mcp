#!/usr/bin/env python3
"""
Scan and fix frontmatter in memory files.

This utility scans all .md files in a vault or memory root (except index.md)
and ensures they have proper YAML frontmatter with required metadata fields:
- title (required): Human-readable name
- category (required): Broad namespace (e.g., 'project', 'user', 'architecture')
- short_description (optional): One-sentence summary
- aliases (optional): Alternative names
- tags (optional): Specific labels
- author (optional): Author or owner
- status (optional): Lifecycle state ('active' or 'archived')
"""

import re
from pathlib import Path
from typing import Any

from smriti_mcp.frontmatter import parse_markdown, build_markdown


def extract_title_from_filename(path: Path) -> str:
    """Extract a reasonable title from filename."""
    name = path.stem
    # Remove date prefixes (e.g., "2026-06-05-" or similar)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    # Remove UUIDs at end (e.g., "-325c5707")
    name = re.sub(r"-[a-f0-9]{8}$", "", name)
    # Replace dashes and underscores with spaces
    name = re.sub(r"[-_]+", " ", name).strip()
    # Capitalize each word
    return " ".join(word.capitalize() for word in name.split())


def extract_title_from_content(content: str) -> str | None:
    """Extract title from first heading in content."""
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return None


def infer_category_from_path(path: Path) -> str:
    """Infer category from directory structure."""
    parts = path.parts
    # Look for common category directories
    if "kb" in parts:
        kb_index = parts.index("kb")
        if kb_index + 1 < len(parts):
            category = parts[kb_index + 1]
            # Clean up directory name
            return category.replace("-", " ").replace("_", " ").strip()
    
    # Check for specific patterns
    name = path.stem.lower()
    if "signal" in name or "2026-" in name and path.parent.name == "signals":
        return "signal"
    if "content-idea" in path.parent.name:
        return "content-ideas"
    if "draft" in path.parent.name or "content-draft" in path.parent.name:
        return "content-drafts"
    if "clipping" in path.parent.name:
        return "clippings"
    
    return path.parent.name or "general"


def extract_type_from_frontmatter(meta: dict[str, Any]) -> str | None:
    """Extract type field if it exists (for signal/content-ideas)."""
    return meta.get("type")


def infer_category_from_meta(meta: dict[str, Any], path: Path) -> str:
    """Use type field if present, otherwise infer from path."""
    type_field = extract_type_from_frontmatter(meta)
    if type_field:
        if type_field == "signal":
            return "signal"
        if type_field == "content-ideas":
            return "content-ideas"
        return type_field
    return infer_category_from_path(path)


def extract_date_from_frontmatter(meta: dict[str, Any]) -> str | None:
    """Extract date from frontmatter if present."""
    return meta.get("date") or meta.get("created_at")


def extract_tags_from_frontmatter(meta: dict[str, Any]) -> list[str]:
    """Extract existing tags."""
    tags = meta.get("tags")
    if isinstance(tags, list):
        return tags
    if isinstance(tags, str):
        return [tags]
    return []


def normalise_list_field(value: Any) -> list[str]:
    """Preserve scalar YAML values while repairing list-shaped metadata."""
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [text for item in values if (text := str(item).strip())]


def ensure_frontmatter(path: Path) -> tuple[bool, str]:
    """
    Check and fix frontmatter for a single file.
    
    Returns:
        (modified: bool, message: str)
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Error reading: {e}"
    
    meta, body = parse_markdown(content)
    original_meta = meta.copy()
    modified = False
    
    # Ensure title
    if "title" not in meta or not meta["title"]:
        title = extract_title_from_content(body) or extract_title_from_filename(path)
        meta["title"] = title
        modified = True
    elif not isinstance(meta["title"], str):
        meta["title"] = str(meta["title"])
        modified = True
    
    # Ensure category
    if "category" not in meta or not meta["category"]:
        category = infer_category_from_meta(original_meta, path)
        meta["category"] = category
        modified = True
    elif not isinstance(meta["category"], str):
        meta["category"] = str(meta["category"])
        modified = True
    
    # Ensure status (default to active)
    if "status" not in meta:
        meta["status"] = "active"
        modified = True

    # OKF compatibility fields
    if "type" not in meta or not meta["type"]:
        meta["type"] = meta["category"]
        modified = True
    if "description" not in meta or not meta["description"]:
        if "short_description" in meta and meta["short_description"]:
            meta["description"] = meta["short_description"]
            modified = True
        elif body.strip():
            first_line = body.strip().splitlines()[0].strip()
            meta["description"] = first_line[:160]
            modified = True
        else:
            meta["description"] = None
    if "short_description" not in meta or not meta["short_description"]:
        meta["short_description"] = meta.get("description")
        if meta["short_description"] is not None:
            modified = True
    if "resource" not in meta:
        meta["resource"] = None
    if "timestamp" not in meta or not meta["timestamp"]:
        meta["timestamp"] = meta.get("updated_at") or meta.get("created_at")
        if meta["timestamp"] is not None:
            modified = True
    
    # Ensure aliases is a list
    if "aliases" in meta and meta["aliases"] != normalise_list_field(meta["aliases"]):
        meta["aliases"] = normalise_list_field(meta["aliases"])
        modified = True
    elif "aliases" not in meta:
        meta["aliases"] = []
    
    # Ensure tags is a list
    if "tags" in meta and meta["tags"] != normalise_list_field(meta["tags"]):
        meta["tags"] = normalise_list_field(meta["tags"])
        modified = True
    elif "tags" not in meta:
        meta["tags"] = []
    
    if modified:
        try:
            new_content = build_markdown(meta, body)
            path.write_text(new_content, encoding="utf-8")
            return True, f"Fixed frontmatter: title='{meta['title']}', category='{meta['category']}'"
        except Exception as e:
            return False, f"Error writing: {e}"
    
    return False, "Already valid"


def scan_vault(vault_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """
    Scan and fix all memory files in vault.
    
    Args:
        vault_path: Path to vault root
        dry_run: If True, only report issues without fixing
    
    Returns:
        Summary dict with statistics
    """
    vault_path = Path(vault_path).expanduser().resolve()
    
    if not vault_path.exists():
        return {"error": f"Vault path not found: {vault_path}"}
    
    # Find all .md files except reserved files
    md_files = [
        f for f in vault_path.rglob("*.md") 
        if f.name not in {"index.md", "log.md"} and f.name != ".obsidian"
    ]
    
    # Filter out hidden directories
    md_files = [f for f in md_files if not any(p.startswith(".") for p in f.parts)]
    
    stats = {
        "total_files": len(md_files),
        "fixed": 0,
        "already_valid": 0,
        "errors": 0,
        "details": [],
    }
    
    for md_file in sorted(md_files):
        relative_path = md_file.relative_to(vault_path)
        
        if dry_run:
            # Just check
            try:
                content = md_file.read_text(encoding="utf-8")
                meta, _ = parse_markdown(content)
                
                has_title = "title" in meta and meta["title"]
                has_category = "category" in meta and meta["category"]
                
                if not (has_title and has_category):
                    stats["details"].append({
                        "file": str(relative_path),
                        "status": "needs_fix",
                        "missing": [k for k in ["title", "category"] if k not in meta or not meta[k]],
                    })
                    stats["errors"] += 1
                else:
                    stats["details"].append({
                        "file": str(relative_path),
                        "status": "valid",
                    })
                    stats["already_valid"] += 1
            except Exception as e:
                stats["details"].append({
                    "file": str(relative_path),
                    "status": "error",
                    "error": str(e),
                })
                stats["errors"] += 1
        else:
            # Fix frontmatter
            modified, message = ensure_frontmatter(md_file)
            
            if modified:
                stats["fixed"] += 1
                status = "fixed"
            elif "Error" in message:
                stats["errors"] += 1
                status = "error"
            else:
                stats["already_valid"] += 1
                status = "valid"
            
            stats["details"].append({
                "file": str(relative_path),
                "status": status,
                "message": message,
            })
    
    return stats


def print_summary(stats: dict[str, Any]) -> None:
    """Print summary of scan/fix operation."""
    if "error" in stats:
        print(f"Error: {stats['error']}")
        return

    print("\nFrontmatter scan summary")
    print(f"{'=' * 60}")
    print(f"Total files:      {stats['total_files']}")
    print(f"Fixed:            {stats['fixed']}")
    print(f"Already valid:    {stats['already_valid']}")
    print(f"Errors:           {stats['errors']}")
    
    # Show errors if any
    errors = [d for d in stats["details"] if d["status"] == "error"]
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for detail in errors:
            print(f"  - {detail['file']}: {detail.get('error', 'Unknown error')}")
    
    # Show files that were fixed
    fixed = [d for d in stats["details"] if d["status"] == "fixed"]
    if fixed and len(fixed) <= 20:
        print(f"\nFixed ({len(fixed)}):")
        for detail in fixed:
            print(f"  - {detail['file']}: {detail['message']}")
    elif fixed:
        print(f"\nFixed {len(fixed)} files")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scan and fix frontmatter in markdown memory files"
    )
    parser.add_argument(
        "vault_path",
        help="Path to the markdown vault or memory root to scan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report issues without fixing",
    )
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault_path).expanduser()
    stats = scan_vault(vault_path, dry_run=args.dry_run)
    print_summary(stats)
    
    # Exit with non-zero if there were errors
    if stats.get("errors", 0) > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

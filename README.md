# Smriti MCP

> A portable memory server for AI agents, built for the Model Context Protocol (MCP).

[![PyPI version](https://img.shields.io/pypi/v/smriti-mcp.svg)](https://pypi.org/project/smriti-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()

Smriti stores durable memories as plain markdown files with YAML frontmatter. This keeps your data readable, git-friendly, and easy to inspect outside any single agent runtime.

## Features

- **Framework agnostic**: Works with any MCP-compatible agent (Claude, OpenAI, local models, etc.)
- **Durable & portable**: All memories stored as plain markdown files—no database required
- **Git-friendly**: Version control your memories alongside your code
- **Search & filter**: Full-text search, filtering by tags, categories, and status
- **Relationship tracking**: Use `[[wikilinks]]` to connect related memories
- **Memory index**: Auto-generate markdown indexes of your entire memory store
- **Archive & organize**: Hierarchical organization with categories and status tracking

## Installation

Smriti MCP is published on PyPI as [`smriti-mcp`](https://pypi.org/project/smriti-mcp/).

### With pip

Install into your current Python environment:

```bash
pip install smriti-mcp
```

Then verify the CLI is available:

```bash
smriti-mcp --help
```

### With uv

Install Smriti as a persistent command-line tool:

```bash
uv tool install smriti-mcp
```

Or run it directly without a separate install:

```bash
uvx smriti-mcp --help
```

### From source for development

```bash
git clone https://github.com/deepak-bhardwaj-ps/smriti-mcp.git
cd smriti-mcp
pip install -e .
```

## Quick Start

### 1. Run the server locally

```bash
smriti-mcp server --memory-root ~/.smriti/memory
```

By default, Smriti uses `~/.smriti/memory`. You can override it with:

```bash
export SMRITI_MEMORY_ROOT="$HOME/.smriti/memory"
smriti-mcp server
```

If you prefer `uvx`, run the server with:

```bash
uvx smriti-mcp server --memory-root ~/.smriti/memory
```

### 2. Configure in your MCP client

**Claude Desktop with pip or `uv tool install`** (`~/.config/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "smriti": {
      "type": "stdio",
      "command": "smriti-mcp",
      "args": ["server", "--memory-root", "~/.smriti/memory"]
    }
  }
}
```

**Claude Desktop with `uvx`**:

```json
{
  "mcpServers": {
    "smriti": {
      "type": "stdio",
      "command": "uvx",
      "args": ["smriti-mcp", "server", "--memory-root", "~/.smriti/memory"]
    }
  }
}
```

Then restart Claude Desktop and Smriti will be available as a tool.

## Available Tools

### Core Operations

| Tool | Description |
|------|-------------|
| `create_memory` | Create a new durable markdown memory with metadata |
| `get_memory` | Retrieve a memory by ID and return its full content |
| `append_memory` | Add content to the end of an existing memory |
| `update_memory` | Patch metadata or replace memory content |
| `delete_memory` | Permanently remove a memory |
| `remember` | Agent-friendly write API that records a trace and can create, append, or update |
| `consolidate_memory` | Create, append, or update a memory from reviewed trace content |

### Search & Browse

| Tool | Description |
|------|-------------|
| `search_memory` | Full-text search across title, tags, categories, and body. Returns ranked results |
| `list_memories` | Browse memory metadata without loading full content. Filter by status, category, tags |

### Organization

| Tool | Description |
|------|-------------|
| `archive_memory` | Mark a memory as archived (soft delete) |
| `build_memory_index` | Generate a markdown index of all memories for easy browsing |
| `rebuild_memory` | Fix frontmatter, apply/normalize wikilinks from titles and aliases, and rebuild indexes |
| `load_memory_index` | Load the generated index as markdown |

## Memory Format

Each memory is stored as a markdown file with YAML frontmatter:

```markdown
---
id: project/Example Architecture Decision
title: Example Architecture Decision
category: project
tags:
  - architecture
  - decision
status: active
short_description: Decided to use async/await pattern
created_at: "2026-06-05T10:30:00+10:00"
updated_at: "2026-06-05T10:30:00+10:00"
---

## Background

We needed to handle concurrent requests efficiently.

## Decision

Use async/await with asyncio for I/O-bound operations.

## Consequences

- Improved throughput for concurrent operations
- Need to manage event loop carefully in multi-threaded contexts

See also: [[Async Migration]], [[Performance Metrics]]
```

### Metadata Fields

- **id**: Unique identifier (auto-generated from category + title, or custom)
- **title**: Human-readable title
- **category**: Organizational category (becomes directory in file structure)
- **tags**: Array of searchable tags
- **status**: `active`, `archived`, or custom status
- **short_description**: Brief summary (used in indexes)
- **created_at**: ISO 8601 timestamp
- **updated_at**: ISO 8601 timestamp
- **memory_type**, **confidence**, **salience**, **scope**, **source_agent**: Optional agent memory metadata used for filtering and recall

## File Structure

```
~/.smriti/memory/
├── project/
│   ├── Example Architecture Decision.md
│   ├── Async Migration.md
│   └── Performance Metrics.md
├── research/
│   └── LLM Benchmarks.md
├── decisions/
│   └── Use Postgres.md
└── index.md
```

Smriti keeps default filenames aligned with memory titles so Obsidian-style wikilinks like
`[[API Rate Limiting Strategy]]` resolve to `API Rate Limiting Strategy.md`.

When you run `rebuild_memory`, Smriti can automatically add missing wikilinks and normalize
alias links. It matches longer titles and aliases first and only links whole phrases, so
`Durable Memory` is preferred over `durable`, and `able` is not linked inside `durable`.

## Usage Examples

### Create a memory

```python
from smriti_mcp.store import MemoryStore

store = MemoryStore("~/.smriti/memory")

result = store.create_memory(
    {
        "title": "API Rate Limiting Strategy",
        "category": "decisions",
        "tags": ["api", "performance"],
        "short_description": "Decided on sliding window rate limiting",
    },
    content="We chose sliding window over token bucket because...",
)

# Returns: {"id": "decisions/API Rate Limiting Strategy", ...}
```

### Remember with precise metadata

```python
result = store.remember(
    content="User prefers markdown-first durable memory with no mandatory vector database.",
    id="preferences/Markdown First Memory",
    meta={
        "title": "Markdown First Memory",
        "category": "preferences",
        "memory_type": "preference",
        "short_description": "Preference for markdown-first durable memory.",
        "source_agent": "codex",
        "confidence": "high",
    },
    mode="create",
)
```

`remember` treats supplied `meta` as authoritative. If `short_description` is omitted,
Smriti leaves it omitted instead of deriving a partial summary from the body. In `auto`
mode, Smriti only appends to an existing memory when there is a strong deterministic
match such as the same title; use `id` with `append` or `update` mode for explicit writes.

### Search memories

```python
results = store.search_memory(
    query="rate limiting",
    include_content=False,  # Just metadata
)

for result in results:
    print(f"{result['id']}: {result['title']}")
```

### List memories with filters

```python
active_decisions = store.list_memories(
    status="active",
    category="decisions",
)

for memory in active_decisions:
    print(f"{memory['title']} ({memory['status']})")
```

### Rebuild and repair memories

```python
result = store.rebuild_memory(
    fix_frontmatter=True,
    apply_wikilinks=True,
    group_by_category=True,
)

print(result["wikilinks"]["links_added"])
```

## Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run integration tests only
pytest tests/test_smriti_mcp_integration.py -v
```

All tests pass, including full MCP stdio round-trip integration tests.

## Architecture

- **MemoryStore**: Core storage engine with markdown file I/O
- **Server**: MCP server exposing tools to agents
- **CLI**: Command-line interface for running the stdio server
- **Frontmatter**: YAML metadata parsing and generation

The package has **zero external database dependencies** and works with Python 3.10+.

## Roadmap

- [ ] Web UI for browsing memories
- [ ] Multi-user support with authentication
- [ ] Memory graph visualization
- [ ] Sync to cloud storage (S3, GCS)
- [ ] Memory embeddings for semantic search

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Add tests for new functionality
4. Ensure all tests pass (`pytest tests/ -v`)
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Created by Deepak Bhardwaj.

## See Also

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Claude MCP Documentation](https://claude.ai/resources/docs)
- [Smriti concept](https://en.wikipedia.org/wiki/Smriti)

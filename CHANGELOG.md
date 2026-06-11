# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-06-11

### Added
- Added precise `remember(meta=...)` metadata support for agent memory writes.
- Added regression coverage for exact archived recall matches and conservative auto-append behavior.

### Changed
- `remember` now honors explicit create IDs and no longer derives partial `short_description` values from content when omitted.
- Tightened `remember` auto-append matching to avoid appending on weak lexical overlap.
- Improved search and recall scoring for exact content phrase matches.

## [0.1.1] - 2026-06-09

### Changed
- Updated README installation instructions for published PyPI package usage with pip and uv.

## [0.1.0] - 2026-06-08

### Added
- Initial release of Smriti MCP
- Core memory operations: create, read, update, delete, append
- Full-text search across memories with ranking
- Archive and soft-delete functionality
- Memory indexing with markdown output
- YAML frontmatter metadata support
- Category-based organization with hierarchical file structure
- Tag-based filtering and organization
- Search with optional content filtering
- List memories with status and category filters
- MCP stdio server implementation
- CLI interface for running the server
- Comprehensive test suite with integration tests
- Full tool parameter documentation

### Features
- Zero external database dependencies (file-based storage)
- Git-friendly plain markdown format
- Wikilink support for memory relationships
- Automatic ID generation from category and title, preserving title-style filenames for wikilinks
- Memory rebuild operation that can fix frontmatter, apply or normalize title/alias wikilinks, and rebuild indexes
- Path traversal attack prevention
- Full MCP server compliance for agent compatibility

[0.1.0]: https://github.com/deepak-bhardwaj-ps/smriti-mcp/releases/tag/v0.1.0
[0.1.1]: https://github.com/deepak-bhardwaj-ps/smriti-mcp/releases/tag/v0.1.1
[0.1.2]: https://github.com/deepak-bhardwaj-ps/smriti-mcp/releases/tag/v0.1.2

from pathlib import Path
from typing import Any

from smriti_mcp.server import create_server


def test_smriti_server_registers_expected_tools(tmp_path: Path) -> None:
    server = create_server(tmp_path)

    tools = server._tool_manager.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "create_memory",
        "get_memory",
        "append_memory",
        "update_memory",
        "archive_memory",
        "delete_memory",
        "list_memories",
        "search_memory",
        "record_trace",
        "remember",
        "recall_context",
        "mark_accessed",
        "suggest_consolidation",
        "consolidate_memory",
        "supersede_memory",
        "review_memory_health",
        "build_memory_index",
        "rebuild_memory",
        "load_memory_index",
    }.issubset(names)


def test_smriti_tool_and_parameter_descriptions_are_complete(tmp_path: Path) -> None:
    server = create_server(tmp_path)

    for tool in server._tool_manager.list_tools():
        assert tool.description and len(tool.description) > 20, tool.name
        assert_descriptions(tool.parameters, path=tool.name)


def assert_descriptions(schema: dict[str, Any], path: str) -> None:
    for name, prop in schema.get("properties", {}).items():
        assert prop.get("description"), f"{path}.{name} is missing description"

    for def_name, definition in schema.get("$defs", {}).items():
        for name, prop in definition.get("properties", {}).items():
            assert prop.get("description"), f"{path}.{def_name}.{name} is missing description"

from __future__ import annotations

import pytest

from core.agent_contracts import list_tool_contracts
from core.agent_runtime import RustAgentRuntime
from core.agent_tools import KnowledgeToolset
from tests.conftest import make_runtime


def test_python_contracts_match_knowledge_toolset_handlers(tmp_path):
    runtime = make_runtime(tmp_path)
    toolset = KnowledgeToolset(runtime)
    contract_names = {contract.name for contract in list_tool_contracts() if contract.name != "shell_exec"}
    handler_names = set(toolset.tool_names())

    assert handler_names == contract_names


def test_contracts_have_schema_and_category():
    contracts = list_tool_contracts()

    assert contracts
    for contract in contracts:
        assert contract.description
        assert contract.category in {"read_only", "mutating", "dangerous"}
        assert contract.input_schema["type"] == "object"
        assert "additionalProperties" in contract.input_schema


def test_rust_contracts_match_python_contracts():
    runtime = RustAgentRuntime()
    if not runtime.available:
        pytest.skip("Rust agent runtime not available")
    rust_tools = {tool["name"]: tool for tool in runtime.list_tools()["tools"]}
    python_tools = {contract.name: contract for contract in list_tool_contracts()}

    assert rust_tools.keys() == python_tools.keys()
    for name, contract in python_tools.items():
        assert rust_tools[name]["description"] == contract.description
        assert rust_tools[name]["category"] == contract.category
        assert rust_tools[name]["input_schema"] == contract.input_schema

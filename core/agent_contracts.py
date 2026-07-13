from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgentToolContract:
    name: str
    description: str
    category: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _object_schema(
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


_TOOL_CONTRACTS = [
    AgentToolContract(
        name="kb_get_stats",
        description="Return knowledge base indexing statistics.",
        category="read_only",
        input_schema=_object_schema(),
    ),
    AgentToolContract(
        name="kb_list_files",
        description="Browse workspace files known to Luna.",
        category="read_only",
        input_schema=_object_schema({
            "subdir": {"type": "string"},
            "search": {"type": "string"},
        }),
    ),
    AgentToolContract(
        name="kb_list_documents",
        description="List indexed knowledge base documents.",
        category="read_only",
        input_schema=_object_schema({
            "status": {"type": "string", "enum": ["all", "indexed", "failed"]},
        }),
    ),
    AgentToolContract(
        name="kb_search",
        description="Search indexed knowledge base chunks.",
        category="read_only",
        input_schema=_object_schema(
            {
                "query": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            required=["query"],
        ),
    ),
    AgentToolContract(
        name="kb_index_files",
        description="Index a list of workspace files.",
        category="mutating",
        input_schema=_object_schema(
            {
                "paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
            },
            required=["paths"],
        ),
    ),
    AgentToolContract(
        name="kb_rebuild_index",
        description="Rebuild the knowledge base index.",
        category="mutating",
        input_schema=_object_schema({"force": {"type": "boolean"}}),
    ),
    AgentToolContract(
        name="kb_delete_document",
        description="Delete a document from the knowledge base.",
        category="mutating",
        input_schema=_object_schema(
            {"document_id": {"type": "string", "minLength": 1}},
            required=["document_id"],
        ),
    ),
    AgentToolContract(
        name="kb_update_tags",
        description="Update tags for a knowledge base document.",
        category="mutating",
        input_schema=_object_schema(
            {
                "document_id": {"type": "string", "minLength": 1},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            required=["document_id", "tags"],
        ),
    ),
    AgentToolContract(
        name="kb_clear_index",
        description="Clear the knowledge base index.",
        category="dangerous",
        input_schema=_object_schema(),
    ),
    AgentToolContract(
        name="shell_exec",
        description="Execute arbitrary shell commands.",
        category="dangerous",
        input_schema=_object_schema(
            {"command": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
            required=["command"],
        ),
    ),
]


def list_tool_contracts() -> list[AgentToolContract]:
    return list(_TOOL_CONTRACTS)


def get_tool_contract(name: str) -> AgentToolContract | None:
    return next((contract for contract in _TOOL_CONTRACTS if contract.name == name), None)


def knowledge_tool_names() -> set[str]:
    return {contract.name for contract in _TOOL_CONTRACTS if contract.name != "shell_exec"}

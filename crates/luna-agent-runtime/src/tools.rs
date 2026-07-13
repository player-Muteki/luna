use crate::protocol::ToolCategory;
use serde::Serialize;
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct ToolSpec {
    pub name: &'static str,
    pub description: &'static str,
    pub category: ToolCategory,
    pub input_schema: Value,
}

#[derive(Debug, Clone, Default)]
pub struct ToolRegistry {
    tools: Vec<ToolSpec>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: vec![
                ToolSpec {
                    name: "kb_get_stats",
                    description: "Return knowledge base indexing statistics.",
                    category: ToolCategory::ReadOnly,
                    input_schema: object_schema(json!({}), None),
                },
                ToolSpec {
                    name: "kb_list_files",
                    description: "Browse workspace files known to Luna.",
                    category: ToolCategory::ReadOnly,
                    input_schema: object_schema(json!({
                        "subdir": {"type": "string"},
                        "search": {"type": "string"}
                    }), None),
                },
                ToolSpec {
                    name: "kb_list_documents",
                    description: "List indexed knowledge base documents.",
                    category: ToolCategory::ReadOnly,
                    input_schema: object_schema(json!({
                        "status": {"type": "string", "enum": ["all", "indexed", "failed"]}
                    }), None),
                },
                ToolSpec {
                    name: "kb_search",
                    description: "Search indexed knowledge base chunks.",
                    category: ToolCategory::ReadOnly,
                    input_schema: object_schema(json!({
                        "query": {"type": "string", "minLength": 1},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20}
                    }), Some(json!(["query"]))),
                },
                ToolSpec {
                    name: "kb_index_files",
                    description: "Index a list of workspace files.",
                    category: ToolCategory::Mutating,
                    input_schema: object_schema(json!({
                        "paths": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "minItems": 1
                        }
                    }), Some(json!(["paths"]))),
                },
                ToolSpec {
                    name: "kb_rebuild_index",
                    description: "Rebuild the knowledge base index.",
                    category: ToolCategory::Mutating,
                    input_schema: object_schema(json!({
                        "force": {"type": "boolean"}
                    }), None),
                },
                ToolSpec {
                    name: "kb_delete_document",
                    description: "Delete a document from the knowledge base.",
                    category: ToolCategory::Mutating,
                    input_schema: object_schema(json!({
                        "document_id": {"type": "string", "minLength": 1}
                    }), Some(json!(["document_id"]))),
                },
                ToolSpec {
                    name: "kb_update_tags",
                    description: "Update tags for a knowledge base document.",
                    category: ToolCategory::Mutating,
                    input_schema: object_schema(json!({
                        "document_id": {"type": "string", "minLength": 1},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }), Some(json!(["document_id", "tags"]))),
                },
                ToolSpec {
                    name: "kb_clear_index",
                    description: "Clear the knowledge base index.",
                    category: ToolCategory::Dangerous,
                    input_schema: object_schema(json!({}), None),
                },
                ToolSpec {
                    name: "shell_exec",
                    description: "Execute arbitrary shell commands.",
                    category: ToolCategory::Dangerous,
                    input_schema: object_schema(json!({
                        "command": {"type": "array", "items": {"type": "string"}, "minItems": 1}
                    }), Some(json!(["command"]))),
                },
            ],
        }
    }

    pub fn list(&self) -> &[ToolSpec] {
        &self.tools
    }

    pub fn get(&self, name: &str) -> Option<&ToolSpec> {
        self.tools.iter().find(|tool| tool.name == name)
    }
}

fn object_schema(properties: Value, required: Option<Value>) -> Value {
    let mut schema = json!({
        "type": "object",
        "properties": properties,
        "additionalProperties": false
    });
    if let Some(required) = required {
        schema["required"] = required;
    }
    schema
}

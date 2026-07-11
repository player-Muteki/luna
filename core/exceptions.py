"""Lore 自定义异常层次。

提供比内建 ValueError / RuntimeError 更精确的异常类型，
让调用方可以按错误类别做针对性处理（如 HTTP status code 映射）。
"""


class LoreError(Exception):
    """所有 Lore 异常的基类。"""


class ConfigError(LoreError):
    """配置相关错误（缺少 API Key、配置格式错误等）。"""


class RetrievalError(LoreError):
    """检索过程错误（向量库损坏、检索器未初始化等）。"""


class LLMError(LoreError):
    """LLM 调用错误（认证失败、模型不可用、额度不足等）。"""


class IngestError(LoreError):
    """文档索引错误（不支持的格式、解析失败、文件过大等）。"""


class LLMRetryError(LLMError):
    """LLM 重试耗尽——所有重试尝试均失败后抛出。"""

"""知识链路的 Adapter 装配与内部常量（Phase 2）。

可替换 Seam：FileStore / Parser / EmbeddingGateway / VectorStore。
本文件只做“按配置构造”，不承载业务规则；测试通过环境变量切换实现根目录。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from app.adapters.embedding.deterministic import DeterministicEmbedding, embed_text
from app.adapters.filestore.local import FileStore
from app.adapters.parser.document_parser import (
    SUPPORTED_TYPES,
    ChunkDraft,
    ParsedDocument,
    ParserError,
    build_chunks,
    detect_file_type,
    manifest_payload,
    parse_bytes,
    parser_config_digest,
)
from app.adapters.vector.local import LocalVectorStore
from app.config import get_settings

# ---- 任务 / 租约参数（后端详细设计 §10.2 BE 初始值）----
TASK_KIND_PERSIST: Final = "doc_persist"
TASK_KIND_PUBLISH: Final = "batch_publish"
TASK_KIND_DOC_CLEANUP: Final = "doc_cleanup"
TASK_KIND_BATCH_CLEANUP: Final = "batch_cleanup"

LEASE_SECONDS: Final = 30
HEARTBEAT_SECONDS: Final = 10
POLL_SECONDS: Final = 1.0
MAX_ATTEMPTS: Final = 5
BACKOFF_SECONDS: Final = (2, 4, 8, 16)

# 确定性失败码：不自动重试（SRS §8 异步任务错误码 + 解析错误）。
NON_RETRYABLE_CODES: Final = frozenset(
    {
        "NO_TEXT_EXTRACTED",
        "DOCUMENT_ENCRYPTED",
        "PARSE_FAILED",
        "UNSUPPORTED_FILE_TYPE",
        "DOCUMENT_EMPTY",
        "DOCUMENT_BUSY",
        "COMPENSATED",
    }
)


def file_store() -> FileStore:
    return FileStore()


def vector_store() -> LocalVectorStore:
    return LocalVectorStore()


def embedding() -> DeterministicEmbedding:
    return DeterministicEmbedding()


def corpus_vector_space() -> str:
    return os.environ.get("CCA_VECTOR_SPACE", "corpus_v1").strip() or "corpus_v1"


def retrieval_min_score() -> float:
    """检索候选的最低相关性分（FR-QA-003：依据不足要说没找到，而不是硬凑 top-k）。

    确定性 Hash Embedding 下这只是经验阈值；接真实 Embedding（TBD-04）后需要用
    评测集重新标定。设 0 / 负数表示不启用阈值。
    """
    raw = os.environ.get("CCA_RETRIEVAL_MIN_SCORE", "0.12").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.12
    return max(0.0, min(value, 1.0))


def upload_max_files() -> int:
    return get_settings().upload_max_files


def upload_max_file_bytes() -> int:
    return get_settings().upload_max_file_bytes


def upload_max_total_bytes() -> int:
    return get_settings().upload_max_total_bytes


def sealed_key(upload_id: str) -> str:
    return f"uploads/{upload_id}/sealed-original"


def document_key(document_id: str) -> str:
    return f"documents/{document_id}/original"


def attempt_file_prefix(task_id: str, fence: int, version_id: str) -> str:
    return f"attempts/{task_id}/{int(fence)}/{version_id}"


def attempt_text_key(task_id: str, fence: int, version_id: str) -> str:
    return f"{attempt_file_prefix(task_id, fence, version_id)}/extracted-text"


def attempt_manifest_key(task_id: str, fence: int, version_id: str) -> str:
    return f"{attempt_file_prefix(task_id, fence, version_id)}/chunk-manifest"


def attempt_namespace(
    task_id: str, fence: int, document_id: str, version_id: str, *, vector_space: str
) -> str:
    """向量命名空间必须由**版本行冻结的** vector_space 派生，不能再读环境变量。

    否则 ``CCA_VECTOR_SPACE`` 在"接受上传→staging"之间变化时，向量会写进新空间，
    而屏障/发布/检索都按版本行里的旧空间走 —— 结果是"已发布但永久检索不到"。
    """
    return f"{vector_space}/{document_id}/{version_id}/{task_id}/{int(fence)}"


def vector_space_prefix() -> str:
    return corpus_vector_space()


__all__ = [
    "BACKOFF_SECONDS",
    "ChunkDraft",
    "HEARTBEAT_SECONDS",
    "LEASE_SECONDS",
    "MAX_ATTEMPTS",
    "NON_RETRYABLE_CODES",
    "POLL_SECONDS",
    "ParsedDocument",
    "ParserError",
    "SUPPORTED_TYPES",
    "TASK_KIND_BATCH_CLEANUP",
    "TASK_KIND_DOC_CLEANUP",
    "TASK_KIND_PERSIST",
    "TASK_KIND_PUBLISH",
    "attempt_file_prefix",
    "attempt_manifest_key",
    "attempt_namespace",
    "attempt_text_key",
    "build_chunks",
    "corpus_vector_space",
    "detect_file_type",
    "document_key",
    "embed_text",
    "embedding",
    "file_store",
    "manifest_payload",
    "parse_bytes",
    "parser_config_digest",
    "retrieval_min_score",
    "sealed_key",
    "upload_max_file_bytes",
    "upload_max_files",
    "upload_max_total_bytes",
    "vector_space_prefix",
    "vector_store",
]

"""知识链路的 Adapter 装配与内部常量（Phase 2）。

可替换 Seam：FileStore / Parser / EmbeddingGateway / VectorStore。
本文件只做“按配置构造”，不承载业务规则；装配键走 ``app.config.env_*``
（进程环境变量优先，其次 ``backend/.env``，P1-5）；测试用环境变量切换实现根目录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from app.adapters.embedding.deterministic import embed_text
from app.adapters.embedding.registry import build_embedding
from app.adapters.judge import build_judge
from app.adapters.rerank import build_reranker
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
from app.config import (
    env_float,
    env_str,
    get_settings,
    rerank_band,
    rerank_fail_open,
    rerank_noise_floor,
    rerank_top_k,
)

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


def embedding():
    """按 ``CCA_EMBEDDING_PROVIDER`` 装配（默认确定性；真实语义向量走远端 Adapter）。"""
    return build_embedding()


def corpus_vector_space() -> str:
    return env_str("CCA_VECTOR_SPACE", "corpus_v1").strip() or "corpus_v1"


def retrieval_min_score() -> float:
    """检索候选的最低相关性分（FR-QA-003：依据不足要说没找到，而不是硬凑 top-k）。

    确定性 Hash Embedding 下**默认关闭（0）**：实测短查询（如"数组"）相似度可低于
    0.05，任何非零默认值都会误杀正常命中；接真实 Embedding（TBD-04）后须用评测集
    重新标定再打开。设 0 / 负数表示不启用阈值。
    """
    raw_score = env_float("CCA_RETRIEVAL_MIN_SCORE", 0.0)
    return max(0.0, min(raw_score, 1.0))


def retrieval_judge():
    """检索充分性判官（``CCA_RETRIEVAL_JUDGE=1`` 时装配，否则 None = 完全跳过这一层）。"""
    return build_judge()


def retrieval_reranker():
    """检索精排器（``CCA_RERANK_ENABLED=1`` 时装配，否则 None = 完全跳过这一层）。

    开启后检索侧的裁决顺序变为"精排分门 → 判官"，余弦硬门（``CCA_RETRIEVAL_MIN_SCORE``）
    不再生效：那道门会把余弦偏低但确实含答案的片段一起挡掉（main 集 B01 实测）。
    """
    return build_reranker()


def rerank_limit() -> int:
    """送入精排的候选上限（精排关闭时本函数不会被调用）。"""
    return rerank_top_k()


def rerank_thresholds() -> tuple[float, float]:
    """精排分数门 ``(LOW, HIGH)``：低于 LOW 判空，高于等于 HIGH 放行，中间问判官。"""
    return rerank_band()


def rerank_noise() -> float:
    """精排分的噪声底：低于它等于"模型完全没找到对应关系"，可直接判空。

    与 ``rerank_thresholds()[0]``（LOW）的分工见 ``app.config.rerank_noise_floor``。
    """
    return rerank_noise_floor()


def rerank_on_failure() -> bool:
    """精排不可用时是否退回余弦分数门（默认 1=退回）。"""
    return rerank_fail_open()


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
    "retrieval_judge",
    "retrieval_min_score",
    "retrieval_reranker",
    "rerank_limit",
    "rerank_noise",
    "rerank_on_failure",
    "rerank_thresholds",
    "sealed_key",
    "upload_max_file_bytes",
    "upload_max_files",
    "upload_max_total_bytes",
    "vector_space_prefix",
    "vector_store",
]

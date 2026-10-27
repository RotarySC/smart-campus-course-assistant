"""``search_course_docs`` 的服务侧实现（PHASE-03 A3）。

Phase 2 合并后：使用真实 ``knowledge.search``（``KnowledgeService`` 单例 + ``SearchQuery``），
**不改** knowledge 模块。knowledge 不可导入时**默认显式失败**（``RETRIEVAL_UNAVAILABLE``）；
只有显式设置 ``CCA_ASSISTANT_ALLOW_STUB_EVIDENCE=true``（演示/测试）或调用方主动
``set_stub_evidence()`` 注入时，才允许回落到确定性 stub —— 不允许悄悄伪造引用。

无论来源，都强制：单项文本 ≤20,000 码点；只返回已发布/有效片段的权威引用。
"""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.model.gateway import (
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
)
from app.config import get_settings
from app.modules.assistant.settings import get_assistant_settings
from app.shared.context import ActorContext
from app.shared.errors import ApiError

logger = logging.getLogger("cca.assistant.retrieval")

MAX_CHUNK_TEXT = 20_000


def _stub_evidence() -> EvidenceSet:
    reference = EvidenceReference(
        reference_id="cit_stub_syllabus_0001",
        document_id="doc_stub_syllabus",
        version_id="dvs_stub_syllabus_1",
        file_name="数据结构课程大纲.txt",
        location_label="第 2 页 · 课程要求",
        page_number=2,
    )
    chunk = EvidenceChunk(
        chunk_id="chk_stub_syllabus_0001",
        reference_id=reference.reference_id,
        document_id=reference.document_id,
        version_id=reference.version_id,
        text=(
            "课程要求：每周完成一次实验并提交实验报告；"
            "期末成绩由平时作业（40%）、实验（20%）与期末考试（40%）组成。"
        ),
        location_label=reference.location_label,
        page_number=reference.page_number,
    )
    return EvidenceSet(
        status="ok",
        corpus_empty=False,
        revision=0,
        chunks=(chunk,),
        references=(reference,),
    )


# 测试/演示可替换（例如验证 empty/failed 分支）；None 表示回到默认固定 stub。
_stub_override: EvidenceSet | None = None


def set_stub_evidence(evidence: EvidenceSet | None) -> None:
    global _stub_override
    _stub_override = evidence


def reset_stub_evidence() -> None:
    set_stub_evidence(None)


def _real_search():  # noqa: ANN202 - 冻结接口由 Phase 2 提供
    """返回 ``async (actor, query) -> EvidenceSet``；未合并时返回 None（走 stub）。"""
    try:  # Phase 2 已合并：knowledge 暴露 KnowledgeService 单例与 SearchQuery
        from app.modules.knowledge import SearchQuery, knowledge as knowledge_service

        method = getattr(knowledge_service, "search", None)
        if callable(method):
            async def _invoke(actor: ActorContext, query: str):
                return await method(actor, SearchQuery(query=query))

            return _invoke
    except Exception:  # noqa: BLE001 - 未合并/导入失败时按 stub 处理
        pass
    try:  # 兜底：兼容模块级 search 函数形态
        from app.modules.knowledge import service as knowledge_module

        function = getattr(knowledge_module, "search", None)
        if callable(function):
            return function
    except Exception:  # noqa: BLE001
        return None
    return None


async def search_course_docs(actor: ActorContext, query: str) -> EvidenceSet:
    """检索共享资料；返回权威 chunks/references（空结果与失败分开）。"""
    real = _real_search()
    if real is not None:
        try:
            raw = await real(actor, query)
            return _normalize(raw)
        except NotImplementedError:
            pass
        except ApiError:
            # 知识链路自己已给出稳定错误码（如参数/权限）：原样上抛。
            raise
        except Exception as exc:  # noqa: BLE001 - 检索依赖故障统一收敛
            logger.exception("knowledge.search failed; retrieval unavailable")
            # SRS §7.3：检索依赖故障必须映射为 503 RETRIEVAL_UNAVAILABLE，
            # 不能让适配器异常漏成 500 INTERNAL_ERROR（AT-30 实测缺口）。
            raise ApiError("RETRIEVAL_UNAVAILABLE") from exc
    logger.debug("knowledge module unavailable; checking stub fallback")
    if _stub_override is not None:
        # 显式注入（测试/受控演示）优先；调用方自己承担"这不是真实依据"的责任。
        return _stub_override
    if not get_settings().assistant_allow_stub_evidence:
        # INV-04/05：宁可显式失败，也不把固定假证据（伪造文件名/页码）当权威引用。
        raise ApiError("RETRIEVAL_UNAVAILABLE")
    logger.warning(
        "knowledge module unavailable; using deterministic stub evidence "
        "(CCA_ASSISTANT_ALLOW_STUB_EVIDENCE=true)"
    )
    return _stub_evidence()


def _get(raw: Any, key: str, default: Any = None) -> Any:
    if isinstance(raw, dict):
        return raw.get(key, default)
    return getattr(raw, key, default)


def _normalize(raw: Any) -> EvidenceSet:
    """把真实实现对返回的 EvidenceSet/dict/对象统一为 ``EvidenceSet``。"""
    if isinstance(raw, EvidenceSet):
        return raw
    max_len = get_assistant_settings().max_text_length
    chunks: list[EvidenceChunk] = []
    for item in _get(raw, "chunks", ()) or ():
        text = str(_get(item, "text", "") or "")[:max_len]
        if not text:
            continue
        chunks.append(
            EvidenceChunk(
                chunk_id=str(_get(item, "chunk_id", "") or ""),
                reference_id=str(_get(item, "reference_id", "") or ""),
                document_id=str(_get(item, "document_id", "") or ""),
                version_id=str(_get(item, "version_id", "") or ""),
                text=text,
                location_label=str(_get(item, "location_label", "") or ""),
                page_number=_get(item, "page_number"),
            )
        )
    references: list[EvidenceReference] = []
    for item in _get(raw, "references", ()) or ():
        references.append(
            EvidenceReference(
                reference_id=str(_get(item, "reference_id", "") or ""),
                document_id=str(_get(item, "document_id", "") or ""),
                version_id=str(_get(item, "version_id", "") or ""),
                file_name=str(_get(item, "file_name", "") or ""),
                location_label=str(_get(item, "location_label", "") or ""),
                page_number=_get(item, "page_number"),
            )
        )
    status = "ok" if _get(raw, "status", "") == "ok" and chunks else "empty"
    return EvidenceSet(
        status=status,  # type: ignore[arg-type]
        corpus_empty=bool(_get(raw, "corpus_empty", False)),
        revision=int(_get(raw, "revision", 0) or 0),
        chunks=tuple(chunks),
        references=tuple(references),
    )


__all__ = [
    "MAX_CHUNK_TEXT",
    "reset_stub_evidence",
    "search_course_docs",
    "set_stub_evidence",
]

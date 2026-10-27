"""检索兜底开关（P0-⑤）：真实检索不可用时必须显式失败，不得伪造引用。

背景：``retrieval.search_course_docs`` 在 knowledge 不可导入时曾无条件回落到固定
假证据（伪造文件名/页码），一旦被接进真实链路就会把假引用当权威依据（INV-04/05）。
现在默认抛 ``RETRIEVAL_UNAVAILABLE``，只有显式开关或显式注入才允许 stub。
"""

from __future__ import annotations

import pytest

from app.config import reset_settings_cache
from app.shared.errors import ApiError


def _actor():
    from app.shared.context import ActorContext

    return ActorContext(
        user_id="usr_retrieval_fallback",
        session_id="ses_retrieval_fallback",
        auth_version=1,
        role="student",
        trace_request_id="req_retrieval_fallback",
        account="fallback_probe",
        display_name="兜底探针",
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    from app.modules.assistant import retrieval

    monkeypatch.delenv("CCA_ASSISTANT_ALLOW_STUB_EVIDENCE", raising=False)
    retrieval.reset_stub_evidence()
    reset_settings_cache()
    yield
    retrieval.reset_stub_evidence()
    reset_settings_cache()


async def test_real_retriever_missing_fails_loudly(monkeypatch):
    """knowledge 不可用且开关未开 → RETRIEVAL_UNAVAILABLE，不返回假证据。"""
    from app.modules.assistant import retrieval

    monkeypatch.setattr(retrieval, "_real_search", lambda: None)

    with pytest.raises(ApiError) as exc:
        await retrieval.search_course_docs(_actor(), "期末成绩怎么算？")

    assert exc.value.code == "RETRIEVAL_UNAVAILABLE"
    assert exc.value.status_code == 503


async def test_stub_is_opt_in_via_env(monkeypatch):
    from app.modules.assistant import retrieval

    monkeypatch.setenv("CCA_ASSISTANT_ALLOW_STUB_EVIDENCE", "true")
    reset_settings_cache()
    monkeypatch.setattr(retrieval, "_real_search", lambda: None)

    evidence = await retrieval.search_course_docs(_actor(), "期末成绩怎么算？")

    assert evidence.chunks, "开关打开时才允许回落 stub 证据"
    assert all(chunk.reference_id for chunk in evidence.chunks)


async def test_explicit_injection_bypasses_logging_path(monkeypatch):
    """测试/演示主动注入的 EvidenceSet 优先于开关，且不改开关语义。"""
    from app.adapters.model.gateway import EvidenceChunk, EvidenceReference, EvidenceSet
    from app.modules.assistant import retrieval

    injected = EvidenceSet(
        status="ok",
        corpus_empty=False,
        revision=1,
        chunks=(
            EvidenceChunk(
                chunk_id="chk_injected_1",
                reference_id="cit_injected_1",
                document_id="doc_injected",
                version_id="dvs_injected",
                text="注入的证据片段",
                location_label="第 1 段",
            ),
        ),
        references=(
            EvidenceReference(
                reference_id="cit_injected_1",
                document_id="doc_injected",
                version_id="dvs_injected",
                file_name="注入.txt",
                location_label="第 1 段",
            ),
        ),
    )
    retrieval.set_stub_evidence(injected)
    monkeypatch.setattr(retrieval, "_real_search", lambda: None)

    assert await retrieval.search_course_docs(_actor(), "任意问题") is injected

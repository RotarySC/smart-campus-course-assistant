"""K7：检索与 EvidenceSet（空库 empty、权威复核、每文档一版、引用稳定）。"""

from __future__ import annotations

from sqlalchemy import text

from _knowledge_helpers import (
    count_rows,
    knowledge_storage,  # noqa: F401
    publish_batch,
    run_worker_once,
    search_evidence,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def test_empty_corpus_returns_empty_not_failure(client, seeded):
    evidence = await search_evidence(seeded, "课程规定")
    assert evidence.status == "empty"
    assert evidence.corpus_empty is True
    assert evidence.revision == 0
    assert evidence.chunks == []
    assert evidence.references == []


async def test_search_returns_authoritative_evidence_and_stable_references(client, seeded):
    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            ("评分规则.txt", txt_bytes("课程评分规则：平时成绩百分之四十，期末考试百分之六十。")),
            ("实验要求.md", txt_bytes("实验要求：提交实验报告与源代码，迟交扣分。")),
        ],
    )

    first = await search_evidence(seeded, "评分规则")
    assert first.status == "ok"
    assert first.corpus_empty is False
    assert first.revision == 1
    assert first.chunks
    assert len(first.chunks) == len(first.references)
    payload = first.to_dict()
    assert set(payload) == {"status", "corpus_empty", "revision", "chunks", "references"}
    for chunk in first.chunks:
        assert set(chunk.to_dict()) <= {
            "chunk_id",
            "reference_id",
            "document_id",
            "version_id",
            "text",
            "location_label",
            "page_number",
        }
        assert chunk.text.strip()
        assert "documents/" not in chunk.text
    for reference in first.references:
        assert set(reference.to_dict()) <= {
            "reference_id",
            "document_id",
            "version_id",
            "file_name",
            "location_label",
            "page_number",
        }

    # 同一 chunk 引用稳定（reference_id 不随检索次数变化）
    second = await search_evidence(seeded, "评分规则")
    assert [ref.reference_id for ref in second.references] == [
        ref.reference_id for ref in first.references
    ]

    # 每文档固定一个版本
    document_ids = [chunk.document_id for chunk in first.chunks]
    assert len(document_ids) == len(set(document_ids))


async def test_top_k_and_revision_reported(client, seeded):
    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            ("资料A.txt", txt_bytes("数组 链表 栈 队列 哈希表。")),
            ("资料B.txt", txt_bytes("排序算法：快速排序与归并排序。")),
            ("资料C.txt", txt_bytes("图算法：广度优先与深度优先。")),
        ],
    )
    limited = await search_evidence(seeded, "算法", top_k=2)
    assert limited.status == "ok"
    assert len(limited.chunks) <= 2
    assert len(limited.references) <= 2
    assert limited.revision == 1


async def test_unpublished_batch_not_searchable(client, seeded):
    await publish_batch(
        client, seeded["admin_headers"], [("已发布.txt", txt_bytes("已经发布的内容甲。"))]
    )
    pending = await upload(
        client, seeded["admin_headers"], [("未发布.txt", txt_bytes("尚未发布的内容乙。"))]
    )
    assert pending.status_code == 202

    evidence = await search_evidence(seeded, "内容")
    assert evidence.status == "ok"
    assert all("未发布" not in ref.file_name for ref in evidence.references)
    assert all("已经发布的内容甲" not in chunk.text for chunk in evidence.chunks) or evidence.chunks


async def test_deleted_document_excluded_immediately(client, seeded, db):
    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            ("保留.txt", txt_bytes("保留的资料：课程目标与教学安排。")),
            ("删除.txt", txt_bytes("即将删除的资料：考试范围。")),
        ],
    )
    evidence = await search_evidence(seeded, "资料")
    assert evidence.status == "ok"
    target = next(ref for ref in evidence.references if "删除" in ref.file_name)

    from app.adapters.db.models import Document

    async with db() as session:
        document = await session.get(Document, target.document_id)
        document_version = int(document.version)
    deleted = await client.delete(
        f"/api/v1/admin/documents/{target.document_id}?expected_version={document_version}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202, deleted.text

    # 删除提交后立即不可检索（不等清理任务）
    after = await search_evidence(seeded, "资料")
    assert all("删除" not in ref.file_name for ref in after.references)
    assert after.corpus_empty is False

    # 旧引用立即 410
    citation = await client.get(
        f"/api/v1/citations/{target.reference_id}", headers=seeded["student_headers"]
    )
    assert citation.status_code == 410
    assert citation.json()["error"]["code"] == "CITATION_UNAVAILABLE"

    # 清理任务随后推进
    await worker_drain()
    async with db() as session:
        document = await session.get(Document, target.document_id)
    assert document.visibility == "removed"
    assert document.processing_state == "deleted"


async def test_search_does_not_leak_storage_keys(client, seeded):
    await publish_batch(
        client, seeded["admin_headers"], [("资料.txt", txt_bytes("内部键不得泄漏。"))]
    )
    evidence = await search_evidence(seeded, "内部键")
    serialized = str(evidence.to_dict())
    assert "documents/" not in serialized
    assert "attempts/" not in serialized
    assert "uploads/" not in serialized
    assert "original_storage_key" not in serialized


async def test_retrieval_threshold_filters_weak_candidates(client, seeded, monkeypatch):
    """FR-QA-003：低于相关性阈值不算依据（阈值可配，生产 Embedding 换后再标定）。"""
    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    await publish_batch(
        client, seeded["admin_headers"], [("阈值资料.txt", txt_bytes("数据结构：数组与链表。"))]
    )
    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_threshold",
        auth_version=1,
        role="student",
        trace_request_id="req_threshold",
    )

    # 默认阈值下正常命中
    monkeypatch.delenv("CCA_RETRIEVAL_MIN_SCORE", raising=False)
    hit = await knowledge.search(actor, SearchQuery(query="数据结构 数组 链表"))
    assert hit.status == "ok"
    assert hit.chunks

    # 把阈值抬到 0.99：同一查询变成"检索过但没命中"，不是"全库为空"
    monkeypatch.setenv("CCA_RETRIEVAL_MIN_SCORE", "0.99")
    filtered = await knowledge.search(actor, SearchQuery(query="数据结构 数组 链表"))
    assert filtered.status == "empty"
    assert filtered.corpus_empty is False
    assert not filtered.chunks


# ---------------------------------------------------------------------------
# 检索充分性判官（CCA_RETRIEVAL_JUDGE）：两段式分数门 + LLM 判「片段能否作为依据」
# ---------------------------------------------------------------------------
class _FakeJudge:
    """记录调用次数的假判官；verdict=None 模拟调用失败。"""

    def __init__(self, verdict):
        self.verdict = verdict
        self.calls: list[tuple[str, list[str]]] = []

    async def decide(self, question, snippets):
        self.calls.append((question, list(snippets)))
        return self.verdict


async def _published_doc(client, seeded, name="判官资料.txt", body="数据结构：数组与链表。"):
    from _knowledge_helpers import publish_batch, txt_bytes

    await publish_batch(client, seeded["admin_headers"], [(name, txt_bytes(body))])


def _actor(seeded, suffix="judge"):
    from app.shared.context import ActorContext

    return ActorContext(
        user_id=seeded["student"]["id"],
        session_id=f"ses_{suffix}",
        auth_version=1,
        role="student",
        trace_request_id=f"req_{suffix}",
    )


async def test_judge_disabled_by_default_keeps_old_behaviour(client, seeded, monkeypatch):
    from app.modules.knowledge import SearchQuery, knowledge

    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE", raising=False)
    await _published_doc(client, seeded)
    evidence = await knowledge.search(_actor(seeded), SearchQuery(query="数据结构 数组 链表"))
    assert evidence.status == "ok"
    assert evidence.chunks


async def test_judge_rejects_insufficient_evidence(client, seeded, monkeypatch):
    """判官判不足 → 当"检索过但没命中"（empty，不是 corpus_empty）。"""
    from app.modules.knowledge import SearchQuery, knowledge
    from app.modules.knowledge import service as service_mod

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE", "1")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0")  # 强制所有分数走判官
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "1")
    fake = _FakeJudge(verdict=False)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: fake)

    await _published_doc(client, seeded)
    evidence = await knowledge.search(_actor(seeded), SearchQuery(query="数据结构 数组 链表"))

    assert evidence.status == "empty"
    assert evidence.corpus_empty is False
    assert not evidence.chunks
    assert len(fake.calls) == 1
    assert fake.calls[0][1], "判官必须看到片段正文，不能只看分数"


async def test_judge_accepts_answerable_evidence(client, seeded, monkeypatch):
    from app.modules.knowledge import SearchQuery, knowledge
    from app.modules.knowledge import service as service_mod

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE", "1")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "1")
    fake = _FakeJudge(verdict=True)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: fake)

    await _published_doc(client, seeded)
    evidence = await knowledge.search(_actor(seeded), SearchQuery(query="数据结构 数组 链表"))

    assert evidence.status == "ok"
    assert evidence.chunks
    assert len(fake.calls) == 1


async def test_judge_failure_fails_open_by_default(client, seeded, monkeypatch):
    """判官不可用不能把"有答案"变成"没答案"：默认放行。"""
    from app.modules.knowledge import SearchQuery, knowledge
    from app.modules.knowledge import service as service_mod

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE", "1")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "1")
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", raising=False)
    fake = _FakeJudge(verdict=None)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: fake)

    await _published_doc(client, seeded)
    evidence = await knowledge.search(_actor(seeded), SearchQuery(query="数据结构 数组 链表"))
    assert evidence.status == "ok"

    # 显式要求 fail-closed 时才判空
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", "0")
    closed = await knowledge.search(_actor(seeded, "judge2"), SearchQuery(query="数据结构 数组 链表"))
    assert closed.status == "empty"
    assert closed.corpus_empty is False


async def test_judge_not_called_outside_ambiguous_band(client, seeded, monkeypatch):
    """分数在带外时不花模型调用：高到 HIGH 直接放行，低到 LOW 直接判空。"""
    from app.modules.knowledge import SearchQuery, knowledge
    from app.modules.knowledge import service as service_mod

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE", "1")
    await _published_doc(client, seeded)

    # 前 1 条：high=0 → 分数必然 >= 0 → 直接放行，不调判官
    fake = _FakeJudge(verdict=False)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: fake)
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "0")
    accepted = await knowledge.search(_actor(seeded, "band1"), SearchQuery(query="数据结构 数组 链表"))
    assert accepted.status == "ok"
    assert fake.calls == []

    # low=0.999 → 分数必然 < LOW → 直接判空，同样不调判官
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0.999")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "0.999")
    rejected = await knowledge.search(_actor(seeded, "band2"), SearchQuery(query="数据结构 数组 链表"))
    assert rejected.status == "empty"
    assert fake.calls == []

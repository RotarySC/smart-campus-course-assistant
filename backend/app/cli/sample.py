"""样例数据：``python -m app.cli.sample``（开发/演示；可重复执行）。

在 ``seed --demo`` 之外补一批「打开就能演示 / 能测」的数据：

- 8 个学生账号 ``student_s01``…``student_s08``（口令 ``demo1234``，仅开发）；
- 8 门课程（CS101/MA201/CS201/CS301/CS302/MA202/PHY101/SE201）；
- 每个学生未来两周 6 节课程安排；
- 每个学生 2 份学习计划（含 ``write_operations`` 记录）；
- 5 份**已发布**课程资料（batch/document/version/chunk/citation_reference + 本地向量），
  助手提问可直接检索出真实引用。

判重：账号、课程码、课表（用户+课程+日期+时段）、计划操作键、文档固定 id。
可重复执行：已存在的行跳过；向量按命名空间幂等 upsert，重跑可修复向量缺失。

仅用于本机开发/演示库，**不要**在生产库执行。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import timedelta
from typing import Final

from sqlalchemy import select

from app.adapters.db.engine import dispose_engine
from app.adapters.db.models import (
    Chunk,
    CitationReference,
    CorpusControl,
    Course,
    Document,
    DocumentBatch,
    DocumentVersion,
    Schedule,
    StudyPlan,
    User,
    WriteOperation,
)
from app.adapters.db.uow import uow
from app.adapters.embedding.deterministic import embed_text
from app.adapters.vector.local import LocalVectorStore
from app.config import get_settings
from app.modules.knowledge.adapters import corpus_vector_space
from app.shared.clock import now_utc, parse_time, school_date, to_db
from app.shared.ids import (
    PREFIX_COURSE,
    PREFIX_PLAN,
    PREFIX_SCHEDULE,
    PREFIX_USER,
    new_id,
)
from app.shared.payload import basis_snapshot_from_payload, plan_payload_digest
from app.shared.security import hash_password

SAMPLE_PASSWORD: Final = "demo1234"

STUDENTS: Final[tuple[tuple[str, str], ...]] = (
    ("student_s01", "陈嘉宁"),
    ("student_s02", "李思远"),
    ("student_s03", "王沐晴"),
    ("student_s04", "赵子航"),
    ("student_s05", "周楚言"),
    ("student_s06", "孙卓然"),
    ("student_s07", "吴静姝"),
    ("student_s08", "郑铭轩"),
)

COURSES: Final[tuple[tuple[str, str, str], ...]] = (
    ("CS101", "数据结构", "数组、链表、树、图与基础算法"),
    ("MA201", "高等数学", "极限、导数、积分与级数"),
    ("CS201", "操作系统", "进程与线程、内存管理、文件系统"),
    ("CS301", "计算机网络", "分层模型、TCP/IP、HTTP 与网络编程"),
    ("CS302", "数据库系统", "关系模型、SQL、索引与事务"),
    ("MA202", "线性代数", "矩阵、向量空间与特征值"),
    ("PHY101", "大学物理", "力学、电磁学与实验"),
    ("SE201", "软件工程", "需求、设计、测试与协作"),
)

# (距今天数, 开始, 结束, 地点)；每名学生按序号轮转课程
SCHEDULE_SLOTS: Final[tuple[tuple[int, str, str, str], ...]] = (
    (1, "08:00", "09:40", "教学楼 A-201"),
    (1, "14:00", "15:40", "教学楼 B-305"),
    (2, "10:00", "11:40", "实验楼 C-101"),
    (4, "08:00", "09:40", "教学楼 A-302"),
    (7, "10:00", "11:40", "教学楼 B-201"),
    (9, "14:00", "15:40", "实验楼 D-204"),
)

PLAN_TEMPLATES: Final[tuple[dict[str, str], ...]] = (
    {
        "title": "第 1 周学习计划",
        "goal": "跟上本周课程节奏，完成课后练习",
        "content": "周一至周三复习课堂笔记；周四完成课后习题；周五整理错题；周末复盘本周知识盲点。",
    },
    {
        "title": "第 2 周学习计划",
        "goal": "完成实验报告，准备阶段小测",
        "content": "先做实验并记录数据；周三前写完实验报告；周四串一遍考点；周末做一套模拟题并订正。",
    },
)

# 已发布资料：文件名 + 正文（按空行切段，每段即一个 chunk）
DOCUMENTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "数据结构-课程大纲.md",
        "课程目标：掌握线性表、树、图等基础数据结构的存储与操作，能分析常见算法的时间与空间复杂度。\n\n"
        "核心章节：数组与链表、栈与队列、二叉树与遍历、图的表示与最短路径、排序与查找。"
        "重点掌握链表反转、二叉树层序遍历、拓扑排序与快速排序的实现。\n\n"
        "考核方式：平时作业 30%，实验 20%，期中 20%，期末 30%。实验需提交可运行代码与复杂度分析。",
    ),
    (
        "操作系统-实验手册.md",
        "实验一：进程调度。实现先来先服务与时间片轮转两种调度策略，统计平均周转时间与等待时间。\n\n"
        "实验二：同步与互斥。用信号量解决生产者-消费者问题，验证缓冲区满与空两种边界不会死锁。\n\n"
        "实验三：虚拟内存。模拟页面置换算法，比较 FIFO、LRU 与 Clock 的缺页率。",
    ),
    (
        "计算机网络-复习指南.md",
        "TCP 建立连接需要三次握手：SYN、SYN-ACK、ACK；关闭连接需要四次挥手，注意 TIME_WAIT 状态的作用。\n\n"
        "拥塞控制包含慢启动、拥塞避免、快重传与快恢复。慢启动阶段拥塞窗口按指数增长，直到达到阈值。\n\n"
        "HTTP/1.1 默认长连接；HTTP/2 引入多路复用与头部压缩；HTTPS 在传输层之上叠加 TLS。",
    ),
    (
        "数据库系统-索引与事务.md",
        "B+ 树索引把数据放在叶子节点并用链表串联，因此范围查询高效；聚簇索引决定行的物理顺序，二级索引需要回表。\n\n"
        "事务隔离级别从低到高为读未提交、读已提交、可重复读、串行化；MySQL 默认可重复读，通过 MVCC 与间隙锁处理幻读。\n\n"
        "索引失效常见原因：列上使用函数、隐式类型转换、前导通配符 LIKE '%x'、以及违反最左前缀原则。",
    ),
    (
        "高等数学-期中考试说明.md",
        "考试范围：极限与连续、导数与微分、中值定理、不定积分与定积分；不含级数。\n\n"
        "题型：选择题 20 分、填空题 20 分、计算题 40 分、证明题 20 分。计算题重点考查洛必达法则与换元积分。\n\n"
        "允许携带不带存储功能的计算器；考试时长 120 分钟；平时作业与出勤合计占课程总评 30%。",
    ),
)

_PARSER_CONFIG_DIGEST: Final = hashlib.sha256(b"sample-parser-v1").digest()


def _norm(value: str) -> bytes:
    return value.strip().casefold().encode("utf-8")


def _sha256(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _chunk_texts(body: str, limit: int = 480) -> list[str]:
    parts = [part.strip() for part in body.split("\n\n") if part.strip()]
    chunks: list[str] = []
    for part in parts:
        if len(part) <= limit:
            chunks.append(part)
        else:
            chunks.extend(part[i : i + limit] for i in range(0, len(part), limit))
    return chunks


async def _ensure_user(account: str, display_name: str, role: str) -> tuple[User, bool]:
    norm = _norm(account)
    async with uow() as tx:
        user = (
            await tx.session.execute(select(User).where(User.account_norm == norm))
        ).scalar_one_or_none()
        if user is not None:
            return user, False
        now = to_db(now_utc())
        user = User(
            id=new_id(PREFIX_USER),
            account=account,
            account_norm=norm,
            display_name=display_name,
            password_hash=await hash_password(SAMPLE_PASSWORD),
            role=role,
            enabled=True,
            auth_version=1,
            version=1,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(user)
        await tx.commit()
        return user, True


async def _ensure_course(code: str, name: str, description: str) -> tuple[Course, bool]:
    norm = _norm(code)
    async with uow() as tx:
        course = (
            await tx.session.execute(select(Course).where(Course.code_norm == norm))
        ).scalar_one_or_none()
        if course is not None:
            return course, False
        now = to_db(now_utc())
        course = Course(
            id=new_id(PREFIX_COURSE),
            code=code,
            code_norm=norm,
            name=name,
            description=description,
            enabled=True,
            version=1,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(course)
        await tx.commit()
        return course, True


async def _ensure_schedule(
    user_id: str, course_id: str, class_date, start: str, end: str, location: str
) -> bool:
    start_time = parse_time(start)
    end_time = parse_time(end)
    async with uow() as tx:
        exists = (
            await tx.session.execute(
                select(Schedule.id).where(
                    Schedule.user_id == user_id,
                    Schedule.course_id == course_id,
                    Schedule.class_date == class_date,
                    Schedule.start_time == start_time,
                    Schedule.end_time == end_time,
                )
            )
        ).first()
        if exists is not None:
            return False
        now = to_db(now_utc())
        tx.session.add(
            Schedule(
                id=new_id(PREFIX_SCHEDULE),
                user_id=user_id,
                course_id=course_id,
                class_date=class_date,
                start_time=start_time,
                end_time=end_time,
                location=location,
                overlap_reason=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        await tx.commit()
        return True


async def _ensure_plan(user: User, index: int) -> bool:
    template = PLAN_TEMPLATES[index]
    start = school_date() + timedelta(days=7 * index)
    end = start + timedelta(days=6)
    operation_id = f"sample-plan-{user.account}-{index + 1:02d}"
    payload = {
        "title": f"{user.display_name}的{template['title']}",
        "goal": template["goal"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "content": template["content"],
        "basis_types": ["schedule", "general"],
        "references": [],
    }
    digest = plan_payload_digest(payload)
    now = to_db(now_utc())
    async with uow() as tx:
        existed = (
            await tx.session.execute(
                select(WriteOperation).where(
                    WriteOperation.user_id == user.id,
                    WriteOperation.operation_id == operation_id,
                )
            )
        ).scalar_one_or_none()
        if existed is not None:
            return False
        operation = WriteOperation(
            user_id=user.id,
            operation_id=operation_id,
            source="manual",
            origin_chat_request_id=None,
            authorization_chat_request_id=None,
            draft_id=None,
            draft_version=None,
            content_digest=digest,
            state="pending",
            resolution="recovering",
            plan_id=None,
            error_code=None,
            retryable=False,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(operation)
        # ORM 未声明 FK：先 flush 保证 write_operations 先于 study_plans 落库。
        await tx.session.flush()
        plan = StudyPlan(
            id=new_id(PREFIX_PLAN),
            user_id=user.id,
            operation_id=operation_id,
            title=payload["title"],
            goal=payload["goal"],
            start_date=start,
            end_date=end,
            content=payload["content"],
            source="manual",
            basis_snapshot=basis_snapshot_from_payload(payload),
            version=1,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(plan)
        await tx.session.flush()
        operation.plan_id = plan.id
        operation.state = "succeeded"
        operation.resolution = "confirmed"
        operation.updated_at = now
        await tx.commit()
        return True


async def _ensure_document(index: int, name: str, body: str, *,
                           admin_id: str, vector_space: str) -> tuple[bool, list[str]]:
    """写入一份「已发布」资料；返回 (是否新建, chunk_id 列表)。"""
    tag = f"{index + 1:02d}"
    batch_id = f"bat_samp{tag}"
    document_id = f"doc_samp{tag}"
    version_id = f"dvs_samp{tag}"
    chunk_texts = _chunk_texts(body)
    chunk_ids = [f"chk_samp{tag}{n + 1:02d}" for n in range(len(chunk_texts))]
    now = to_db(now_utc())
    created = False

    async with uow() as tx:
        if await tx.session.get(Document, document_id) is None:
            created = True
            if await tx.session.get(DocumentBatch, batch_id) is None:
                tx.session.add(
                    DocumentBatch(
                        id=batch_id,
                        uploaded_by=admin_id,
                        state="published",
                        expected_files=1,
                        total_bytes=len(body.encode("utf-8")),
                        error_code=None,
                        published_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await tx.session.flush()
            tx.session.add(
                Document(
                    id=document_id,
                    batch_id=batch_id,
                    original_name=name,
                    file_type="md",
                    byte_size=len(body.encode("utf-8")),
                    original_storage_key=None,
                    visibility="shared",
                    processing_state="available",
                    # documents.active_version_id ↔ document_versions.document_id 是循环外键：
                    # 先落 document（暂时为空）→ 落 version → 回填 active_version_id。
                    active_version_id=None,
                    mutation_task_id=None,
                    error_code=None,
                    deleted_at=None,
                    cleanup_state="not_required",
                    version=2,
                    created_at=now,
                    updated_at=now,
                )
            )
            await tx.session.flush()
            tx.session.add(
                DocumentVersion(
                    id=version_id,
                    document_id=document_id,
                    version_no=1,
                    state="active",
                    content_digest=_sha256(body),
                    parser_config_digest=_PARSER_CONFIG_DIGEST,
                    vector_space=vector_space,
                    selected_attempt_id=None,
                    extracted_text_key=None,
                    error_code=None,
                    created_at=now,
                )
            )
            await tx.session.flush()
            document = await tx.session.get(Document, document_id)
            assert document is not None
            document.active_version_id = version_id

        for n, text in enumerate(chunk_texts):
            chunk_id = chunk_ids[n]
            if await tx.session.get(Chunk, chunk_id) is None:
                tx.session.add(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        version_id=version_id,
                        chunk_index=n + 1,
                        text_content=text,
                        page_number=None,
                        location_label=f"第 {n + 1} 段",
                        content_digest=_sha256(text),
                    )
                )
            citation_id = f"cit_samp{tag}{n + 1:02d}"
            if await tx.session.get(CitationReference, citation_id) is None:
                tx.session.add(
                    CitationReference(
                        id=citation_id,
                        document_id=document_id,
                        version_id=version_id,
                        chunk_id=chunk_id,
                        revoked_at=None,
                        created_at=now,
                    )
                )
        await tx.commit()

    # 向量：按命名空间幂等 upsert（重跑可修复向量缺失）
    store = LocalVectorStore()
    namespace = f"{vector_space}/{document_id}/{version_id}/tsk_samp{tag}/1"
    await store.upsert(
        namespace,
        [(chunk_ids[n], embed_text(text)) for n, text in enumerate(chunk_texts)],
        fence=1,
    )
    return created, chunk_ids


async def _ensure_corpus(vector_space: str, *, bump: bool) -> None:
    async with uow() as tx:
        row = (
            await tx.session.execute(
                select(CorpusControl).where(CorpusControl.singleton_id == 1)
            )
        ).scalar_one_or_none()
        if row is None:
            row = CorpusControl(
                singleton_id=1,
                revision=1 if bump else 0,
                active_vector_space=vector_space,
                publish_frozen=False,
                updated_at=to_db(now_utc()),
            )
            tx.session.add(row)
        else:
            if row.active_vector_space is None:
                row.active_vector_space = vector_space
            if row.publish_frozen:
                row.publish_frozen = False
            if bump:
                row.revision = int(row.revision) + 1
            row.updated_at = to_db(now_utc())
        await tx.commit()


async def seed_sample() -> dict[str, object]:
    settings = get_settings()
    admin, admin_created = await _ensure_user("admin_demo", "演示管理员", "admin")

    users_created = 0
    students: dict[str, User] = {}
    for account, display in STUDENTS:
        user, created = await _ensure_user(account, display, "student")
        students[account] = user
        users_created += int(created)

    courses_created = 0
    courses: dict[str, Course] = {}
    for code, name, description in COURSES:
        course, created = await _ensure_course(code, name, description)
        courses[code] = course
        courses_created += int(created)

    today = school_date()
    schedules_created = 0
    codes = [code for code, _, _ in COURSES]
    for offset, student in enumerate(students.values()):
        for slot_index, (day_offset, start, end, location) in enumerate(SCHEDULE_SLOTS):
            code = codes[(offset + slot_index) % len(codes)]
            schedules_created += int(
                await _ensure_schedule(
                    student.id,
                    courses[code].id,
                    today + timedelta(days=day_offset),
                    start,
                    end,
                    location,
                )
            )

    plans_created = 0
    for student in students.values():
        for index in range(len(PLAN_TEMPLATES)):
            plans_created += int(await _ensure_plan(student, index))

    vector_space = corpus_vector_space()
    documents_created = 0
    document_ids: list[str] = []
    chunks_total = 0
    for index, (name, body) in enumerate(DOCUMENTS):
        created, chunk_ids = await _ensure_document(
            index, name, body, admin_id=admin.id, vector_space=vector_space
        )
        documents_created += int(created)
        chunks_total += len(chunk_ids)
        document_ids.append(f"doc_samp{index + 1:02d}")

    await _ensure_corpus(vector_space, bump=documents_created > 0)

    return {
        "database": settings.database_name,
        "sample_password": SAMPLE_PASSWORD,
        "admin": {"account": "admin_demo", "created": admin_created},
        "students": {"count": len(students), "created": users_created},
        "courses": {"count": len(courses), "created": courses_created},
        "schedules_created": schedules_created,
        "plans_created": plans_created,
        "documents": {
            "count": len(DOCUMENTS),
            "created": documents_created,
            "chunks": chunks_total,
            "ids": document_ids,
            "vector_space": vector_space,
        },
    }


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli.sample")
    parser.add_argument(
        "--yes", action="store_true", help="跳过确认（CI / 脚本内使用）"
    )
    args = parser.parse_args(argv)
    if not args.yes:
        print("将向当前 DATABASE_URL 指向的库写入样例数据（仅开发/演示库）。")
        print("继续请加 --yes。")
        return 2
    try:
        result = await seed_sample()
    finally:
        await dispose_engine()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()

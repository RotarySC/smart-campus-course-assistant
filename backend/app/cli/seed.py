"""开发种子：``python -m app.cli.seed --demo``（仅开发/演示，不用于试点部署）。

- student_demo / admin_demo，口令 demo1234（开发种子，非默认生产口令）。
- 2 门课程；student_demo 的按 Asia/Shanghai 具体日期课表（今天 / 明天 / 下周一）。
- 一个示例计划（含 write_operations 记录）。
- 可重复执行：按规范值/唯一键/操作键判重，不重复插入。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import timedelta

from sqlalchemy import select

from app.adapters.db.engine import dispose_engine
from app.adapters.db.models import (
    Course,
    Schedule,
    StudyPlan,
    User,
    WriteOperation,
)
from app.adapters.db.uow import uow
from app.config import get_settings
from app.shared.clock import now_utc, parse_time, school_date, to_db
from app.shared.ids import PREFIX_COURSE, PREFIX_PLAN, PREFIX_SCHEDULE, PREFIX_USER, new_id
from app.shared.payload import basis_snapshot_from_payload, plan_payload_digest
from app.shared.security import hash_password

DEMO_PASSWORD = "demo1234"
DEMO_STUDENT = "student_demo"
DEMO_ADMIN = "admin_demo"
DEMO_PLAN_OPERATION = "seed-demo-plan-0001"


def _norm(value: str) -> bytes:
    return value.strip().casefold().encode("utf-8")


async def _ensure_user(account: str, display_name: str, role: str) -> tuple[User, bool]:
    norm = _norm(account)
    async with uow() as tx:
        result = await tx.session.execute(select(User).where(User.account_norm == norm))
        user = result.scalar_one_or_none()
        if user is not None:
            return user, False
        password_hash = await hash_password(DEMO_PASSWORD)
        now = to_db(now_utc())
        user = User(
            id=new_id(PREFIX_USER),
            account=account,
            account_norm=norm,
            display_name=display_name,
            password_hash=password_hash,
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


async def _ensure_course(code: str, name: str, description: str | None) -> tuple[Course, bool]:
    norm = _norm(code)
    async with uow() as tx:
        result = await tx.session.execute(select(Course).where(Course.code_norm == norm))
        course = result.scalar_one_or_none()
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
        result = await tx.session.execute(
            select(Schedule).where(
                Schedule.user_id == user_id,
                Schedule.course_id == course_id,
                Schedule.class_date == class_date,
                Schedule.start_time == start_time,
                Schedule.end_time == end_time,
            )
        )
        if result.scalar_one_or_none() is not None:
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


async def _ensure_demo_plan(user: User) -> bool:
    payload = {
        "title": "第一周学习计划",
        "goal": "熟悉课程大纲并完成第一章练习",
        "start_date": school_date().isoformat(),
        "end_date": (school_date() + timedelta(days=6)).isoformat(),
        "content": "周一至周三阅读教材第一章；周四完成习题；周末复盘。",
        "basis_types": ["schedule", "general"],
        "references": [],
    }
    digest = plan_payload_digest(payload)
    now = to_db(now_utc())
    async with uow() as tx:
        result = await tx.session.execute(
            select(WriteOperation).where(
                WriteOperation.user_id == user.id,
                WriteOperation.operation_id == DEMO_PLAN_OPERATION,
            )
        )
        operation = result.scalar_one_or_none()
        if operation is not None:
            return False
        operation = WriteOperation(
            user_id=user.id,
            operation_id=DEMO_PLAN_OPERATION,
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
        # 显式 flush：ORM 未声明 FK，需保证 write_operations 先于 study_plans 落库。
        await tx.session.flush()
        plan = StudyPlan(
            id=new_id(PREFIX_PLAN),
            user_id=user.id,
            operation_id=DEMO_PLAN_OPERATION,
            title=payload["title"],
            goal=payload["goal"],
            start_date=school_date(),
            end_date=school_date() + timedelta(days=6),
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


async def _ensure_demo_corpus() -> None:
    """开发/演示：解除资料发布冻结（迁移默认 TRUE 是安全默认）。

    仅影响本机演示库；生产切换必须按后端详细设计 §11.3 的向量空间迁移流程显式解除，
    不得把本函数当作试点发布步骤。
    """
    from app.adapters.db.models import CorpusControl

    async with uow() as tx:
        row = (
            await tx.session.execute(
                select(CorpusControl).where(CorpusControl.singleton_id == 1)
            )
        ).scalar_one_or_none()
        if row is None:
            row = CorpusControl(
                singleton_id=1,
                revision=0,
                active_vector_space=None,
                publish_frozen=False,
                updated_at=to_db(now_utc()),
            )
            tx.session.add(row)
        elif row.publish_frozen:
            row.publish_frozen = False
            row.updated_at = to_db(now_utc())
        await tx.commit()


async def seed_demo() -> dict[str, object]:
    settings = get_settings()
    admin, admin_created = await _ensure_user(DEMO_ADMIN, "演示管理员", "admin")
    student, student_created = await _ensure_user(DEMO_STUDENT, "演示学生", "student")
    ds, ds_created = await _ensure_course("CS101", "数据结构", "数组、链表、树与基础算法")
    ma, ma_created = await _ensure_course("MA201", "高等数学", "极限、导数与积分")

    today = school_date()
    tomorrow = today + timedelta(days=1)
    # “下周一”：当前自然周之后一周的周一（周一为一周起点）
    next_monday = today + timedelta(days=(7 - today.weekday()) + 7)

    schedules_created = 0
    schedules_created += int(
        await _ensure_schedule(student.id, ds.id, today, "08:00", "09:40", "教学楼 A-201")
    )
    schedules_created += int(
        await _ensure_schedule(student.id, ma.id, tomorrow, "10:00", "11:40", "教学楼 B-305")
    )
    schedules_created += int(
        await _ensure_schedule(student.id, ds.id, next_monday, "14:00", "15:40", "实验楼 C-101")
    )
    plan_created = int(await _ensure_demo_plan(student))
    await _ensure_demo_corpus()

    return {
        "database": settings.database_name,
        "school_timezone": settings.school_timezone,
        "corpus_publish_frozen": False,
        "users": {
            "admin_demo": {"id": admin.id, "created": admin_created},
            "student_demo": {"id": student.id, "created": student_created},
        },
        "courses": {
            "CS101": {"id": ds.id, "created": ds_created},
            "MA201": {"id": ma.id, "created": ma_created},
        },
        "schedules_created": schedules_created,
        "demo_plan_created": plan_created,
        "demo_password": DEMO_PASSWORD,
    }


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli.seed")
    parser.add_argument("--demo", action="store_true", help="写入开发演示种子（可重复执行）")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.print_help()
        return 2
    try:
        result = await seed_demo()
    finally:
        await dispose_engine()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()

"""chat_requests.instruction_class：保存指令分类持久化（M5.1 / 审计 P0-①）。

背景：保存事务此前在写入时**现场签发** direct_instruction 许可，等于「只要调用方
声称要保存就能落库」。本迁移把服务端对用户消息的分类结果持久化到请求行，
让保存事务可以 fail-closed 复核（explicit 才写），模型与调用方无法自行声明。

0001 的说明里写过「P2/P3 不再新增迁移」——本次是安全修复引入的最小增量（可空列 +
CHECK），不回改既有 DDL；对旧数据无破坏（NULL 表示「未分类」，保存事务按拒绝处理）。

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chat_requests "
        "ADD COLUMN instruction_class VARCHAR(16) NULL AFTER terminal_reason"
    )
    op.execute(
        "ALTER TABLE chat_requests ADD CONSTRAINT ck_chat_instruction "
        "CHECK (instruction_class IS NULL OR instruction_class IN "
        "('none','explicit','ambiguous','denied'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chat_requests DROP CHECK ck_chat_instruction")
    op.execute("ALTER TABLE chat_requests DROP COLUMN instruction_class")

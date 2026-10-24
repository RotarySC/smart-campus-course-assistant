"""G2 反向注入（系统级，不修改任何源码）：启动一个**管理员鉴权被旁路**的"坏"实例。

做法：正常导入应用后，把 `app.modules.identity.interface.get_admin` 换成"直接放行调用者"
（认证 `get_actor` 保持真实），并在导入 `app.main`/路由之前完成替换，使路由里的
`Depends(get_admin)` 捕获旁路实现。仓库源码零改动。

用途：证明"学生令牌打 /admin/** → 403"是**服务端**强制（不是只在 UI 隐藏入口）：
坏实例必须让这条门禁失败（返回 200/非 403）。

启动后监听 127.0.0.1:8299；检查脚本见 `g2_gate_check.py`。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))  # 允许从仓库根直接运行本脚本

import uvicorn  # noqa: E402
from fastapi import Depends, Request  # noqa: E402

import app.modules.identity.interface as iface  # noqa: E402
from app.shared.context import ActorContext  # noqa: E402

BROKEN_PORT = 8299

_real_get_actor = iface.get_actor


async def _broken_get_admin(request: Request, actor: ActorContext = Depends(_real_get_actor)) -> ActorContext:  # noqa: ARG001
    """旁路：不做 role 校验，任何已认证用户都被当作管理员放行。"""
    return actor


def main() -> int:
    # 必须在 app.main / routers 导入之前替换，路由器的 Depends(get_admin) 才能捕获旁路实现
    iface.get_admin = _broken_get_admin  # type: ignore[assignment]
    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=BROKEN_PORT, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""内部 API 入口：``uvicorn app.entrypoints.internal_api:app --port 8101``（只回环）。

Phase 3 实现委派兑换与三工具；本阶段四个端点返回 501 统一信封。
"""

from app.main import create_internal_app

app = create_internal_app()

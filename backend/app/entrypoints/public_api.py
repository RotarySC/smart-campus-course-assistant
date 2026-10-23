"""公共 API 入口：``uvicorn app.entrypoints.public_api:app --port 8100``。"""

from app.main import create_app

app = create_app()

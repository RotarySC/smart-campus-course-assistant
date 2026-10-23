"""本地 VectorStore Adapter（TBD-07 未冻结时的可替换实现）。

语义与生产选型要求对齐（后端详细设计 §10.5 / §11.3）：

- **命名空间**：``<vector_space>/<document_id>/<version_id>/<task_id>/<fence>``；
- **幂等 upsert**：同一 chunk 同一代次重复写不产生重复；
- **按范围删除**：按 namespace 或前缀彻底删除；
- **写入收敛屏障 barrier**：登记 ``(prefix, fence)`` 后，``fence <= barrier_fence``
  的写入被拒绝，已写入的旧代次记录被清除（证明不会出现迟到写入）。

持久化到 ``<root>/vector_store.json``（``CCA_VECTOR_ROOT``，默认 backend/var/vector）。
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any, Final

import numpy as np

from app.config import BACKEND_DIR

_NS_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-")
_LOCKS: dict[str, asyncio.Lock] = {}


class VectorStoreError(Exception):
    """向量存储不可用。"""


class LateWriteRejected(VectorStoreError):
    """收敛屏障之后仍出现旧代次写入（必须被拒绝）。"""


def default_root() -> Path:
    raw = os.environ.get("CCA_VECTOR_ROOT", "").strip()
    return Path(raw) if raw else BACKEND_DIR / "var" / "vector"


def _lock_for(path: Path) -> asyncio.Lock:
    key = str(path)
    lock = _LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[key] = lock
    return lock


class LocalVectorStore:
    provider: Final = "local-json"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or default_root()).resolve()
        self.data_file = self.root / "vector_store.json"

    # ------------------------------------------------------------------ 基础设施
    def _load(self) -> dict[str, Any]:
        if not self.data_file.exists():
            return {"namespaces": {}, "barriers": {}}
        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VectorStoreError("向量存储损坏") from exc
        payload.setdefault("namespaces", {})
        payload.setdefault("barriers", {})
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.data_file.with_name(f".vector_store.{secrets.token_hex(6)}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.data_file)

    @staticmethod
    def _check_namespace(namespace: str) -> str:
        if (
            not namespace
            or len(namespace) > 512
            or ".." in namespace
            or namespace.startswith("/")
            or any(ch not in _NS_CHARS for ch in namespace)
        ):
            raise VectorStoreError("非法向量命名空间")
        return namespace

    @staticmethod
    def _under(namespace: str, prefix: str) -> bool:
        return namespace == prefix or namespace.startswith(prefix + "/")

    # ------------------------------------------------------------------ 写入
    async def upsert(
        self, namespace: str, items: list[tuple[str, Any]], *, fence: int
    ) -> int:
        """幂等 upsert；晚于收敛屏障的旧代次写入抛 :class:`LateWriteRejected`。"""
        self._check_namespace(namespace)
        if not items:
            return 0
        async with _lock_for(self.data_file):
            payload = self._load()
            for prefix, barrier_fence in payload["barriers"].items():
                if self._under(namespace, prefix) and int(fence) <= int(barrier_fence):
                    raise LateWriteRejected(
                        f"fence={fence} 已被 {prefix} 的屏障 {barrier_fence} 覆盖"
                    )
            entry = payload["namespaces"].setdefault(
                namespace, {"fence": int(fence), "records": {}}
            )
            entry["fence"] = max(int(entry.get("fence", 0)), int(fence))
            records = entry["records"]
            written = 0
            for chunk_id, vector in items:
                existing = records.get(chunk_id)
                if existing is not None and int(existing.get("fence", 0)) > int(fence):
                    continue  # 新代次数据不被旧代次覆盖
                arr = np.asarray(vector, dtype=np.float32).ravel()
                norm = float(np.linalg.norm(arr))
                if norm == 0.0:
                    continue
                records[chunk_id] = {
                    "v": [round(float(x), 6) for x in (arr / norm)],
                    "fence": int(fence),
                }
                written += 1
            self._save(payload)
            return written

    async def barrier(self, prefix: str, fence: int) -> int:
        """登记收敛屏障并清除旧代次记录；返回清除的记录数。"""
        self._check_namespace(prefix)
        async with _lock_for(self.data_file):
            payload = self._load()
            payload["barriers"][prefix] = max(
                int(payload["barriers"].get(prefix, 0)), int(fence)
            )
            removed = 0
            for namespace in list(payload["namespaces"]):
                if not self._under(namespace, prefix):
                    continue
                entry = payload["namespaces"][namespace]
                records = entry.get("records", {})
                for chunk_id in list(records):
                    if int(records[chunk_id].get("fence", 0)) <= int(fence):
                        del records[chunk_id]
                        removed += 1
                if not records and int(entry.get("fence", 0)) <= int(fence):
                    del payload["namespaces"][namespace]
            self._save(payload)
            return removed

    async def delete_namespace(self, namespace: str) -> int:
        """按命名空间彻底删除，返回删除记录数。"""
        self._check_namespace(namespace)
        async with _lock_for(self.data_file):
            payload = self._load()
            entry = payload["namespaces"].pop(namespace, None)
            self._save(payload)
            return len(entry.get("records", {})) if entry else 0

    async def delete_prefix(self, prefix: str) -> int:
        """按前缀删除（attempt 目标范围），返回删除记录数。"""
        self._check_namespace(prefix)
        async with _lock_for(self.data_file):
            payload = self._load()
            removed = 0
            for namespace in list(payload["namespaces"]):
                if self._under(namespace, prefix):
                    removed += len(
                        payload["namespaces"][namespace].get("records", {})
                    )
                    del payload["namespaces"][namespace]
            self._save(payload)
            return removed

    # ------------------------------------------------------------------ 查询
    async def namespace_chunk_ids(self, namespace: str) -> list[str]:
        self._check_namespace(namespace)
        async with _lock_for(self.data_file):
            payload = self._load()
            return sorted(payload["namespaces"].get(namespace, {}).get("records", {}))

    async def list_chunk_ids(self, prefix: str) -> list[str]:
        """列举前缀范围内全部 chunk_id（校验索引完整性用）。"""
        self._check_namespace(prefix)
        async with _lock_for(self.data_file):
            payload = self._load()
            ids: list[str] = []
            for namespace, entry in payload["namespaces"].items():
                if self._under(namespace, prefix):
                    ids.extend(entry.get("records", {}).keys())
            return sorted(ids)

    async def record_count(self, prefix: str) -> int:
        return len(await self.list_chunk_ids(prefix))

    async def search(
        self, prefix: str, vector: Any, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """在前缀范围内按余弦相似度取 Top-K。"""
        self._check_namespace(prefix)
        query = np.asarray(vector, dtype=np.float32).ravel()
        norm = float(np.linalg.norm(query))
        if norm == 0.0 or limit <= 0:
            return []
        query = query / norm
        async with _lock_for(self.data_file):
            payload = self._load()
            candidates: list[tuple[float, str, str]] = []
            for namespace, entry in payload["namespaces"].items():
                if not self._under(namespace, prefix):
                    continue
                for chunk_id, record in entry.get("records", {}).items():
                    arr = np.asarray(record["v"], dtype=np.float32)
                    if arr.shape != query.shape:
                        continue
                    candidates.append((float(arr @ query), chunk_id, namespace))
            candidates.sort(key=lambda item: (-item[0], item[1]))
            return [
                {"chunk_id": chunk_id, "namespace": namespace, "score": score}
                for score, chunk_id, namespace in candidates[:limit]
            ]

    # ------------------------------------------------------------------ 测试工具
    async def reset(self) -> None:
        async with _lock_for(self.data_file):
            self._save({"namespaces": {}, "barriers": {}})

    async def describe(self) -> dict[str, Any]:
        async with _lock_for(self.data_file):
            payload = self._load()
        namespaces = payload["namespaces"]
        return {
            "provider": self.provider,
            "root": str(self.root),
            "namespaces": len(namespaces),
            "records": sum(len(e.get("records", {})) for e in namespaces.values()),
            "barriers": payload["barriers"],
            "production": False,
        }


__all__ = [
    "LateWriteRejected",
    "LocalVectorStore",
    "VectorStoreError",
    "default_root",
]

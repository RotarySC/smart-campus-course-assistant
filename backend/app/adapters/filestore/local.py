"""本地卷 FileStore：内部随机键 + 路径穿越防护 + 流式写入。

存储布局（后端详细设计 §10.1；键为内部约定，不返回客户端）::

    uploads/{upload_id}/sealed-original
    documents/{document_id}/original
    attempts/{task_id}/{fence}/{version_id}/extracted-text
    attempts/{task_id}/{fence}/{version_id}/chunk-manifest

根目录由 ``CCA_FILESTORE_ROOT`` 覆盖，默认 ``backend/uploads``（已 gitignore）。
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import BinaryIO, Iterable

from app.config import BACKEND_DIR, env_str

_KEY_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CHUNK = 1024 * 1024


class StorageError(Exception):
    """FileStore 不可用或键非法（对外映射 STORAGE_UNAVAILABLE / 内部错误）。"""


def default_root() -> Path:
    raw = env_str("CCA_FILESTORE_ROOT", "").strip()
    return Path(raw) if raw else BACKEND_DIR / "uploads"


class FileStore:
    """本地文件适配器；所有公开方法只接受内部键。"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or default_root()).resolve()

    # ------------------------------------------------------------------ 键
    def validate_key(self, key: str) -> str:
        if not isinstance(key, str) or not key or len(key) > 512:
            raise StorageError("非法存储键")
        if key.startswith(("/", "\\")) or "\\" in key or ":" in key:
            raise StorageError("非法存储键")
        parts = key.split("/")
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise StorageError("非法存储键")
        for part in parts:
            if not _KEY_PART.match(part):
                raise StorageError("非法存储键")
        return key

    def path_of(self, key: str) -> Path:
        self.validate_key(key)
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise StorageError("非法存储键")
        return path

    # ------------------------------------------------------------------ 写入
    def _atomic_write(self, key: str, writer) -> int:
        target = self.path_of(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
        try:
            written = writer(tmp)
            os.replace(tmp, target)
            return written
        except BaseException:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - 清理尽力而为
                pass
            raise

    def write_stream(self, key: str, stream: BinaryIO, *, max_bytes: int | None = None) -> int:
        """流式写入：分块计量，超过 ``max_bytes`` 抛 ``StorageError`` 并清理半成品。"""
        target = self.path_of(key)

        def _writer(tmp: Path) -> int:
            written = 0
            with tmp.open("wb") as handle:
                while True:
                    block = stream.read(_CHUNK)
                    if not block:
                        break
                    written += len(block)
                    if max_bytes is not None and written > max_bytes:
                        raise StorageError("超出单文件字节上限")
                    handle.write(block)
            return written

        return self._atomic_write(key, _writer)

    def write_bytes(self, key: str, data: bytes) -> int:
        def _writer(tmp: Path) -> int:
            tmp.write_bytes(data)
            return len(data)

        return self._atomic_write(key, _writer)

    async def write_async_stream(
        self,
        key: str,
        stream,
        *,
        max_bytes: int | None = None,
        validator=None,
    ) -> int:
        """异步流式写入（multipart 上传用）：分块计量 + 可选内容校验回调。"""
        target = self.path_of(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
        written = 0
        try:
            with tmp.open("wb") as handle:
                while True:
                    block = await stream.read(_CHUNK)
                    if not block:
                        break
                    written += len(block)
                    if max_bytes is not None and written > max_bytes:
                        raise StorageError("超出单文件字节上限")
                    if validator is not None:
                        validator(block)
                    handle.write(block)
            os.replace(tmp, target)
            return written
        except BaseException:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
            raise

    def copy(self, source_key: str, target_key: str) -> int:
        source = self.path_of(source_key)
        target = self.path_of(target_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
        try:
            shutil.copyfile(source, tmp)
            os.replace(tmp, target)
            return target.stat().st_size
        except BaseException:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
            raise

    # ------------------------------------------------------------------ 读取
    def exists(self, key: str) -> bool:
        return self.path_of(key).is_file()

    def size_of(self, key: str) -> int:
        return self.path_of(key).stat().st_size

    def read_bytes(self, key: str) -> bytes:
        return self.path_of(key).read_bytes()

    def read_first_bytes(self, key: str, size: int = 8) -> bytes:
        with self.path_of(key).open("rb") as handle:
            return handle.read(size)

    def read_text(self, key: str, *, encoding: str = "utf-8") -> str:
        return self.read_bytes(key).decode(encoding)

    # ------------------------------------------------------------------ 删除 / 列举
    def delete(self, key: str) -> bool:
        path = self.path_of(key)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def delete_prefix(self, prefix: str) -> int:
        """删除前缀下全部对象（attempt 范围清理）；返回删除对象数。"""
        self.validate_key(prefix)
        base = self.path_of(prefix)
        if not base.exists():
            return 0
        removed = 0
        if base.is_dir():
            for child in sorted(base.rglob("*")):
                if child.is_file():
                    child.unlink(missing_ok=True)
                    removed += 1
            shutil.rmtree(base, ignore_errors=True)
        else:
            base.unlink(missing_ok=True)
            removed = 1
        return removed

    def list_keys(self, prefix: str) -> list[str]:
        self.validate_key(prefix)
        base = self.path_of(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [prefix]
        return sorted(
            str(path.relative_to(self.root)).replace(os.sep, "/")
            for path in base.rglob("*")
            if path.is_file()
        )

    def count_keys(self, prefix: str) -> int:
        return len(self.list_keys(prefix))

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def digest(data: bytes) -> bytes:
        return hashlib.sha256(data).digest()

    @staticmethod
    def sha256_file(path: Path) -> bytes:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(block)
        return digest.digest()


def norm_key_parts(parts: Iterable[str]) -> str:
    """拼接内部键并校验各段（供调用方构造键时使用）。"""
    cleaned = []
    for part in parts:
        text = str(part)
        if not _KEY_PART.match(text):
            raise StorageError("非法存储键片段")
        cleaned.append(text)
    return "/".join(cleaned)


__all__ = ["FileStore", "StorageError", "default_root", "norm_key_parts"]

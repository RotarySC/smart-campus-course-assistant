"""FileStore Adapter（Phase 2 知识链路）。

本地卷实现见 :mod:`app.adapters.filestore.local`。生产环境可替换为对象存储，
只要满足 ``storage_attempts`` 所需的幂等写、按 attempt 前缀列举/删除与收敛屏障语义。
"""

from app.adapters.filestore.local import FileStore, StorageError

__all__ = ["FileStore", "StorageError"]

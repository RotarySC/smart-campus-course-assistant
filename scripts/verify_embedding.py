#!/usr/bin/env python3
"""Embedding 服务内容级回归探针（换服务端 / 发布前 / CI 必跑）。

为什么需要它：2026-10-28 服务端那类缺陷（左填充却按右填充取池化下标）发生时，
响应条数、向量维度、L2 范数**三项校验全部正常**，只有「同一文本：批量结果 vs 单条结果」
的内容比对能发现。后端内置了 ``CCA_EMBEDDING_VERIFY_BATCH=1`` 的在线自检；本脚本是
**跨进程、可复跑**的同一判据，给 CI 和「换机器/换服务端后先验一遍」用。

判据：批内每条与其单条结果的余弦相似度 ≥ ``--min-cos``（默认 0.999）；
      并单独检查批内**第一条**（左填充错位最先打中它）。

用法（仓库根）：

    & .\\.venv\\Scripts\\python.exe scripts\\verify_embedding.py
    & .\\.venv\\Scripts\\python.exe scripts\\verify_embedding.py --samples 12 --min-cos 0.999

退出码：0 通过；1 有偏差或服务不可用；2 未启用远端 Embedding（配置缺失，不算失败）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402 - 需先调整 sys.path

from app.adapters.embedding import registry  # noqa: E402
from app.adapters.embedding.remote import RemoteEmbedding  # noqa: E402

# 刻意做成"长度差异大、中英混排、含标点/数字"的一组文本：
# 批量错位在长度接近时最不容易暴露，所以样本要长短悬殊。
SAMPLE_TEXTS = (
    "数据结构课程的实验报告什么时候提交？",
    "操作系统实验要求：每次实验前完成预习报告，写明实验目的、步骤与预期结果，并在实验开始前提交。"
    "评分规则为预习 20%、过程 30%、报告 50%，补做实验按 80% 计分。",
    "索引与事务：B+ 树把数据集中在叶子层以减少随机 I/O；事务隔离级别包括读未提交、读已提交、可重复读与串行化。",
    "计算机网络复习：TCP 三次握手与四次挥手，拥塞控制包括慢启动、拥塞避免、快重传与快恢复。",
    "高等数学期中考试范围包含级数与多元函数微分，考试时长 90 分钟，闭卷，可带计算器。",
    "The quick brown fox jumps over the lazy dog.",
    "Embedding 服务自检：这一条专门用来与长度悬殊的其它样本配对，检验批量填充与池化是否逐条对齐。",
    "短句。",
)


def _health(base_url: str) -> dict:
    """尽量取服务端自报信息（built_at / dim / pooling）；取不到不算失败。"""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    try:
        response = httpx.get(f"{root}/health", timeout=5.0)
        return {"status": response.status_code, "payload": response.json()}
    except Exception as exc:  # 服务端可能没有 /health，或不可达
        return {"status": None, "error": f"{type(exc).__name__}: {exc}"}


def _cos(a, b) -> float:
    # 适配器返回的向量已是归一化单位向量，直接点积即余弦；为稳妥仍按定义归一一次。
    import numpy as np

    va = np.asarray(a, dtype=np.float64).ravel()
    vb = np.asarray(b, dtype=np.float64).ravel()
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


async def _run(samples: int, min_cos: float) -> int:
    if not registry.is_remote():
        print(
            "SKIP 当前 CCA_EMBEDDING_PROVIDER 不是 openai-compatible（确定性 Embedding 无需本探针）。",
            flush=True,
        )
        return 2

    from app.adapters.embedding.remote import base_url, embedding_dim, model_name

    # verify_batch_=False：这里要测**原始批量通路**，不能用自己的在线自检掩盖问题。
    provider = RemoteEmbedding(verify_batch_=False)
    texts = list(SAMPLE_TEXTS[: max(1, min(samples, len(SAMPLE_TEXTS)))])
    print(
        f"provider={provider.provider} dim={embedding_dim()} model={model_name()} "
        f"base_url={base_url()} batch={len(texts)}",
        flush=True,
    )
    print("health=" + json.dumps(_health(base_url()), ensure_ascii=False), flush=True)

    batch = await provider.embed_batch(texts)
    if len(batch) != len(texts):
        print(f"FAIL 批量条数不符：请求 {len(texts)}，返回 {len(batch)}", flush=True)
        return 1
    dims = {len(vector) for vector in batch}
    if dims != {embedding_dim()}:
        print(f"FAIL 维度不符：期望 {embedding_dim()}，实际 {sorted(dims)}", flush=True)
        return 1

    failures = 0
    worst = (1.0, -1)
    for index, text in enumerate(texts):
        single = await provider.embed(text)
        cos = _cos(batch[index], single)
        ok = cos >= min_cos
        failures += 0 if ok else 1
        if cos < worst[0]:
            worst = (cos, index)
        print(
            f"{'OK  ' if ok else 'FAIL'} #{index} chars={len(text):4d} cos={cos:.6f} "
            f"{'' if ok else '← 批量与单条不一致（疑似填充/池化错位）'}",
            flush=True,
        )

    first_cos = _cos(batch[0], await provider.embed(texts[0]))
    print(f"首条复核：cos={first_cos:.6f}（左填充错位最先打中批内第 1 条）", flush=True)
    if failures or first_cos < min_cos:
        print(
            f"RESULT FAIL：{failures}/{len(texts)} 条不一致，最差 #{worst[1]} cos={worst[0]:.6f} "
            f"（阈值 {min_cos}）",
            flush=True,
        )
        return 1
    print(f"RESULT PASS：{len(texts)} 条批量/单条一致（阈值 {min_cos}）", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embedding 批量对齐内容级探针")
    parser.add_argument("--samples", type=int, default=8, help=f"样本条数（1–{len(SAMPLE_TEXTS)}，默认 8）")
    parser.add_argument("--min-cos", type=float, default=0.999, help="批量 vs 单条的余弦下限（默认 0.999）")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args.samples, args.min_cos))
    except Exception as exc:  # 服务不可达 / 响应畸形
        print(f"FAIL 探针执行异常：{type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

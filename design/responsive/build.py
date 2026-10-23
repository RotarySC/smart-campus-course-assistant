#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装方向 B 的响应式原型。

    python design/responsive/build.py

做三件事：
1. 把 rb.css 内联进 shell.html 的 {{CSS}}，把四个片段按 S01→S12 顺序拼进 {{VIEWS}}，
   产出**单文件、零外部请求**的 `design/responsive/b-responsive.html`。
2. **构建期契约检查**（有问题就报出来，不阻断构建）：
   - 片段里用到的 class 必须都能在 rb.css 里找到定义；
   - 带 `table--stack` 的表格里，每个 `<td>` 都必须有 `data-label`（漏了窄屏会渲染出空字段名）；
   - 片段里不得出现 `<style>`、`<html>`、`@media`、裸 hex、emoji。
3. 打印每个视图的 id 与字节数，便于核对。
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

# 视图拼接顺序：S01 登录 → 助手 → 学生业务 → 管理中心
PARTS = [
    ("login.html", "S01"),
    ("assistant.html", "S02–S06"),
    ("records.html", "S07–S09"),
    ("admin.html", "S10–S12"),
]

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\uFE0F]"
)
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


def read(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


def classes_defined(css):
    return set(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", css))


def classes_used(html):
    used = set()
    for m in re.finditer(r'class="([^"]+)"', html):
        for c in m.group(1).split():
            used.add(c)
    return used


def check_stack_tables(html, name, problems):
    """带 table--stack 的表格里，每个 <td> 都要有 data-label。"""
    for tm in re.finditer(r"<table[^>]*>", html):
        if "table--stack" not in tm.group(0):
            continue
        end = html.find("</table>", tm.end())
        block = html[tm.end(): end if end > 0 else len(html)]
        for td in re.finditer(r"<td[^>]*>", block):
            if "data-label" not in td.group(0):
                problems.append("%s: 一处 <td> 缺 data-label（窄屏会显示空字段名）：%s"
                                % (name, td.group(0)[:70]))


def main():
    css = read("rb.css")
    shell = read("shell.html")
    defined = classes_defined(css)

    views, problems, report = [], [], []
    for fname, ids in PARTS:
        path = os.path.join(HERE, "parts", fname)
        if not os.path.exists(path):
            problems.append("缺少片段文件：parts/%s" % fname)
            continue
        html = read(os.path.join("parts", fname))
        views.append(html)

        # 约束检查必须排除注释：片段的说明性注释里会**提到** `<style>` 等字样
        body = re.sub(r"<!--.*?-->", " ", html, flags=re.S)

        found_ids = re.findall(r'<section class="view" id="(v-S\d\d)"', body)
        report.append("  parts/%-16s 视图 %-9s %s  (%d 字节)"
                      % (fname, ids, ",".join(found_ids) or "无", len(html.encode("utf-8"))))

        unknown = sorted(c for c in classes_used(body) if c not in defined)
        if unknown:
            problems.append("parts/%s 使用了 rb.css 未定义的 class：%s" % (fname, ", ".join(unknown)))
        if re.search(r"<style\b", body):
            problems.append("parts/%s 含 <style>（片段不允许）" % fname)
        if re.search(r"@media", body):
            problems.append("parts/%s 含 @media（片段不允许，重排只在 rb.css 里）" % fname)
        if re.search(r"</?(html|head|body)\b", body):
            problems.append("parts/%s 含 html/head/body 标签（片段不允许）" % fname)
        hexes = sorted(set(HEX_RE.findall(body)))
        if hexes:
            problems.append("parts/%s 含裸 hex：%s" % (fname, ",".join(hexes[:8])))
        emo = sorted(set(EMOJI_RE.findall(body)))
        if emo:
            problems.append("parts/%s 含 emoji 字符：%s"
                            % (fname, ",".join("U+%04X" % ord(c) for c in emo)))
        check_stack_tables(body, "parts/%s" % fname, problems)

    out = shell.replace("{{CSS}}", css.rstrip()).replace("{{VIEWS}}", "\n".join(views))

    dest = os.path.join(HERE, "b-responsive.html")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(out)

    print("=" * 74)
    print("方向 B 响应式原型 · 组装报告")
    print("=" * 74)
    print("片段：")
    print("\n".join(report) if report else "  （无）")
    print("\n产物：design/responsive/b-responsive.html  %d 字节" % len(out.encode("utf-8")))
    print("内联 CSS %d 字节；rb.css 定义 class %d 个" % (len(css.encode("utf-8")), len(defined)))

    # 产物级检查
    ext = [u for u in re.findall(r"https?://[^\s\"'<>)]+", out) if "w3.org" not in u]
    print("产物外部引用：%s" % (ext or "无"))
    print("产物 <img>/<link>/<script src>：%d/%d/%d"
          % (len(re.findall(r"<img\s", out)), len(re.findall(r"<link\b", out)),
             len(re.findall(r"<script[^>]+src=", out))))
    ids = re.findall(r'<section class="view" id="(v-S\d\d)"', out)
    print("产物视图 %d 个：%s" % (len(ids), ", ".join(ids)))

    print("\n构建期契约检查：")
    if problems:
        for p in problems:
            print("  ! %s" % p)
        print("  共 %d 条" % len(problems))
    else:
        print("  全部通过（class 契约 / data-label / 无 style / 无 @media / 无裸 hex / 无 emoji）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

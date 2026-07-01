#!/usr/bin/env python
"""
render_state.py — 从 project.db 生成 STATUS.md 格式文本

用法:
    python render_state.py <db_path>          # 输出到 stdout
    python render_state.py <db_path> --file   # 写到 STATUS.md
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_all_state, check_consistency


def render(db_path: str) -> str:
    state = get_all_state(db_path)
    warnings = check_consistency(db_path)

    lines = []
    lines.append("# Current Status\n")
    lines.append(f"> 最后更新: {state.get('status_health', {}).get('status_md_updated', '?')}\n")

    # 项目标识
    lines.append(f"**项目**: {state.get('current_branch', '?')} 分支\n")

    # 最近提交
    lc = state.get("last_commit", {})
    if lc:
        lines.append(f"**最后提交**: {lc.get('message', '?')}")
        lines.append(f"**SHA**: {lc.get('sha', '?')[:12]}")
        lines.append(f"**日期**: {lc.get('date', '?')[:19]}")
        lines.append("")

    # dirty files
    dirty = state.get("dirty_files", 0)
    if dirty:
        lines.append(f"**⚠ 未提交变更**: {dirty} 个文件\n")
    else:
        lines.append("**工作区**: 干净\n")

    # AI 操作
    ai_action = state.get("last_ai_action")
    if ai_action:
        lines.append(f"**上次 AI 操作**: {ai_action}\n")

    # 一致性警告
    if warnings:
        lines.append("## 一致性警告\n")
        for w in warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    # 健康状态
    health = state.get("status_health", {})
    if health.get("healthy") is False:
        lines.append("> ⚠ 状态健康检查未通过，建议运行 `python .ai-hooks/db.py summary <db_path>`\n")

    return "\n".join(lines).strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_state.py <db_path> [--file]")
        sys.exit(1)

    db_path = sys.argv[1]
    output = render(db_path)

    if len(sys.argv) >= 3 and sys.argv[2] == "--file":
        status_path = os.path.join(os.path.dirname(db_path), "STATUS.md")
        with open(status_path, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
        print(f"Written to {status_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()

---
name: ai-review
description: Run .ai/ project state review — check consistency, review checklist, suggest MEMORY/STATUS updates after a work session
---

# ai-review

当用户要求 review / 检查工作 / 准备提交，或触发 `/ai-review` 时执行。

## 流程

### 1. 读取当前状态
- 读 `.ai/project.db` — 使用 hooks.conf 中的 `$AI_HOOKS_DIR/db.py summary`
- 读 `git log --oneline -5`
- 读 `git diff --stat`

### 2. 检查 CHECKLIST.md
- 逐项检查 `.ai/CHECKLIST.md`

### 3. 一致性检查
- 检查 state 表的关键条目是否过期
- 检查和当前 git 状态是否匹配

### 4. 建议
- state 过期 → 建议 `render_state.py --file`
- MEMORY.md 可追加 → 给出建议内容
- 新决策 → 建议追加 DECISIONS.md

### 5. 报告
```
=== ai-review ===
项目: {project_name}
状态: ✅ / ⚠
CHECKLIST: {n}/{total}
建议: ...
```

### 实现提示
- `$AI_HOOKS_DIR` 和 `$AI_HOOKS_PYTHON` 来自项目的 hooks.conf
- project.db 路径: `.ai/project.db`
- Python 工具路径: `$AI_HOOKS_DIR/db.py`, `$AI_HOOKS_DIR/render_state.py`

---
name: ai-review
description: Run .ai/ project state review — check consistency, review checklist, suggest MEMORY/STATUS updates after a work session
---

# ai-review

当用户要求 review / 检查工作 / 准备提交，或触发 `/ai-review` 时执行：

## 流程

### 1. 读取当前状态
- 读 `.ai/project.db` — 执行 `python F:/projects/.ai-hooks/db.py summary <db_path>`
- 读 `git log --oneline -5`
- 读 `git diff --stat`（如果有未提交变更）

### 2. 检查 CHECKLIST.md
- 逐项检查项目的 `.ai/CHECKLIST.md`
- 标记已满足和未满足的项目

### 3. 一致性检查
- 运行 `python F:/projects/.ai-hooks/db.py query <db_path> "SELECT COUNT(*) as cnt FROM events"`
- 检查 `state` 表的关键条目是否过期
- 检查 events 和 state 是否匹配

### 4. 建议
- 如果 state 过期 → 建议运行 `python F:/projects/.ai-hooks/render_state.py <db_path> --file`
- 如果 MEMORY.md 可以追加新条目 → 给出建议内容
- 如果需要提交 → 建议 commit message
- 如果发现有新的架构决策 → 建议追加到 DECISIONS.md

### 5. 报告
输出格式：
```
=== ai-review 报告 ===
项目: {project_name}
状态: ✅ 健康 / ⚠ 需注意

CHECKLIST 完成度: {n}/{total}

一致性: ✅ / ⚠ {issues}

建议:
- {suggestion 1}
- {suggestion 2}
```

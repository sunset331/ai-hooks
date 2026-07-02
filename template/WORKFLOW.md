# 开发工作流

## 开始
1. 读取 `.ai/`（STATUS.md → MEMORY.md → DECISIONS.md）
2. CLAUDE.md 已自动加载

## 开发中
- 每完成一个模块立即验证，不要全部写完一起 Debug

## 提交
- `git commit` → 自动记录事件到 project.db
- `git checkout` → 自动刷新 state 摘要
- 提交后 STATUS.md 自动更新

## 检查
- 输入 `/ai-review` 触发 review skill
- 参考 CHECKLIST.md

## 事件记录
- 完成重要任务后运行: `ai-log "做了什么，结果是什么"`
- 这会写入 event 到 project.db，下次 session 自动恢复上下文
- 无需手动记，完成后顺手敲一行即可

## 结束
- 更新 MEMORY.md 记录踩坑/修复/经验
- 必要时更新 DECISIONS.md

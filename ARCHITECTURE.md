# .ai-hooks — Architecture

> 基于事件溯源的 AI 协同开发基础设施。
> 把 AI 的"记忆"变成项目的一部分，而不是工具的一部分。

## 架构图

```
               Git commit / checkout
                      │
                      ▼
            ┌─────────────────┐
            │    Git Hooks     │  pre-commit (warning)
            │  (post-commit,   │  post-commit (record event)
            │   post-checkout) │  post-checkout (record event + summary)
            └────────┬────────┘
                     │ write event
                     ▼
            ┌─────────────────┐
            │    SQLite DB     │  events 表 (append-only)
            │  .ai/project.db  │  state 表 (KV, UPSERT)
            │                  │  schema_version (升级用)
            └────────┬────────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
   ┌──────────┐ ┌────────┐ ┌──────────┐
   │STATUS.md │ │session │ │scheduler │
   │(render)  │ │-start  │ │-check    │
   │          │ │(Claude │ │(Task     │
   │          │ │启动注入)│ │每日)     │
   └──────────┘ └────────┘ └──────────┘

  Claude Code ─── SessionStart hook ──→ 自动注入 state + events 到上下文
  Windows ─────── Task Scheduler ─────→ 每日健康检查 (只读, 永不 git commit)
  AI ─────────── /ai-review skill ────→ CHECKLIST 检查 + 一致性验证
```

## 目录结构

```
F:/projects/.ai-hooks/           # 共享基础设施 (一个 git repo)
├── hooks.conf                   # 环境变量 (AI_HOOKS_PYTHON, PYTHONUTF8)
├── db.py                        # SQLite 封装 (init/migrate/record/set/get/summary)
├── record_event.py              # CLI: 写事件
├── update_state.py              # CLI: 事件→state 聚合
├── render_state.py              # CLI: state→STATUS.md
├── session-start.sh             # Claude Code SessionStart hook
├── setup.sh (ai-init)           # 新项目一键配置
├── uninstall.sh (ai-uninstall)  # 撤销 setup.sh (保留 .ai/ 数据)
├── update.sh (ai-update)        # 升级配置路径 + schema
├── doctor.sh (ai-doctor)        # 诊断健康状态
├── check.sh                     # 快速检查
├── scheduler-check.ps1          # Windows Task Scheduler 每日检查
├── pre-commit                   # Git hook (warning only)
├── post-commit                  # Git hook (record commit + render)
├── post-checkout                # Git hook (record checkout + summary)
├── template/                    # 新项目模板文件
│   ├── STATUS.md
│   ├── MEMORY.md
│   ├── DECISIONS.md
│   ├── CHECKLIST.md
│   ├── WORKFLOW.md
│   ├── settings.json
│   └── ai-review/SKILL.md
└── tests/
    ├── test_core.sh             # 8 项核心测试 (临时 git repo)
    └── test_concurrency.py      # 10 线程并发测试
```

## 项目目录（每个项目独立）

```
<project>/
├── .ai/
│   ├── project.db       # SQLite (events + state 表)
│   ├── STATUS.md        # 从 state 渲染 (自动生成)
│   ├── MEMORY.md        # 踩坑记录 (人写)
│   ├── DECISIONS.md     # 架构决策 (人写)
│   ├── CHECKLIST.md     # 检查清单 (模板)
│   └── WORKFLOW.md      # 工作流 (模板)
├── .claude/
│   ├── settings.json    # SessionStart hook 配置
│   └── skills/ai-review/SKILL.md
└── .gitignore            # 包含 .ai/project.db
```

## 事件 Schema

所有事件存于 `events` 表，`event_version=1`:

| type | payload | 触发源 |
|------|---------|--------|
| commit | sha, message, date, author | post-commit hook |
| checkout | branch, from | post-checkout hook |
| ai_session | action, model, summary | Claude Code (手动调 record_event) |
| ai_action | action, file, description | Claude Code (手动调) |
| scheduler_check | status, dirty_count, warnings | Task Scheduler |
| pre_commit_scan | warnings_count, items | pre-commit hook |

## 数据流 (典型路径)

```
git commit -m "fix bug"
    → post-commit hook
        → record_event.py → events 表 +1
        → update_state.py → state.last_commit 更新
        → render_state.py → STATUS.md 重写
    → 终端: "OK .ai: commit event recorded, STATUS.md updated"

git checkout feature-branch
    → post-checkout hook
        → record_event.py → events 表 +1
        → update_state.py → state.current_branch 更新
        → render_state.py → STATUS.md 重写
    → 终端: "=== .ai 状态 ===" + 摘要

Claude Code 打开项目
    → SessionStart hook
        → db.py summary → 注入 state + 最近 5 条 events
    → 用户看到: 项目状态 + 最近事件 + 工作流提示

Task Scheduler 每天 10:07
    → scheduler-check.ps1
        → git status (只读)
        → check_consistency()
        → 过期 > 3 天 → Windows Toast
        → 不一致 → .ai/heal-patch-{date}.note (非自动执行)
        → record scheduler_check 事件
```

## 安装

```bash
python F:/projects/.ai-hooks/setup.sh /path/to/new-project
```

setup.sh 自动:
1. 创建 `.ai/` 目录 + 从 template/ 复制文件
2. `python db.py init` 初始化 SQLite
3. `git config core.hooksPath` (如果是 git repo)
4. 创建 `.claude/settings.json` (SessionStart hook)
5. 安装 ai-review skill
6. `.gitignore` 追加 `.ai/project.db`

## 升级

```bash
python F:/projects/.ai-hooks/db.py migrate /path/to/.ai/project.db
# 或
bash F:/projects/.ai-hooks/update.sh /path/to/project
```

`db.py migrate` 检测 `state.schema_version`:
- v0 → v1: 初始建表
- 未来 v1 → v2: 加 `ALTER TABLE`

不修改用户数据。

## 卸载

```bash
bash F:/projects/.ai-hooks/uninstall.sh /path/to/project
```

删除: core.hooksPath、settings hook 引用、skill
**保留**: `.ai/` 全部数据 (project.db + 所有 .md)

## 诊断

```bash
bash F:/projects/.ai-hooks/doctor.sh /path/to/project
```

检查: .ai/ 存在、project.db 可打开、hooks 配置正确、settings 有效

## 测试

```bash
# 核心功能测试 (8 项, 临时 git repo, 不污染现有项目)
AI_HOOKS_PYTHON="F:/miniconda3/python.exe" bash tests/test_core.sh

# 并发测试 (10 线程)
AI_HOOKS_PYTHON="F:/miniconda3/python.exe" python tests/test_concurrency.py
```

## 环境变量

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `AI_HOOKS_PYTHON` | `python` | Python 可执行文件路径 (scheduler 必须显式设置) |
| `AI_HOOKS_DIR` | 自动检测 | .ai-hooks 目录路径 |
| `PYTHONUTF8` | `1` (hooks.conf 强制) | Windows 下中文不乱码 |

## 设计原则

1. **每种事件必须有 consumer** — 无 consumer 的事件不记录 (砍掉 merge/rewrite)
2. **Git hooks 只写不阻** — 打 warning 但不 exit 1，stash/amend/rebase 不依赖 hook
3. **State 是 best-effort 聚合** — 不是确定性重放，接受一定的滞后
4. **Scheduler 只读永不写** — 不 git add/commit，不一致只生成 patch 文件
5. **SQLite busy_timeout=5000** — 处理并发写入，两个 Claude 同时跑不崩溃
6. **Schema version** — `state.schema_version` 保障未来升级

## FAQ

**Q: 去哪看数据？**
```bash
sqlite3 .ai/project.db "SELECT * FROM events"
sqlite3 .ai/project.db "SELECT * FROM state"
```

**Q: 两个 Claude 同时写同一个 project.db 会怎样？**
不会崩。busy_timeout=5000ms，第二个等第一个写完再写。

**Q: 我需要手动更新 STATUS.md？**
不用。post-commit 和 post-checkout 自动调用 `render_state.py --file`。
但 MEMORY.md 和 DECISIONS.md 需要你手动写。

**Q: 如果不用 Claude Code，这套系统还有用吗？**
Git hooks 和 Task Scheduler 完全独立于 Claude。但 SessionStart hook 和 ai-review skill 需要 Claude Code。
ChatGPT/Cursor/Codex 不识别 `.claude/` 配置，但能读懂 `.ai/` 里的 Markdown 文件。

**Q: 错误事件会被记录吗？**
是的。任何会导致 hook 失败的情况都被 `|| true` / `2>/dev/null` 兜底：DB 不存在时跳过，
JSON 解析失败时跳过，Python 找不到时跳过。系统不会因为 .ai/ 的问题阻塞你的 git 操作。

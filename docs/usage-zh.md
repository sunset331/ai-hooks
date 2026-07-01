---
创建: 2026-07-01
标签: [ai-hooks, devops, workflow, 基础设施]
---

# .ai-hooks 使用手册 v3

> **AI 协同开发基础设施** — 把 AI 的记忆变成项目的一部分。
>
> 核心理念：AI 负责推理，人负责决策；文档负责记忆，Git 负责历史。

---

## 目录

1. [这是什么](#1-这是什么)
2. [快速上手](#2-快速上手)
3. [命令体系](#3-命令体系)
4. [日常工作流](#4-日常工作流)
5. [文件说明](#5-文件说明)
6. [事件系统](#6-事件系统)
7. [数据流详解](#7-数据流详解)
8. [调试与诊断](#8-调试与诊断)
9. [故障排除](#9-故障排除)
10. [常见问题](#10-常见问题)

---

## 1. 这是什么

`.ai-hooks` 是一套**项目级 AI 协同基础设施**，作用是把 AI 的"记忆"从聊天窗口里搬进项目的文件系统中。

### 解决的问题

| 问题 | 以前 | 现在 |
|------|------|------|
| 关闭聊天窗口 → 所有上下文丢失 | 每次要重新读代码、回忆踩坑 | 自动注入项目状态到 AI 上下文 |
| 忘了清理 `__pycache__` 就提交 | Review 时才被发现 | pre-commit 自动 warning |
| 修过的 bug 下次又踩一遍 | 靠人脑记，下次忘 | MEMORY.md 永久记录 |
| 新 AI 工具接手项目从零开始 | Claude→GPT→Cursor 各自为战 | 所有 AI 读同一套 `.ai/` 文件 |
| 写 STATUS.md 忘了更新 | 手写 → drift | post-commit 自动渲染 |

### 架构概览

```
Git hooks ──→ SQLite ──→ STATUS.md (自动渲染)
Claude Code ──→ SessionStart hook (启动注入)
Windows ──→ Task Scheduler (每日检查, 只读)

命令: ai-init, ai-update, ai-doctor, ai-uninstall
```

---

## 2. 快速上手

### 2.1 新项目接入

```bash
bash F:/projects/.ai-hooks/setup.sh /path/to/your/project
```

这个命令会自动完成：

1. 创建 `.ai/` 目录 + 5 个模板文件
2. 初始化 SQLite 数据库
3. 配置 git hooks（如果是 git 项目）
4. 创建 `.claude/settings.json`（SessionStart hook）
5. 安装 ai-review skill
6. `.gitignore` 追加 `.ai/project.db`

### 2.2 验证

```bash
# 检查是否配置成功
bash F:/projects/.ai-hooks/doctor.sh /path/to/your/project

# 提交一次试运行
cd /path/to/your/project
echo "test" > test.txt
git add test.txt
git commit -m "test .ai hooks"
# 输出应包含: "OK .ai: commit event recorded, STATUS.md updated"
```

### 2.3 激活 Claude Code 配置

重新打开 Claude Code，你应该在顶部看到：

```
=== 项目状态 ===
分支: main
最后提交: test .ai hooks (abc12345)
工作区干净

最近事件:
  [2026-07-01 14:30] commit: test .ai hooks

=== 工作流提示 ===
...
```

---

## 3. 命令体系

| 命令 | 等价 | 用途 |
|------|------|------|
| `bash setup.sh <dir>` | ai-init | 新项目一键接入（幂等） |
| `bash uninstall.sh <dir>` | ai-uninstall | 移除 hook 配置，保留 `.ai/` 数据 |
| `bash update.sh <dir>` | ai-update | 升级 hooks 路径 + 数据库 schema |
| `bash doctor.sh <dir>` | ai-doctor | 诊断项目 .ai/ 健康状态 |
| `python db.py init <db>` | — | 初始化 SQLite |
| `python db.py migrate <db>` | — | 升级到最新 schema |
| `python db.py query <db> <sql>` | — | 执行 SQL 查询 |
| `python db.py summary <db>` | — | 打印状态摘要 |
| `python record_event.py <db> <type> <json> <project>` | — | 手动写事件 |
| `python render_state.py <db> --file` | — | 手动刷新 STATUS.md |
| `/ai-review` (Claude Code 内) | — | 触发 review skill |

### 3.1 setup.sh 详情

**幂等**：重复运行不会覆盖已有的 STATUS.md / MEMORY.md / DECISIONS.md。

```bash
# 完整用法
bash F:/projects/.ai-hooks/setup.sh /path/to/your/project

# 如果你项目还没有创建也可以
bash F:/projects/.ai-hooks/setup.sh /path/to/new-project-that-doesnt-exist-yet
```

### 3.2 uninstall.sh 详情

**保留 `.ai/` 数据**：只清除配置，不删你的记忆。

```bash
bash F:/projects/.ai-hooks/uninstall.sh /path/to/your/project
```

删除：
- `core.hooksPath`（如果是本系统设置的）
- `.claude/settings.json` 中的 SessionStart hook
- `ai-review` skill

保留：
- `.ai/` 整个目录（project.db + 所有 .md 文件）

### 3.3 doctor.sh 详情

诊断以下内容：
- `.ai/` 目录是否存在
- project.db 是否可打开
- `core.hooksPath` 是否配置正确
- `.claude/settings.json` 是否包含 SessionStart hook
- ai-review skill 是否安装
- `.gitignore` 是否包含 project.db
- 事件统计（总数、分类、state key 数）

---

## 4. 日常工作流

### 4.1 开始工作

```
1. 打开 Claude Code
   → 自动看到项目状态 + 最近事件
2. 读 MEMORY.md (踩坑记录)
3. 读 DECISIONS.md (架构决策)
4. 开始写代码
```

### 4.2 开发中

- 每完成一个模块**立即验证**，不要全部写完一起 Debug
- `git checkout <branch>` → 自动输出分支状态摘要

### 4.3 提交

```
git commit -m "fix: xpinn weight transpose bug"
│
├→ post-commit hook (自动)
│   ├→ 写 commit 事件到 SQLite
│   ├→ 刷新 state.last_commit
│   ├→ 自动更新 STATUS.md
│   └→ 输出 "OK .ai: commit event recorded"
│
└→ 手动（可选）
    ├→ 更新 MEMORY.md（踩坑记录）
    └→ 必要时更新 DECISIONS.md（架构决策）
```

### 4.4 检查

```
在 Claude Code 中输入: /ai-review
→ 自动检查 CHECKLIST
→ 检查一致性
→ 建议 MEMORY/STATUS 更新
```

### 4.5 每天结束

```
git status → 确认无 dirty files
更新 MEMORY.md:
  - 今天做了什么
  - 踩了什么坑
  - 下一步计划
```

---

## 5. 文件说明

### 5.1 `.ai/` 目录

| 文件 | 生成方式 | 更新频率 | 用途 |
|------|---------|---------|------|
| `project.db` | `setup.sh init` | 每次提交/切换 | SQLite 数据库 (events + state 表) |
| `STATUS.md` | `render_state.py` 自动 | 每次提交/切换 | 当前项目状态（自动生成，不要手改） |
| `MEMORY.md` | 手动 | 每天 | 踩坑记录、修复经验、里程碑 |
| `DECISIONS.md` | 手动 | 新决策时 | 架构选择与理由 |
| `CHECKLIST.md` | `setup.sh` 复制模板 | 项目扩展时 | 开发/提交/发布检查项 |
| `WORKFLOW.md` | `setup.sh` 复制模板 | 很少 | 项目特定工作流 |

> **⚠ 重要**：STATUS.md 是自动生成的。改它会被下一次提交覆盖。
> 想记录东西写到 MEMORY.md 和 DECISIONS.md。

### 5.2 `.claude/` 项目配置

| 文件 | 用途 |
|------|------|
| `.claude/settings.json` | SessionStart hook（启动时自动注入上下文） |
| `.claude/skills/ai-review/SKILL.md` | `/ai-review` 技能定义 |

---

## 6. 事件系统

### 6.1 数据库表

**events 表（append-only）**:

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增 ID
  event_version INTEGER DEFAULT 1,        -- schema 版本
  created_at TEXT,                         -- ISO 8601 UTC
  type TEXT,                               -- commit / checkout / ai_session ...
  payload TEXT,                            -- JSON
  project TEXT                             -- 项目名
);
```

**state 表（KV 模式）**:

```sql
CREATE TABLE state (
  key TEXT PRIMARY KEY,
  value TEXT,       -- JSON
  updated_at TEXT
);
```

### 6.2 事件类型

| 类型 | 触发源 | payload | 消费者 |
|------|--------|---------|--------|
| `commit` | post-commit hook | `{sha, message, date, author}` | SessionStart 展示 |
| `checkout` | post-checkout hook | `{branch, from}` | SessionStart 展示 |
| `ai_session` | Claude Code 手动调 | `{action, model, summary}` | SessionStart 展示 |
| `scheduler_check` | Task Scheduler | `{status, dirty_count, warnings}` | SessionStart 展示 + heal |
| `pre_commit_scan` | pre-commit hook | `{warnings_count, items}` | 分析用 |

### 6.3 查询

```bash
# 查看全部事件
sqlite3 .ai/project.db "SELECT id, type, substr(payload,1,60) FROM events"

# 查看最近 5 条
sqlite3 .ai/project.db "SELECT * FROM events ORDER BY id DESC LIMIT 5"

# 查看 state
sqlite3 .ai/project.db "SELECT * FROM state"

# 通过 db.py 查询
python F:/projects/.ai-hooks/db.py query .ai/project.db "SELECT count(*) FROM events"
```

---

## 7. 数据流详解

### 7.1 提交代码

```
你: git commit -m "fix: bug"
    │
    ▼
pre-commit: 扫描 __pycache__ / .pyc
    │  └→ 有 warning → 终端输出 (不阻止)
    │
    ▼
post-commit:
    ├→ record_event.py → events 表 (commit, sha, message, ...)
    ├→ update_state.py → state.last_commit = {sha, message, date}
    ├→ render_state.py --file → STATUS.md 重写
    └→ 终端: "OK .ai: commit event recorded"
```

### 7.2 切换分支

```
你: git checkout feature-x
    │
    ▼
post-checkout:
    ├→ record_event.py → events 表 (checkout, branch="feature-x")
    ├→ update_state.py → state.current_branch = "feature-x"
    ├→ render_state.py --file → STATUS.md 重写
    └→ 终端: "=== .ai 状态 ===" + 摘要
```

### 7.3 Claude Code 启动

```
Claude Code 打开项目
    │
    ▼
.claude/settings.json → SessionStart hook
    │
    ▼
session-start.sh:
    └→ db.py summary → 输出到 Claude 上下文:
        - 分支
        - 最后提交
        - dirty files
        - 上次 AI 操作
        - 最近 5 条事件
        - 工作流提示
```

### 7.4 Task Scheduler 每日检查

```
Windows 每天 10:07 / 10:10
    │
    ▼
scheduler-check.ps1:
    ├→ git status (只读)
    ├→ 读 state 检查过期
    ├→ check_consistency()
    ├→ 有 warning → Windows Toast 通知
    ├→ 不一致 → .ai/heal-patch-{date}.note (不自动执行)
    └→ record_event → scheduler_check 事件
```

---

## 8. 调试与诊断

### 8.1 快速检查

```bash
bash F:/projects/.ai-hooks/check.sh
```

### 8.2 完整诊断

```bash
bash F:/projects/.ai-hooks/doctor.sh /path/to/project
```

输出示例：
```
=== .ai-doctor: music-player ===
  [OK] .ai/ 目录存在
  [OK] project.db 可正常打开
  [OK] core.hooksPath 指向本系统
  [OK] .claude/settings.json 包含 SessionStart hook
  [OK] ai-review skill 已安装
  [OK] .gitignore 包含 .ai/project.db

  事件总数: 3
    commit: 2
    checkout: 1
  state keys: 5

✅ .ai/ 系统健康
```

### 8.3 手动写事件

```bash
python F:/projects/.ai-hooks/record_event.py \
  .ai/project.db \
  ai_session \
  '{"action":"debug","model":"claude","summary":"手动测试"}' \
  project-name
```

### 8.4 手动刷新 STATUS.md

```bash
python F:/projects/.ai-hooks/render_state.py .ai/project.db --file
```

### 8.5 升级 schema

```bash
python F:/projects/.ai-hooks/db.py migrate .ai/project.db
```

---

## 9. 故障排除

### 9.1 git commit 后没有 "OK .ai: ..."

```
可能原因:
1. project.db 不存在 — 检查 .ai/project.db 是否存在
2. hooks path 不对 — 运行 doctor.sh 检查
3. Python 不在 PATH — 设置 AI_HOOKS_PYTHON 环境变量

检查:
  git config core.hooksPath        # 应该输出 F:/projects/.ai-hooks
  ls -la .ai/project.db            # 应该存在
```

### 9.2 中文乱码 / ??? 文字

```
原因: Windows 终端编码 (GBK) 与数据编码 (UTF-8) 不一致
影响: 仅终端显示乱码，SQLite 内数据是 UTF-8 正确的

修复终端显示:
  PYTHONUTF8=1 python ...   # 或已由 hooks.conf 自动处理

验证数据完整性:
  PYTHONUTF8=1 python -c "
  import sqlite3, json
  c = sqlite3.connect('.ai/project.db')
  r = c.execute('SELECT payload FROM events LIMIT 1').fetchone()
  print(r[0])  # 应显示正确中文
  "
```

### 9.3 project.db 被误删

不会崩。下次 `git commit` hook 检测到 DB 不存在就跳过（exit 0）。

恢复：重新 init 即可。

```bash
python F:/projects/.ai-hooks/db.py init .ai/project.db
```

事件记录会丢失，但 `.md` 文件仍在。

### 9.4 SessionStart hook 没生效

```
1. 检查 .claude/settings.json 是否存在且包含 session-start.sh
2. 确认路径是绝对路径（不要用相对路径）
3. 重新打开 Claude Code（hook 只在启动时触发）
4. 运行 doctor.sh 检查配置
```

### 9.5 Task Scheduler 不工作

```
1. 确认脚本路径正确:
   schtasks /query /tn ".ai-health-music-player"
2. 确认 Python 路径正确（scheduler 需要显式指定 Python 路径）
3. 手动运行测试:
   powershell -ExecutionPolicy Bypass -File F:/projects/.ai-hooks/scheduler-check.ps1 -ProjectDir F:/projects/your-project
```

### 9.6 两个 Claude 同时写 project.db

不会崩。SQLite WAL 模式 + `busy_timeout=5000ms`，第二个进程会等第一个写完。

---

## 10. 常见问题

### Q: 这套系统依赖 Claude Code 吗？

不完全是。
- **Git hooks**（post-commit / post-checkout）— 完全独立，任何 git 操作都会触发
- **Task Scheduler** — 完全独立，Windows 级别的定时任务
- **SessionStart hook** — 需要 Claude Code
- **ai-review skill** — 需要 Claude Code
- **.ai/ 目录** — 任何 AI 工具都能读懂（纯 Markdown）

### Q: GPT / Cursor / Codex 能用吗？

GPT/Cursor 不识别 `.claude/` 配置，但 `.ai/` 目录里的 Markdown 文件任何 AI 都能读懂。建议：
- 开始工作时告诉 AI："先读 .ai/ 目录下的所有文件"
- `.ai/` 的明文 Markdown 是跨 AI 工具的通用记忆层

### Q: 我需要手动更新 STATUS.md 吗？

不需要。`post-commit` 和 `post-checkout` 自动调用 `render_state.py --file`。

但 **MEMORY.md** 和 **DECISIONS.md** 需要你手动写。

### Q: 要迁移到新电脑怎么办？

```bash
# 新电脑上
git clone .ai-hooks 仓库到某个目录
bash setup.sh /path/to/project
```

project.db 不带（它是本地缓存），但 .ai/*.md（MEMORY/DECISIONS）建议入 git。

### Q: `项目名/.ai/` 应该入 git 吗？

建议：
- `project.db` → **不入 git**（已在 .gitignore 中）
- `STATUS.md` → **可入**（自动生成，但入 git 能看到历史）
- `MEMORY.md` → **建议入 git**（这是你的长期记忆）
- `DECISIONS.md` → **建议入 git**（架构决策历史）
- `CHECKLIST.md` + `WORKFLOW.md` → **建议入 git**

### Q: 项目间快速切换会怎样？

每次切换项目，Claude Code 关闭后再打开：
1. SessionStart hook 自动注入该项目的最新 state
2. 不需要手动读任何文件就能进入工作状态

### Q: 以后 schema 升级怎么办？

```bash
bash F:/projects/.ai-hooks/update.sh /path/to/project
```

这个命令不会改你的数据，只会：
- 更新 `core.hooksPath` 到新路径
- 更新 `.claude/settings.json` 的路径
- 运行 `db.py migrate` 升级数据库 schema

---

> **最后更新**: 2026-07-01
> **当前版本**: v3.0
> **仓库位置**: `F:/projects/.ai-hooks/`
> **配置文件**: `F:/projects/.ai-hooks/hooks.conf`

# ai-hooks — Persistent Project Memory for AI Coding

```text
AI loses memory between sessions.
This project fixes that.
```

Close Claude Code. All context gone. Switch projects. Re-read everything. Pick up a repo after a week. Start from zero.

**ai-hooks gives Claude Code persistent project memory.** It records every commit, checkout, and AI action as events in SQLite, auto-injects them when you start a session, and keeps STATUS.md always current.

No cloud. No API. No vendor lock-in. Just a Bash script, a Python SQLite wrapper, and git hooks.

```text
git commit
    │
    ▼
SQLite Events ──→ Project State ──→ Claude Session (auto-injected on start)
                                      → STATUS.md (auto-rendered)
```

## Quick Start

```bash
# 1. One command to install
git clone https://github.com/sunset331/ai-hooks.git
cd ai-hooks && bash install.sh

# 2. Quick start options:

#   Option A: Create a new project (git + ai in one step)
ai-new my-project
cd ~/projects/my-project

#   Option B: Add to an existing project
ai-init ~/my-project

# 3. Work normally. That's it.
git commit -m "fix: login bug"      # → event + state auto-recorded
git checkout feature-branch         # → state summary printed
ai-log "BPINNs DCU 验证完成"        # → record non-commit milestones
# next Claude Code session → Smart Resume with context
```

| Situation | Without ai-hooks | With ai-hooks |
|-----------|-----------------|---------------|
| Close Claude Code | Lose all context | Auto-injected next session |
| Switch projects | Re-read everything | Smart Resume picks up where you left off |
| STATUS.md outdated | Drift, stale | Auto-rendered every commit |
| State corrupted | Manual recovery | `doctor --repair` auto-rebuilds from events |
| `__pycache__` in commit | Caught at PR review | Warning at commit time |
| New AI tool joins | Starts from zero | Reads same `.ai/` files |

## Architecture

```
.ai/                           # Per-project (created by ai-init)
├── project.db                 # SQLite — events + state
├── STATUS.md                  # Auto-rendered (read-only)
├── MEMORY.md                  # You write: bugs, fixes, milestones
├── DECISIONS.md               # You write: architecture rationale
├── CHECKLIST.md               # Review checklist
└── WORKFLOW.md                # Project workflow

.claude/
├── settings.json              # SessionStart hook for context injection
└── skills/ai-review/SKILL.md  # /ai-review command

Data flow:
    git commit → post-commit hook
        → record_event.py → SQLite events (append-only)
        → update_state.py → SQLite state (KV, upsert)
        → render_state.py → STATUS.md (overwrite)
    next Claude start → SessionStart hook → db.py summary → context
    daily → Task Scheduler → scheduler-check.ps1 → health check (read-only)
```

## Commands

| Command | Description |
|---------|-------------|
| `ai-new <name>` | Create a new project with git + .ai in one command |
| `ai-init <dir>` | Initialize `.ai/` system in a project (idempotent) |
| `ai-doctor <dir>` | Diagnose `.ai/` health |
| `ai-doctor --repair <dir>` | Diagnose + auto-rebuild state |
| `ai-update <dir>` | Upgrade hooks path + DB schema |
| `ai-uninstall <dir>` | Remove hook config (keeps `.ai/` data) |
| `ai-log <summary>` | Record a milestone event (git fallback if empty) |
| `ai-backfill <db>` | Backfill commit events from git log |

## Events

Every state change is an append-only event. No data loss, full audit trail.

| Type | Trigger | Payload |
|------|---------|---------|
| `commit` | post-commit hook | `{sha, message, date, author}` |
| `checkout` | post-checkout hook | `{branch, from}` |
| `ai_session` | `ai-log` command | `{summary}` |
| `scheduler_check` | Task Scheduler | `{status, dirty_count, warnings}` |

```bash
sqlite3 .ai/project.db "SELECT id, type, payload FROM events"
```

## Who Is This For

- **You use Claude Code daily** and hate losing context between sessions
- **You juggle multiple projects** and need instant state recovery
- **You want your AI memory to outlive any specific tool**
- **You care about engineering fundamentals** — events, state, SQLite — not prompt hacks

## Requirements

- Bash 4+
- Python 3.8+ (with sqlite3)
- Git (optional: hooks need it, `.ai/` files work without)

## Supported AI Tools

- **Claude Code** — Full support (hooks, sessions, skill)
- **Any AI** — `.ai/` is plain Markdown + SQLite, zero dependency on any provider

## License

MIT

---

*[中文使用手册](https://github.com/sunset331/ai-hooks/blob/master/docs/usage-zh.md)* — 完整的中文文档

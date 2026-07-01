# ai-hooks — Persistent Project Memory for AI Coding

> Keep your AI's memory in the project, not in the chat window.
>
> `ai-hooks` is a lightweight runtime that persists AI coding session context across commits, branches, tools, and shutdowns — using git hooks, SQLite events, and Claude Code integration.

```text
         git commit
              │
              ▼
       SQLite Events
              │
              ▼
       Project State
              │
     ┌────────┴────────┐
     ▼                 ▼
Claude Session    STATUS.md (auto-rendered)
(startup inject)   (always current)
```

## Quick Start

```bash
# 1. Clone anywhere
git clone https://github.com/sunset331/ai-hooks.git
cd ai-hooks

# 2. Install global commands
bash install.sh

# 3. Add to your project
ai-init ~/my-project

# 4. Done. Every git commit now automatically:
#    - Records commit/checkout events to SQLite
#    - Updates project state
#    - Renders STATUS.md
```

## What It Does

| Situation | Without ai-hooks | With ai-hooks |
|-----------|-----------------|---------------|
| Close Claude Code | All context lost | Auto-injected on next start |
| Switch projects | Re-read everything | Branch state auto-restored |
| Forgot to update STATUS.md | Drift, stale info | Auto-rendered on every commit |
| New AI tool joins | Starts from zero | Reads the same `.ai/` files |
| `__pycache__` in commit | Caught at review | Warning at commit time |

## Architecture

```
.ai/                           # Per-project (created by ai-init)
├── project.db                 # SQLite — events (append-only) + state (KV)
├── STATUS.md                  # Auto-rendered from state (do not edit)
├── MEMORY.md                  # Bugs, fixes, milestones (you write)
├── DECISIONS.md               # Architecture decisions (you write)
├── CHECKLIST.md               # Review checklist (template)
└── WORKFLOW.md                # Workflow (template)

.claude/
├── settings.json              # SessionStart hook (injects context)
└── skills/ai-review/SKILL.md  # /ai-review skill

.gitignore                     # .ai/project.db added automatically
```

## Commands

| Command | Description |
|---------|-------------|
| `ai-init <dir>` | Setup `.ai/` system for a project (idempotent) |
| `ai-doctor <dir>` | Diagnose `.ai/` health |
| `ai-update <dir>` | Upgrade hooks path + DB schema |
| `ai-uninstall <dir>` | Remove hook config, keep `.ai/` data |

## Events

All state changes are recorded as events in SQLite. Events are append-only and versioned.

| Type | Source | Payload |
|------|--------|---------|
| `commit` | post-commit hook | `{sha, message, date, author}` |
| `checkout` | post-checkout hook | `{branch, from}` |
| `ai_session` | Claude Code | `{action, model, summary}` |
| `scheduler_check` | Task Scheduler | `{status, dirty_count, warnings}` |

```bash
# Query events directly
sqlite3 .ai/project.db "SELECT id, type, substr(payload,1,60) FROM events"
```

## Supported AI Tools

- **Claude Code** — Full support (hooks, sessions, skill)
- **ChatGPT / Cursor / Codex** — Can read `.ai/` Markdown files manually
- **Any future AI** — `.ai/` is plain Markdown + SQLite, zero vendor lock-in

## Requirements

- Bash 4+
- Python 3.8+ (with sqlite3)
- Git (optional: without git, hooks won't fire, but `.ai/` still works)

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — Full architecture and data flow
- [設計笔记](../F:/Desktop/笔记/.ai-hooks使用手册.md) — 中文使用手册 (Obsidian)

## License

MIT

# Changelog

## v3.2.0 (2026-07-02)

- [feat] `ai-backfill` — retroactive event reconstruction from git log (with noise filtering)
- [feat] `ai-backfill --audit` — detect time periods with file changes but no events
- [feat] `ai-backfill --audit --fix` — create events for detected gaps
- [feat] `ai-log` command — quick event recording from any project directory
- [feat] `ai-new` command — one-command project creation (git init + ai-init)
- [feat] `db.py events` — timeline display with `--today` and `--since DATE`
- [feat] SessionStart prompt now includes "事件记录" usage guide
- [fix] `doctor.sh` SQL injection in db path (sys.argv instead of inline)
- [portable] All bin/ scripts self-locate; ai-new uses `$AI_NEW_DIR` env var
- [test] 34 pytest + 24 shell tests, all passing

## v3.1.0 (2026-07-02)

- [refactor] Extract pure `reduce(state, event) -> state` function — the single source of truth for state projection
- [refactor] `update_state.py` now uses the shared reducer and accepts `event_id` param (no more `ORDER BY DESC LIMIT 1`)
- [feat] `set_all_state()` for atomic batch state writes with `busy_timeout=1000` + auto-retry
- [feat] `rebuild_state.py` — full event replay from SQLite: `--strict` debug mode, `--diff` dry-run
- [feat] `doctor.sh --repair` — auto-rebuild state when consistency issues detected
- [feat] Smart Resume (`generate_resume()`) — Claude sees "what you did last session" instead of raw key-value dump
- [feat] SessionStart hook now outputs project summary + last session + suggested next steps
- [fix] State consistency: `record_event` + `update_state` now passes `event_id` instead of racing on `LIMIT 1`
- [fix] Git hook guards: `2>/dev/null || true` on all critical paths (no more false failure propagation)
- [fix] `pre-commit` JSON built via `sys.argv` instead of shell interpolation (was vulnerable to special chars)
- [fix] `summary()` uses relative timestamps ("3 小时前") instead of raw ISO
- [test] 18 reducer unit tests + 9 rebuild/idempotent tests = 30 pytest + 22 shell tests, all passing

## v3.0.0 (2026-07-01)

- Event-driven architecture with SQLite (events + state tables)
- `setup.sh` (ai-init) — one-command project provisioning
- `install.sh` — global command installation
- `uninstall.sh` — clean removal preserving `.ai/` data
- `update.sh` — schema migration and path upgrades
- `doctor.sh` — health diagnostics
- Git hooks: pre-commit (warning only), post-commit (event record), post-checkout (state refresh)
- Claude Code SessionStart hook for automatic context injection
- `ai-review` skill for `/ai-review` command
- Windows Task Scheduler integration (read-only daily checks)
- Concurrent write safety (SQLite WAL + busy_timeout=5000)
- Chinese text encoding support (PYTHONUTF8=1)
- JSON-safe commit messages (Python dumps instead of shell interpolation)
- Automatic STATUS.md rendering
- Schema versioning for future upgrades
- Template-based project scaffolding
- Comprehensive test suite (22 core tests + concurrency tests)

## v2.0.0 (2026-06-30)

- Basic `.ai/` directory structure (STATUS.md, MEMORY.md, DECISIONS.md, CHECKLIST.md, WORKFLOW.md)
- First SQLite-based event recording
- Git hooks with core.hooksPath configuration

## v1.0.0 (2026-06-28)

- Initial concept: manual workflow documentation in `.ai/`

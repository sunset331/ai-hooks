# Changelog

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

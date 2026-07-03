#!/bin/bash
# self-check.sh — 自检 + 自修复（只做安全幂等操作）
#
# 输出: JSON Lines，每条: {"check":"...","status":"...","message":"..."}
#
# 安全修复: project.db, schema, git hooks(版本+路径), settings(merge), gitignore
# 只告警: state 不一致
# 绝不自动: rebuild state, 覆盖用户配置, 删除数据

set -uo pipefail

AI_HOOKS_VERSION="3.1.2"
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR"
PROJECT_DIR="$(cd "$1" 2>/dev/null && pwd || exit 0)"
AI_DIR="$PROJECT_DIR/.ai"
DB="$AI_DIR/project.db"
PYTHON="${AI_HOOKS_PYTHON:-python}"
RESULTS=()

json_out() {
    local check="$1" status="$2" msg="${3:-}"
    if [ -n "$msg" ]; then
        echo "{\"check\":\"$check\",\"status\":\"$status\",\"message\":\"$msg\"}"
    else
        echo "{\"check\":\"$check\",\"status\":\"$status\"}"
    fi
}

# ── 1. .ai/ + project.db ────────────────────────────────────
if [ ! -d "$AI_DIR" ]; then
    mkdir -p "$AI_DIR"
fi

if [ ! -f "$DB" ]; then
    if [ -f "$HOOKS_DIR/db.py" ]; then
        "$PYTHON" "$HOOKS_DIR/db.py" init "$DB" 2>/dev/null && \
            json_out "project_db" "fixed" "initialized" || \
            json_out "project_db" "fail" "init failed"
    fi
else
    json_out "project_db" "ok"
    "$PYTHON" "$HOOKS_DIR/db.py" migrate "$DB" >/dev/null 2>&1 || true
fi

# ── 2. Git hooks: 存在性 + 版本 + AI_HOOKS_DIR 路径 ─────────
if [ -d "$PROJECT_DIR/.git/hooks" ]; then
    HOOK_FIXED=false
    for h in pre-commit post-commit post-checkout; do
        TARGET="$PROJECT_DIR/.git/hooks/$h"
        SOURCE="$HOOKS_DIR/$h"
        NEED_REPLACE=false

        if [ ! -f "$TARGET" ]; then
            NEED_REPLACE=true
        else
            # 检查版本
            HOOK_VER=$(grep "AI_HOOKS_VERSION=" "$TARGET" 2>/dev/null | head -1 | sed 's/.*=//')
            if [ "$HOOK_VER" != "$AI_HOOKS_VERSION" ]; then
                NEED_REPLACE=true
            fi
            # 检查 AI_HOOKS_DIR 路径
            if grep -q "AI_HOOKS_DIR" "$TARGET" 2>/dev/null; then
                REF_DIR=$(grep "HOOKS_DIR\|$(basename $HOOKS_DIR)" "$TARGET" 2>/dev/null | head -1 || true)
                if [ -n "$REF_DIR" ] && [ ! -d "$REF_DIR" ]; then
                    NEED_REPLACE=true
                fi
            fi
        fi

        if [ "$NEED_REPLACE" = true ] && [ -f "$SOURCE" ]; then
            cp "$SOURCE" "$TARGET" && chmod +x "$TARGET" && HOOK_FIXED=true
        fi
    done
    if [ "$HOOK_FIXED" = true ]; then
        json_out "git_hooks" "fixed" "version=$AI_HOOKS_VERSION"
    else
        json_out "git_hooks" "ok"
    fi
fi

# ── 3. settings.json: merge（不覆盖） ─────────────────────────
CLAUDE_DIR="$PROJECT_DIR/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"
mkdir -p "$CLAUDE_DIR"

if [ ! -f "$SETTINGS" ]; then
    cat > "$SETTINGS" << EOFSETTINGS
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOOKS_DIR/session-start.sh\"",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
EOFSETTINGS
    json_out "settings" "fixed" "created"
elif ! grep -q "session-start.sh" "$SETTINGS" 2>/dev/null; then
    # merge: 追加 SessionStart 到已有 settings
    "$PYTHON" -c "
import json, sys
settings_path = sys.argv[1]
hooks_dir = sys.argv[2]
with open(settings_path) as f:
    cfg = json.load(f)
hooks = cfg.setdefault('hooks', {})
ss = hooks.setdefault('SessionStart', [])
for entry in ss:
    for h in entry.get('hooks', []):
        cmd = h.get('command', '')
        if 'session-start.sh' in cmd:
            sys.exit(0)
ss.append({
    'hooks': [{
        'type': 'command',
        'command': 'bash \"%s/session-start.sh\"' % hooks_dir,
        'timeout': 5000
    }]
})
with open(settings_path, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print('merged')
" "$SETTINGS" "$HOOKS_DIR" 2>/dev/null && json_out "settings" "fixed" "merged SessionStart" || \
    json_out "settings" "warn" "merge failed"
else
    json_out "settings" "ok"
fi

# ── 4. .gitignore ──────────────────────────────────────────
GITIGNORE="$PROJECT_DIR/.gitignore"
if [ -f "$GITIGNORE" ]; then
    if ! grep -q ".ai/project.db" "$GITIGNORE" 2>/dev/null; then
        echo "" >> "$GITIGNORE"
        echo ".ai/project.db" >> "$GITIGNORE"
        json_out "gitignore" "fixed" "appended .ai/project.db"
    else
        json_out "gitignore" "ok"
    fi
else
    echo ".ai/project.db" > "$GITIGNORE"
    json_out "gitignore" "fixed" "created"
fi

# ── 5. state 一致性（只告警，不修复） ─────────────────────────
if [ -f "$DB" ]; then
    STATE_CHECK=$("$PYTHON" -c "
import sqlite3, json, sys
conn = sqlite3.connect(sys.argv[1])
e = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
r = conn.execute(\"SELECT value FROM state WHERE key='last_event_id'\").fetchone()
lid = int(json.loads(r[0])) if r and r[0] and r[0] != 'null' else 0
conn.close()
if e > 0 and lid > 0 and e > lid:
    print('stale')
else:
    print('ok')
" "$DB" 2>/dev/null || echo "error")
    case "$STATE_CHECK" in
        ok) json_out "state" "ok" ;;
        stale) json_out "state" "warning" "events > last_event_id" ;;
        error) json_out "state" "check_fail" "state check error" ;;
    esac
fi

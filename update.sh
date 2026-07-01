#!/bin/bash
# update.sh (ai-update) — 升级项目的 .ai-hooks 配置
# 用法: bash update.sh /path/to/project
# 不修改 STATUS / MEMORY / DECISIONS

. "$(dirname "$0")/hooks.conf"

PROJECT_DIR="$(cd "$1" 2>/dev/null && pwd || { echo "目录不存在: $1"; exit 1; })"

echo "=== .ai-hooks update ==="
echo "项目: $PROJECT_DIR"
echo "Hooks: $AI_HOOKS_DIR"

# 1. 更新 core.hooksPath
if [ -d "$PROJECT_DIR/.git" ]; then
    CURRENT_HOOKS=$(cd "$PROJECT_DIR" && git config --get core.hooksPath 2>/dev/null || echo "")
    PARENT_DIR="$(dirname "$AI_HOOKS_DIR")"
    if echo "$CURRENT_HOOKS" | grep -q "$PARENT_DIR" 2>/dev/null; then
        cd "$PROJECT_DIR" && git config core.hooksPath "$AI_HOOKS_DIR"
        echo "  [1] core.hooksPath 更新为 $AI_HOOKS_DIR"
    else
        echo "  [1] core.hooksPath 跳过（非本系统管理）"
    fi
fi

# 2. 更新 .claude/settings.json 路径
SETTINGS="$PROJECT_DIR/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
    "$AI_HOOKS_PYTHON" -c "
import json
with open('$SETTINGS', 'r', encoding='utf-8') as f:
    cfg = json.load(f)
def update_cmds(obj, new_path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'command' and isinstance(v, str):
                # 替换任何指向旧 hooks 目录的路径
                obj[k] = new_path + '/session-start.sh'
            else:
                update_cmds(v, new_path)
    elif isinstance(obj, list):
        for item in obj:
            update_cmds(item, new_path)
# 只替换包含 session-start.sh 的 command
def fix_session_start(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'command' and isinstance(v, str) and 'session-start.sh' in v:
                obj[k] = 'bash \"$AI_HOOKS_DIR/session-start.sh\"'
            else:
                fix_session_start(v)
    elif isinstance(obj, list):
        for item in obj:
            fix_session_start(item)
fix_session_start(cfg)
with open('$SETTINGS', 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print('  [2] settings.json hook 路径已更新')
" 2>/dev/null || echo "  [2] settings.json 未修改"
fi

# 3. SQLite migrate
DB="$PROJECT_DIR/.ai/project.db"
if [ -f "$DB" ]; then
    "$AI_HOOKS_PYTHON" "$AI_HOOKS_DIR/db.py" migrate "$DB"
    echo "  [3] project.db schema 已更新"
fi

echo "=== 更新完成 ==="

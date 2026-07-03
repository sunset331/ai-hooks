#!/bin/bash
# doctor.sh (ai-doctor) — 诊断 .ai/ 系统健康状态
# 用法: bash doctor.sh /path/to/project

. "$(dirname "$0")/hooks.conf"

REPAIR_MODE=false
[ "${1:-}" = "--repair" ] && REPAIR_MODE=true && shift

PROJECT_DIR="$(cd "$1" 2>/dev/null && pwd || { echo "目录不存在: $1"; exit 1; })"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

echo "=== ai-doctor: $PROJECT_NAME ==="
echo ""

ISSUES=0
DB="$PROJECT_DIR/.ai/project.db"

# 1. .ai/ 目录
if [ -d "$PROJECT_DIR/.ai" ]; then
  echo "  [OK] .ai/ 目录存在"
else
  echo "  [FAIL] .ai/ 目录不存在"; ISSUES=$((ISSUES + 1))
fi

# 2. project.db 可读写 + schema 正确
if [ -f "$DB" ]; then
  SCHEMA_OK=$("$AI_HOOKS_PYTHON" -c "
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
ecols = set(r[1] for r in conn.execute('PRAGMA table_info(events)').fetchall())
scols = set(r[1] for r in conn.execute('PRAGMA table_info(state)').fetchall())
required_e = {'id','type','payload','created_at','project'}
required_s = {'key','value','updated_at'}
e_ok = required_e.issubset(ecols)
s_ok = required_s.issubset(scols)
print('OK' if e_ok and s_ok else 'FAIL-events' if not e_ok else 'FAIL-state')
" "$DB" 2>/dev/null || echo "FAIL"
)
  if [ "$SCHEMA_OK" = "OK" ]; then
    echo "  [OK] project.db 可读写，events/state 表 schema 正确"
  else
    echo "  [WARN] project.db schema 异常 ($SCHEMA_OK)"
  fi
else
  echo "  [FAIL] project.db 不存在"; ISSUES=$((ISSUES + 1))
fi

# 3. Git hooks 已安装
if [ -d "$PROJECT_DIR/.git" ]; then
  PRE_COMMIT="$PROJECT_DIR/.git/hooks/pre-commit"
  POST_COMMIT="$PROJECT_DIR/.git/hooks/post-commit"
  POST_CHECKOUT="$PROJECT_DIR/.git/hooks/post-checkout"
  if [ -f "$PRE_COMMIT" ] && [ -f "$POST_COMMIT" ]; then
    echo "  [OK] Git hooks: pre-commit + post-commit 已安装"
  else
    echo "  [FAIL] Git hooks 缺失: pre-commit, post-commit 未安装"; ISSUES=$((ISSUES + 1))
  fi
  if [ -f "$POST_CHECKOUT" ]; then
    echo "  [OK] Git hooks: post-checkout 已安装"
  else
    echo "  [WARN] Git hooks: post-checkout 未安装（可选）"
  fi
else
  echo "  [WARN] 非 git 项目，跳过 hooks 检查"
fi

# 4. .claude/settings.json SessionStart hook
SETTINGS="$PROJECT_DIR/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
  if grep -q "session-start.sh" "$SETTINGS" 2>/dev/null; then
    echo "  [OK] .claude/settings.json 包含 SessionStart hook"
  else
    echo "  [WARN] .claude/settings.json 中未找到 session-start.sh 引用"
  fi
else
  echo "  [FAIL] .claude/settings.json 不存在"; ISSUES=$((ISSUES + 1))
fi

# 5. ai-log 可调用
if command -v ai-log &>/dev/null; then
  echo "  [OK] ai-log 命令可用"
else
  echo "  [FAIL] ai-log 不在 PATH 中（建议添加）"; ISSUES=$((ISSUES + 1))
fi

# 6. .gitignore
if [ -f "$PROJECT_DIR/.gitignore" ]; then
  if grep -q ".ai/project.db" "$PROJECT_DIR/.gitignore" 2>/dev/null; then
    echo "  [OK] .gitignore 包含 .ai/project.db"
  else
    echo "  [WARN] .gitignore 缺少 .ai/project.db"
  fi
fi

# 7. 事件统计 + 链路健康
if [ -f "$DB" ]; then
  echo ""
  "$AI_HOOKS_PYTHON" -c "
import sqlite3, sys, json
from datetime import datetime, timezone

conn = sqlite3.connect(sys.argv[1])
total = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
types = conn.execute('SELECT type, COUNT(*) FROM events GROUP BY type').fetchall()
state_count = conn.execute('SELECT COUNT(*) FROM state').fetchone()[0]

print(f'  事件总数: {total}')
for t, c in types: print(f'    {t}: {c}')
print(f'  state keys: {state_count}')

# 事件缺口检查：最后一条事件距今多久
last_row = conn.execute('SELECT type, created_at FROM events ORDER BY id DESC LIMIT 1').fetchone()
if last_row:
    last_type, last_ts = last_row['type'], last_row['created_at']
    try:
        last_dt = datetime.fromisoformat(last_ts)
        delta = datetime.now(timezone.utc) - last_dt
        days = delta.total_seconds() / 86400
        if days > 1:
            print(f'  ⚠ 事件缺口: 最后一条 {last_type} 事件在 {days:.1f} 天前')
        else:
            print(f'  [OK] 最后一条事件: {last_type} ({delta.total_seconds()/3600:.1f}小时前)')
    except:
        pass

# 检查 STATUS.md 是否落后
status_path = sys.argv[1].replace('project.db', 'STATUS.md')
import os
if os.path.exists(status_path):
    status_mtime = os.path.getmtime(status_path)
    db_mtime = os.path.getmtime(sys.argv[1])
    if db_mtime > status_mtime + 30:
        print(f'  ⚠ STATUS.md 可能过期 (project.db 更新于 {datetime.fromtimestamp(db_mtime).strftime(\"%H:%M\")})')
    else:
        print(f'  [OK] STATUS.md 是最新的')
else:
    print(f'  ⚠ STATUS.md 不存在')

conn.close()
" "$DB" 2>/dev/null || true
fi

echo ""
if [ "$ISSUES" -gt 0 ]; then
  echo "发现 $ISSUES 个问题"
  if [ "$REPAIR_MODE" = true ]; then
    echo ""
    echo "=== 尝试自动修复 ==="
    "$AI_HOOKS_PYTHON" "$AI_HOOKS_DIR/rebuild_state.py" "$DB" 2>/dev/null && echo "state 重建完成" || echo "state 重建失败"
    # 安装 git hooks
    if [ -d "$PROJECT_DIR/.git/hooks" ]; then
      for h in pre-commit post-commit post-checkout; do
        [ -f "$AI_HOOKS_DIR/$h" ] && cp "$AI_HOOKS_DIR/$h" "$PROJECT_DIR/.git/hooks/$h" && chmod +x "$PROJECT_DIR/.git/hooks/$h"
      done
      echo "git hooks 已安装"
    fi
  else
    echo "建议: bash $AI_HOOKS_DIR/setup.sh $PROJECT_DIR"
    echo "或: bash $AI_HOOKS_DIR/doctor.sh --repair $PROJECT_DIR 自动修复"
  fi
else
  echo "健康"
fi

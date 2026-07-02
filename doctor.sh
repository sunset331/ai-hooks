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

# 1
if [ -d "$PROJECT_DIR/.ai" ]; then
  echo "  [OK] .ai/ 目录存在"
else
  echo "  [FAIL] .ai/ 目录不存在"; ISSUES=$((ISSUES + 1))
fi

# 2
if [ -f "$DB" ]; then
  if "$AI_HOOKS_PYTHON" -c "import sqlite3; sqlite3.connect('$DB').execute('SELECT 1')" 2>/dev/null; then
    echo "  [OK] project.db 可正常打开"
  else
    echo "  [FAIL] project.db 损坏"; ISSUES=$((ISSUES + 1))
  fi
else
  echo "  [FAIL] project.db 不存在"; ISSUES=$((ISSUES + 1))
fi

# 3
if [ -d "$PROJECT_DIR/.git" ]; then
  HOOKS_PATH=$(cd "$PROJECT_DIR" && git config --get core.hooksPath 2>/dev/null || echo "NOT SET")
  if [ "$HOOKS_PATH" = "$AI_HOOKS_DIR" ]; then
    echo "  [OK] core.hooksPath 指向本系统"
  elif [ "$HOOKS_PATH" = "NOT SET" ]; then
    echo "  [FAIL] core.hooksPath 未配置"; ISSUES=$((ISSUES + 1))
  else
    echo "  [WARN] core.hooksPath 指向其他目录: $HOOKS_PATH"
  fi
else
  echo "  [WARN] 非 git 项目，跳过 hooks 检查"
fi

# 4
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

# 5
SKILL="$PROJECT_DIR/.claude/skills/ai-review/SKILL.md"
if [ -f "$SKILL" ]; then
  echo "  [OK] ai-review skill 已安装"
else
  echo "  [WARN] ai-review skill 未安装"
fi

# 6
if [ -f "$PROJECT_DIR/.gitignore" ]; then
  if grep -q ".ai/project.db" "$PROJECT_DIR/.gitignore" 2>/dev/null; then
    echo "  [OK] .gitignore 包含 .ai/project.db"
  else
    echo "  [WARN] .gitignore 缺少 .ai/project.db"
  fi
fi

# 7 事件统计
if [ -f "$DB" ]; then
  echo ""
  "$AI_HOOKS_PYTHON" -c "
import sqlite3
conn = sqlite3.connect('$DB')
total = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
types = conn.execute('SELECT type, COUNT(*) FROM events GROUP BY type').fetchall()
state_count = conn.execute('SELECT COUNT(*) FROM state').fetchone()[0]
print(f'  事件总数: {total}')
for t, c in types: print(f'    {t}: {c}')
print(f'  state keys: {state_count}')
conn.close()
" 2>/dev/null || true
fi

echo ""
if [ "$ISSUES" -gt 0 ]; then
  echo "发现 $ISSUES 个问题"
  if [ "$REPAIR_MODE" = true ]; then
    echo ""
    echo "=== 尝试自动修复 ==="
    "$AI_HOOKS_PYTHON" "$AI_HOOKS_DIR/rebuild_state.py" "$DB" 2>/dev/null && echo "修复完成" || echo "修复失败"
  else
    echo "建议: bash $AI_HOOKS_DIR/setup.sh $PROJECT_DIR"
    echo "或: bash $AI_HOOKS_DIR/doctor.sh --repair $PROJECT_DIR 自动修复"
  fi
else
  echo "健康"
fi

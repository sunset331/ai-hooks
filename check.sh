#!/bin/bash
# check.sh — .ai-hooks 快速健康检查
# 用法: bash check.sh [project-dir]

. "$(dirname "$0")/hooks.conf"

echo "=== .ai-hooks 检查 ==="
echo "HOOKS_DIR: $AI_HOOKS_DIR"
echo "PYTHON: $AI_HOOKS_PYTHON"
echo ""

# 检查核心文件
for f in db.py record_event.py update_state.py render_state.py hooks.conf \
         session-start.sh pre-commit post-commit post-checkout \
         setup.sh uninstall.sh update.sh doctor.sh \
         scheduler-check.ps1; do
  if [ -f "$AI_HOOKS_DIR/$f" ]; then
    echo "  [OK] $f"
  else
    echo "  [WARN] $f — not found"
  fi
done

echo ""

# 检查模板
for f in STATUS.md MEMORY.md DECISIONS.md CHECKLIST.md WORKFLOW.md \
         settings.json ai-review/SKILL.md; do
  if [ -f "$AI_HOOKS_DIR/template/$f" ]; then
    echo "  [OK] template/$f"
  else
    echo "  [WARN] template/$f — not found"
  fi
done

echo ""

# 检查测试
for f in test_core.sh test_concurrency.py; do
  if [ -f "$AI_HOOKS_DIR/tests/$f" ]; then
    echo "  [OK] tests/$f"
  else
    echo "  [WARN] tests/$f — not found"
  fi
done

# 如果传了项目目录，检查项目配置
if [ -n "$1" ]; then
  PROJECT_DIR="$1"
  echo ""
  bash "$AI_HOOKS_DIR/doctor.sh" "$PROJECT_DIR"
fi

echo ""
echo "=== 完成 ==="

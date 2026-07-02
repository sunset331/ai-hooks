#!/bin/bash
# session-start.sh — Claude Code 启动时注入 .ai/ 上下文
# 被 .claude/settings.json 的 SessionStart hook 调用
#
# 输出: 纯文本，被 Claude Code 注入到系统提示

. "$(dirname "$0")/hooks.conf"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
DB="$PROJECT_DIR/.ai/project.db"

if [ ! -f "$DB" ]; then
    echo "=== .ai/ 系统: 项目数据库未初始化 ==="
    echo "运行: $AI_HOOKS_DIR/setup.sh \"$PROJECT_DIR\""
    exit 0
fi

echo "=== 项目状态 ==="
"$AI_HOOKS_PYTHON" "$AI_HOOKS_DIR/db.py" resume "$DB" 2>/dev/null || \
"$AI_HOOKS_PYTHON" "$AI_HOOKS_DIR/db.py" summary "$DB" 2>/dev/null || \
echo "(读取失败)"

echo ""
echo "=== 工作流提示 ==="
echo "开始工作前: 读取 STATUS.md、MEMORY.md、DECISIONS.md 同步上下文"
echo "结束工作后: 更新 MEMORY.md，必要时更新 DECISIONS.md / STATUS.md"
echo "提交前: 参考 CHECKLIST.md"
echo "完整工作流: 见 WORKFLOW.md"

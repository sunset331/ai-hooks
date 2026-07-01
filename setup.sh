#!/bin/bash
# setup.sh (ai-init) — 为新项目配置 .ai/ 系统
#
# 用法:
#   bash setup.sh /path/to/project
#
# 幂等: 重复运行不覆盖已有 STATUS / MEMORY / DECISIONS

set -euo pipefail

PROJECT_DIR="$(cd "$1" 2>/dev/null && pwd || { mkdir -p "$1" && cd "$1" && pwd; })"
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

# 兼容 Windows Git Bash 路径（/f/xxx → F:/xxx）
normalize_path() {
    local p="$1"
    case "$p" in
      /[a-zA-Z]/*)
        local d=$(echo "$p" | cut -d/ -f2 | tr '[:lower:]' '[:upper:]')
        local r=$(echo "$p" | cut -d/ -f3-)
        echo "${d}:/${r}"
        ;;
      /[a-zA-Z]/)
        local d=$(echo "$p" | cut -d/ -f2 | tr '[:lower:]' '[:upper:]')
        echo "${d}:/"
        ;;
      *) echo "$p" ;;
    esac
}
PROJECT_DIR=$(normalize_path "$PROJECT_DIR")
HOOKS_DIR=$(normalize_path "$HOOKS_DIR")

PYTHON="${AI_HOOKS_PYTHON:-python}"

echo "=== .ai-hooks setup ==="
echo "项目: $PROJECT_DIR"
echo ""

# ── Step 1: 创建 .ai/ 目录 ──
AI_DIR="$PROJECT_DIR/.ai"
mkdir -p "$AI_DIR"
echo "  [1] .ai/ 目录已就绪"

# ── Step 2: 复制模板文件（不覆盖已有） ──
cp -n "$HOOKS_DIR/template/STATUS.md" "$AI_DIR/STATUS.md" 2>/dev/null || true
cp -n "$HOOKS_DIR/template/MEMORY.md" "$AI_DIR/MEMORY.md" 2>/dev/null || true
cp -n "$HOOKS_DIR/template/DECISIONS.md" "$AI_DIR/DECISIONS.md" 2>/dev/null || true
cp -n "$HOOKS_DIR/template/CHECKLIST.md" "$AI_DIR/CHECKLIST.md" 2>/dev/null || true
cp -n "$HOOKS_DIR/template/WORKFLOW.md" "$AI_DIR/WORKFLOW.md" 2>/dev/null || true

# 替换 STATUS.md 中的占位变量
sed -i "s/{{project_name}}/$PROJECT_NAME/g" "$AI_DIR/STATUS.md" 2>/dev/null || true
sed -i "s/{{date}}/$(date +%Y-%m-%d)/g" "$AI_DIR/STATUS.md" 2>/dev/null || true
sed -i "s/{{date}}/$(date +%Y-%m-%d)/g" "$AI_DIR/MEMORY.md" 2>/dev/null || true

echo "  [2] 模板文件已复制 (不覆盖已有)"

# ── Step 3: 初始化 SQLite ──
DB="$AI_DIR/project.db"
if [ ! -f "$DB" ]; then
    "$PYTHON" "$HOOKS_DIR/db.py" init "$DB"
else
    "$PYTHON" "$HOOKS_DIR/db.py" migrate "$DB" 2>/dev/null || true
fi
echo "  [3] project.db 已初始化"

# ── Step 4: Git hooks 配置 ──
if [ -d "$PROJECT_DIR/.git" ]; then
    # 检查是否已配置为本 hooks 目录
    CURRENT_HOOKS=$(cd "$PROJECT_DIR" && git config --get core.hooksPath 2>/dev/null || echo "")
    if [ "$CURRENT_HOOKS" != "$HOOKS_DIR" ]; then
        cd "$PROJECT_DIR" && git config core.hooksPath "$HOOKS_DIR"
        echo "  [4] core.hooksPath 已设置为 $HOOKS_DIR"
    else
        echo "  [4] core.hooksPath 已正确配置，跳过"
    fi
else
    echo "  [4] 非 git 项目，跳过 hooks 配置"
fi

# ── Step 5: Claude Code 配置 ──
CLAUDE_DIR="$PROJECT_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS" ]; then
    cp "$HOOKS_DIR/template/settings.json" "$SETTINGS"
    # 替换占位符
    ESCAPED_HOOKS=$(echo "$HOOKS_DIR" | sed 's|/|\\/|g')
    sed -i "s/{{AI_HOOKS_DIR}}/$ESCAPED_HOOKS/g" "$SETTINGS"
    echo "  [5] .claude/settings.json 已创建"
else
    echo "  [5] .claude/settings.json 已存在，跳过"
fi

# ── Step 6: ai-review skill ──
SKILL_DIR="$CLAUDE_DIR/skills/ai-review"
mkdir -p "$SKILL_DIR"
cp -n "$HOOKS_DIR/template/ai-review/SKILL.md" "$SKILL_DIR/SKILL.md" 2>/dev/null || true
echo "  [6] ai-review skill 已安装"

# ── Step 7: .gitignore ──
GITIGNORE="$PROJECT_DIR/.gitignore"
if [ -f "$GITIGNORE" ]; then
    if ! grep -q ".ai/project.db" "$GITIGNORE" 2>/dev/null; then
        echo "" >> "$GITIGNORE"
        echo "# .ai event system" >> "$GITIGNORE"
        echo ".ai/project.db" >> "$GITIGNORE"
        echo "  [7] .gitignore 已追加 .ai/project.db"
    else
        echo "  [7] .gitignore 已包含 .ai/project.db，跳过"
    fi
else
    echo "# .ai event system" > "$GITIGNORE"
    echo ".ai/project.db" >> "$GITIGNORE"
    echo "  [7] .gitignore 已创建"
fi

echo ""
echo "=== 完成! ==="
echo "项目 $PROJECT_NAME 的 .ai/ 系统已配置完毕。"
echo ""
echo "后续步骤:"
echo "  1. 编辑 .ai/STATUS.md 完善项目状态"
echo "  2. 编辑 .ai/MEMORY.md 记录初始信息"
echo "  3. 激活配置: 重新打开 Claude Code"
echo "  4. 如需卸载: bash $HOOKS_DIR/uninstall.sh $PROJECT_DIR"

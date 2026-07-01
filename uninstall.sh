#!/bin/bash
# uninstall.sh (ai-uninstall) — 从项目移除 .ai/ 系统 hook 配置
#
# 用法:
#   bash uninstall.sh /path/to/project
#
# 保留 .ai/ 数据不删。

set -euo pipefail

PROJECT_DIR="$(cd "$1" && pwd)"
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== .ai-hooks uninstall ==="
echo "项目: $PROJECT_DIR"
echo ""

# ── 1. 删除 core.hooksPath（如果是本系统设置的） ──
if [ -d "$PROJECT_DIR/.git" ]; then
    CURRENT_HOOKS=$(cd "$PROJECT_DIR" && git config --get core.hooksPath 2>/dev/null || echo "")
    if [ "$CURRENT_HOOKS" = "$HOOKS_DIR" ]; then
        cd "$PROJECT_DIR" && git config --unset core.hooksPath
        echo "  [1] core.hooksPath 已清除"
    elif [ -n "$CURRENT_HOOKS" ]; then
        echo "  [1] core.hooksPath 指向其他目录 ($CURRENT_HOOKS)，跳过"
    else
        echo "  [1] core.hooksPath 未配置，跳过"
    fi
else
    echo "  [1] 非 git 项目，跳过"
fi

# ── 2. 清理 .claude/settings.json 中的 SessionStart hook 引用 ──
SETTINGS="$PROJECT_DIR/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
    # 尝试只删除本系统相关的 SessionStart hook
    python -c "
import json
try:
    with open('$SETTINGS', 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    hooks = cfg.get('hooks', {})
    if 'SessionStart' in hooks:
        ss = hooks['SessionStart']
        # 过滤掉 session-start.sh 引用
        if isinstance(ss, list):
            new_ss = []
            for entry in ss:
                inner = entry.get('hooks', [])
                new_inner = [h for h in inner if '$HOOKS_DIR' not in h.get('command', '')]
                if new_inner:
                    entry['hooks'] = new_inner
                    new_ss.append(entry)
            if new_ss:
                cfg['hooks']['SessionStart'] = new_ss
            else:
                del cfg['hooks']['SessionStart']
            with open('$SETTINGS', 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print('  [2] SessionStart hook 已从 settings.json 清理')
        else:
            print('  [2] SessionStart 格式非数组，跳过')
    else:
        print('  [2] 无 SessionStart hook，跳过')
except Exception:
    # settings.json 可能不是有效 JSON 或已被修改
    print('  [2] 无法解析 settings.json，跳过自动清理')
    print('  手动检查: $SETTINGS')
" 2>/dev/null || true
fi

# ── 3. 删除 ai-review skill ──
SKILL_DIR="$PROJECT_DIR/.claude/skills/ai-review"
if [ -d "$SKILL_DIR" ]; then
    rm -rf "$SKILL_DIR"
    echo "  [3] ai-review skill 已删除"
else
    echo "  [3] ai-review skill 未安装，跳过"
fi

# ── 4. .gitignore 清理（移除 .ai/project.db 条目） ──
GITIGNORE="$PROJECT_DIR/.gitignore"
if [ -f "$GITIGNORE" ]; then
    python -c "
with open('$GITIGNORE', 'r', encoding='utf-8') as f:
    lines = f.readlines()
new_lines = [l for l in lines if l.strip() != '.ai/project.db']
if len(new_lines) != len(lines):
    with open('$GITIGNORE', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('  [4] .gitignore 中的 .ai/project.db 已移除')
else:
    print('  [4] .gitignore 无 .ai/project.db 条目，跳过')
" 2>/dev/null || true
fi

echo ""
echo "=== 完成! ==="
echo ""
echo ".ai/ 配置文件已清理。.ai/ 数据和 project.db 已保留。"
echo "如需彻底删除: rm -rf \"$PROJECT_DIR/.ai\""

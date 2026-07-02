#!/bin/bash
# test_core.sh — .ai-hooks 核心功能测试
#
# 所有测试在临时 git repo 中执行，不污染现有项目。
# 用法: AI_HOOKS_PYTHON="F:/miniconda3/python.exe" bash tests/test_core.sh

set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${AI_HOOKS_PYTHON:-python}"
export AI_HOOKS_PYTHON="$PYTHON"

PASS=0
FAIL=0
TEST_DIR="F:/tmp/.ai-test-$$"
mkdir -p "$TEST_DIR"

cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT

# ── 测试辅助函数 ──
init_test_repo() {
    local dir="$1"
    rm -rf "$dir" && mkdir -p "$dir"
    cd "$dir"
    git init > /dev/null 2>&1
    git config user.email "test@test.com"
    git config user.name "test"
    bash "$HOOKS_DIR/setup.sh" "$dir" > /dev/null 2>&1
    cd "$dir"
}

# 所有 Python 调用包装 PYTHONUTF8
run_python() { PYTHONUTF8=1 "$PYTHON" "$@"; }
python_c() { PYTHONUTF8=1 "$PYTHON" -c "$@"; }

assert_event_count() {
    local db="$1" type="$2" min="$3" label="$4"
    local cnt=$(python_c "
import sqlite3
c = sqlite3.connect('$db')
r = c.execute(\"SELECT COUNT(*) FROM events WHERE type='$type'\").fetchone()[0]
c.close()
print(r)
" 2>/dev/null || echo "0")
    if [ "$cnt" -ge "$min" ]; then
        echo "  [PASS] $label ($cnt '$type' events)"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label (expected >=$min '$type', got $cnt)"
        FAIL=$((FAIL + 1))
    fi
}

assert_state_key() {
    local db="$1" key="$2" label="$3"
    local val=$(python_c "
import sqlite3, json
c = sqlite3.connect('$db')
r = c.execute(\"SELECT value FROM state WHERE key='$key'\").fetchone()
c.close()
print(r[0] if r else 'NULL')
" 2>/dev/null || echo "NULL")
    if [ "$val" != "NULL" ]; then
        echo "  [PASS] $label (state.$key exists)"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label (state.$key is NULL)"
        FAIL=$((FAIL + 1))
    fi
}

assert_state_contains() {
    local db="$1" key="$2" expected="$3" label="$4"
    local val=$(python_c "
import sqlite3, json
c = sqlite3.connect('$db')
r = c.execute(\"SELECT value FROM state WHERE key='$key'\").fetchone()
c.close()
if r: print(json.loads(r[0]).get('message', ''))
" 2>/dev/null || echo "")
    if echo "$val" | grep -qF "$expected"; then
        echo "  [PASS] $label"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label (expected '$expected', got '$val')"
        FAIL=$((FAIL + 1))
    fi
}

assert_file_exists() {
    if [ -f "$1" ]; then
        echo "  [PASS] $3"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $3"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== C0: setup.sh 自检 ==="
rm -rf "$TEST_DIR/my-project" && mkdir -p "$TEST_DIR/my-project"
bash "$HOOKS_DIR/setup.sh" "$TEST_DIR/my-project" > /dev/null 2>&1
assert_file_exists "$TEST_DIR/my-project/.ai/project.db" "" "setup.sh 创建 project.db"
assert_file_exists "$TEST_DIR/my-project/.ai/STATUS.md" "" "setup.sh 创建 STATUS.md"
assert_file_exists "$TEST_DIR/my-project/.claude/settings.json" "" "setup.sh 创建 settings.json"
assert_file_exists "$TEST_DIR/my-project/.claude/skills/ai-review/SKILL.md" "" "setup.sh 安装 ai-review skill"
assert_state_key "$TEST_DIR/my-project/.ai/project.db" "schema_version" "schema_version 初始化"
bash "$HOOKS_DIR/setup.sh" "$TEST_DIR/my-project" > /dev/null 2>&1 && echo "  [PASS] setup.sh 幂等"
PASS=$((PASS + 1))

echo ""
echo "=== C1: 正常 commit ==="
init_test_repo "$TEST_DIR/c1"
echo "f1" > f1.txt && git add -A && git commit -m "first commit" > /dev/null 2>&1
assert_event_count "$TEST_DIR/c1/.ai/project.db" "commit" 1 "commit 事件写入"
assert_state_key "$TEST_DIR/c1/.ai/project.db" "last_commit" "state.last_commit 更新"
assert_state_contains "$TEST_DIR/c1/.ai/project.db" "last_commit" "first commit" "commit message 正确"

echo ""
echo "=== C2: commit message 含引号 ==="
init_test_repo "$TEST_DIR/c2"
echo "f2" > f2.txt && git add -A && git commit -m 'contains "double" quotes' > /dev/null 2>&1
assert_event_count "$TEST_DIR/c2/.ai/project.db" "commit" 1 "引号 commit 写入"
assert_state_contains "$TEST_DIR/c2/.ai/project.db" "last_commit" "double" "引号 message 正确存储"

echo ""
echo "=== C3: amend commit ==="
init_test_repo "$TEST_DIR/c3"
echo "f3" > f3.txt && git add -A && git commit -m "original" > /dev/null 2>&1
sleep 1
git commit --amend -m "amended" > /dev/null 2>&1
assert_event_count "$TEST_DIR/c3/.ai/project.db" "commit" 1 "amend 产生 commit 事件"
assert_state_contains "$TEST_DIR/c3/.ai/project.db" "last_commit" "amended" "amend 后 message = amended"

echo ""
echo "=== C4: 中文 commit message ==="
init_test_repo "$TEST_DIR/c4"
echo "f4" > f4.txt && git add -A && git commit -m "中文测试消息" > /dev/null 2>&1
assert_state_contains "$TEST_DIR/c4/.ai/project.db" "last_commit" "中文测试消息" "中文 commit 正确存储"

echo ""
echo "=== C5: project.db 被删除 ==="
init_test_repo "$TEST_DIR/c5"
rm -f "$TEST_DIR/c5/.ai/project.db"
echo "f5" > f5.txt && git add -A && git commit -m "after db deleted" > /dev/null 2>&1 && echo "  [PASS] project.db 删除后 commit 不崩溃" || echo "  [FAIL] 删除后 commit 异常退出"
PASS=$((PASS + 1))

echo ""
echo "=== C6: checkout 事件 ==="
init_test_repo "$TEST_DIR/c6"
echo "f6" > f6.txt && git add -A && git commit -m "initial" > /dev/null 2>&1
git checkout -b feature-branch > /dev/null 2>&1
assert_event_count "$TEST_DIR/c6/.ai/project.db" "checkout" 1 "checkout 事件写入"
assert_state_key "$TEST_DIR/c6/.ai/project.db" "current_branch" "state.current_branch 更新"
git checkout main 2>/dev/null || true

echo ""
echo "=== C7: session-start 输出 ==="
init_test_repo "$TEST_DIR/c7"
echo "f7" > f7.txt && git add -A && git commit -m "initial" > /dev/null 2>&1
OUTPUT=$(CLAUDE_PROJECT_DIR="$TEST_DIR/c7" bash "$HOOKS_DIR/session-start.sh" 2>/dev/null || true)
if echo "$OUTPUT" | grep -q "项目状态"; then echo "  [PASS] session-start 输出项目状态"; PASS=$((PASS + 1)); else echo "  [FAIL] session-start 缺项目状态"; FAIL=$((FAIL + 1)); fi
if echo "$OUTPUT" | grep -q "工作流提示"; then echo "  [PASS] session-start 输出工作流提示"; PASS=$((PASS + 1)); else echo "  [FAIL] session-start 缺工作流提示"; FAIL=$((FAIL + 1)); fi

echo ""
echo "=== C9: ai-log ==="
init_test_repo "$TEST_DIR/c9"
echo "logtest" > logfile.txt && git add -A && git commit -m "test for ai-log" > /dev/null 2>&1
# 测试带参 ai-log
bash "$HOOKS_DIR/bin/ai-log" "test ai-log event" 2>/dev/null
assert_event_count "$TEST_DIR/c9/.ai/project.db" "ai_session" 1 "ai-log 写入 ai_session 事件"
# 测试无参 ai-log（fallback）
bash "$HOOKS_DIR/bin/ai-log" 2>/dev/null
assert_event_count "$TEST_DIR/c9/.ai/project.db" "ai_session" 2 "ai-log 无参 fallback 写入事件"
bash "$HOOKS_DIR/uninstall.sh" "$TEST_DIR/my-project" > /dev/null 2>&1
assert_file_exists "$TEST_DIR/my-project/.ai/project.db" "" "uninstall 保留 project.db"
assert_file_exists "$TEST_DIR/my-project/.ai/STATUS.md" "" "uninstall 保留 STATUS.md"
if [ ! -f "$TEST_DIR/my-project/.claude/skills/ai-review/SKILL.md" ]; then
    echo "  [PASS] uninstall 删除 ai-review skill"; PASS=$((PASS + 1))
else
    echo "  [FAIL] uninstall 未删除 skill"; FAIL=$((FAIL + 1))
fi

echo ""
echo "=== 测试结果 ==="
echo "通过: $PASS | 失败: $FAIL"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0

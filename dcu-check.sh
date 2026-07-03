#!/bin/bash
# dcu-check.sh — DCU 环境完整性检查
# 被 pre-commit hook 调用。
# 跳过条件: CLAUDE.md 或 COMMIT_EDITMSG 包含 [skip dcu]

. "$(dirname "$0")/hooks.conf"

SKIP_FILE="${CLAUDE_PROJECT_DIR:-$(pwd)}/.ai/DCU_SKIP"
if [ -f "$SKIP_FILE" ]; then
    echo "[dcu-check] SKIP (DCU_SKIP found)"
    exit 0
fi

# 检查 PyTorch CUDA 可用性
PYTHON="${AI_HOOKS_PYTHON:-python}"
if ! "$PYTHON" -c "import torch; assert torch.cuda.is_available(), 'No CUDA'" 2>/dev/null; then
    cat <<'EOF'
⚠️  [DCU CHECK] CUDA/HIP 不可用！

你在提交的代码将部署到 DCU (Vega 20 / Radeon Instinct) 环境，但当前环境无可用 GPU。
请确认你至少做了一次 DCU 环境验证:
  source env_setup.sh && python train.py --epochs 100

如果确定不需要 DCU 验证，请运行:
  echo 'skip' > "$(dirname "$0")/.ai/DCU_SKIP"
EOF
    exit 1
fi
echo "[dcu-check] DCU OK: $("$PYTHON" -c "import torch; print(torch.cuda.get_device_name(0))")"

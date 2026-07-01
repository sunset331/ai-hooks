#!/usr/bin/env pwsh
# scheduler-check.ps1 — Task Scheduler 每日状态检查（只读）
#
# 所有路径通过参数传入，无硬编码。
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scheduler-check.ps1 `
#     -HooksDir "C:/path/to/ai-hooks" `
#     -ProjectDir "C:/path/to/project" `
#     -PythonExe "python"

param(
    [Parameter(Mandatory=$true)]
    [string]$HooksDir,

    [Parameter(Mandatory=$true)]
    [string]$ProjectDir,

    [string]$PythonExe = "python"
)

$DbPath = Join-Path $ProjectDir ".ai" "project.db"

# 检查 project.db 是否存在
if (-not (Test-Path $DbPath)) {
    Write-Host "[scheduler] project.db not found at $DbPath"
    exit 0
}

$ProjectName = Split-Path $ProjectDir -Leaf

# 1. git status 检测 dirty files
Push-Location $ProjectDir
$GitStatus = git status --short 2>$null
$DirtyCount = 0
if ($GitStatus) { $DirtyCount = ($GitStatus | Measure-Object -Line).Lines }
Pop-Location

# 2. 从 state 读取状态
$StateOutput = & $PythonExe -c @"
import json, sqlite3
conn = sqlite3.connect('$DbPath')
state = {}
for row in conn.execute('SELECT key, value FROM state').fetchall():
    state[row[0]] = json.loads(row[1])
conn.close()
print(json.dumps(state))
"@ 2>$null

$Warnings = @()
$State = $null
try { $State = $StateOutput | ConvertFrom-Json } catch {}

if ($State) {
    # 3. 检查最后活动时间
    $LastUpdated = $State.status_health.status_md_updated
    if ($LastUpdated) {
        try {
            $LastDate = [DateTime]::Parse($LastUpdated)
            $DiffDays = [DateTime]::Now.Subtract($LastDate).Days
            if ($DiffDays -gt 3) {
                $Warnings += "$DiffDays days since last update"
                Write-Host "[scheduler] STATUS.md $DiffDays 天未更新"
            }
        } catch {}
    }

    # 4. 检查最后 AI session
    $LastAI = $State.last_ai_action
    if (-not $LastAI) {
        $Warnings += "no recent AI session recorded"
    }

    # 5. 一致性检查
    $Consistency = & $PythonExe -c @"
import sys; sys.path.insert(0, '$HooksDir')
from db import check_consistency
w = check_consistency('$DbPath')
for warn in w: print(warn)
"@ 2>$null
    if ($Consistency) {
        foreach ($warn in $Consistency) {
            $Warnings += $warn
        }
    }
}

# 6. 写 scheduler_check 事件
$DirtyJson = "{\`"status\`":\`"done\`",\`"dirty_count\`":$DirtyCount,\`"warnings\`":[$(($Warnings | ForEach-Object { "\`"$_`"" }) -join ",")]}"
& $PythonExe "$HooksDir/record_event.py" $DbPath scheduler_check $DirtyJson $ProjectName 2>$null >$null
& $PythonExe "$HooksDir/update_state.py" $DbPath scheduler_check 2>$null >$null

# 7. 如果有警告，发 Windows Toast
if ($Warnings.Count -gt 0) {
    Write-Host "[scheduler] $($Warnings.Count) warning(s):"
    foreach ($w in $Warnings) {
        Write-Host "  - $w"
    }

    $ToastTitle = ".ai Health - $ProjectName"
    $ToastText = "$($Warnings.Count) issue(s): $($Warnings[0])"
    try {
        $Toast = New-Object -ComObject Windows.UI.Notifications.ToastNotificationManager
        $Template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $TextNodes = $Template.GetElementsByTagName("text")
        $TextNodes.Item(0).AppendChild($Template.CreateTextNode($ToastTitle)) | Out-Null
        $TextNodes.Item(1).AppendChild($Template.CreateTextNode($ToastText)) | Out-Null
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier().Show($Template)
    } catch {
        Write-Host "[scheduler] Toast failed (Win10+ only)"
    }
} else {
    Write-Host "[scheduler] $ProjectName 状态健康"
}

# 8. 如果 dirty files > 0 且不一致，写入 heal patch
if ($DirtyCount -gt 0 -and $Warnings.Count -gt 0) {
    $PatchFile = Join-Path $ProjectDir ".ai" "heal-patch-$(Get-Date -Format 'yyyyMMdd').note"
@"
# .ai Heal Patch - $(Get-Date -Format 'yyyy-MM-dd HH:mm')
#
# 这是一个诊断报告，不是自动执行脚本。
#
# Warnings:
$( for ($i=0; $i -lt $Warnings.Count; $i++) { "  - $($Warnings[$i])`n" } )

# git status:
$GitStatus
"@ | Out-File -FilePath $PatchFile -Encoding utf8
    Write-Host "[scheduler] 诊断报告: $PatchFile"
}

Write-Host "[scheduler] 检查完成"

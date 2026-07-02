"""
reducer.py — 纯函数 Event → State 投影

reduce(state, event) 是纯函数（无 IO、无 system state 依赖），
可被 update_state（增量）和 rebuild_state（全量）共享。

强制规则：
  - reducer 只能消费 event payload，不读时间/git HEAD/环境变量
  - 所有上下文必须在 event 生成阶段固化到 payload 中
"""
from __future__ import annotations


def validate_event(event: dict) -> list[str]:
    """检查 event 字段完整性，返回 missing 字段列表。空列表 = 合法。"""
    missing: list[str] = []
    event_type = event.get("type", "")
    payload = event.get("payload", {})

    if event_type == "commit":
        for k in ("sha", "message"):
            if not payload.get(k):
                missing.append(f"payload.{k}")

    elif event_type == "checkout":
        if not payload.get("branch"):
            missing.append("payload.branch")

    elif event_type == "ai_session":
        if not payload.get("summary"):
            missing.append("payload.summary")

    elif event_type == "scheduler_check":
        if payload.get("dirty_count") is None:
            missing.append("payload.dirty_count")

    return missing


def reduce(state: dict, event: dict) -> dict:
    """纯函数：旧 state + 一条 event → 新 state。

    Args:
        state: 当前 state KV dict（如 {"last_commit": {...}, "dirty_files": 0}）
        event: event dict，含 type / payload / created_at / id

    Returns:
        新 state dict（不修改入参）
    """
    next_state = dict(state)  # 浅拷贝，不修改入参
    event_type = event.get("type", "")
    payload = event.get("payload", {})
    created_at = event.get("created_at", "")

    if event_type == "commit":
        next_state["last_commit"] = {
            "sha": payload.get("sha"),
            "message": payload.get("message"),
            "date": payload.get("date", created_at),
        }
        next_state["dirty_files"] = 0
        next_state["status_health"] = {
            "status_md_updated": created_at[:10],
            "healthy": True,
        }

    elif event_type == "checkout":
        next_state["current_branch"] = payload.get("branch")

    elif event_type == "ai_session":
        next_state["last_ai_action"] = payload.get("summary")

    elif event_type == "scheduler_check":
        next_state["dirty_files"] = payload.get("dirty_count", 0)
        warnings = payload.get("warnings", [])
        next_state["status_health"] = {
            "status_md_updated": created_at[:10],
            "healthy": len(warnings) == 0,
            "warnings": warnings,
        }

    # 记录上次处理的 event id，用于幂等判断
    if "id" in event:
        next_state["last_event_id"] = event["id"]

    return next_state

#!/usr/bin/env python
"""
update_state.py — 从事件聚合更新 state

接收事件参数，更新对应的 state key。
不是纯函数 reducer（不做完整重放），但足以保证 state 不会太久滞后。

用法:
    python update_state.py <db_path> commit       # 从最近 commit 事件刷新
    python update_state.py <db_path> checkout     # 从最近 checkout 事件刷新
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, set_state, get_recent_events, get_state, record_event


def reduce_commit(db_path: str):
    events = get_recent_events(db_path, limit=1, event_type="commit")
    if not events:
        return
    e = events[0]
    payload = e["payload"]
    set_state(db_path, "last_commit", {
        "sha": payload.get("sha"),
        "message": payload.get("message"),
        "date": payload.get("date", e["created_at"]),
    })
    set_state(db_path, "dirty_files", 0)

    # 同时更新健康状态
    set_state(db_path, "status_health", {
        "status_md_updated": e["created_at"][:10],
        "healthy": True,
    })


def reduce_checkout(db_path: str):
    events = get_recent_events(db_path, limit=1, event_type="checkout")
    if not events:
        return
    e = events[0]
    payload = e["payload"]
    set_state(db_path, "current_branch", payload.get("branch"))


def reduce_ai_session(db_path: str):
    events = get_recent_events(db_path, limit=1, event_type="ai_session")
    if not events:
        return
    e = events[0]
    payload = e["payload"]
    set_state(db_path, "last_ai_action", payload.get("summary"))


def reduce_scheduler_check(db_path: str):
    events = get_recent_events(db_path, limit=1, event_type="scheduler_check")
    if not events:
        return
    e = events[0]
    payload = e["payload"]
    set_state(db_path, "dirty_files", payload.get("dirty_count", 0))

    # 更新健康状态
    w = payload.get("warnings", [])
    set_state(db_path, "status_health", {
        "status_md_updated": e["created_at"][:10],
        "healthy": len(w) == 0,
        "warnings": w,
    })


REDUCERS = {
    "commit": reduce_commit,
    "checkout": reduce_checkout,
    "ai_session": reduce_ai_session,
    "scheduler_check": reduce_scheduler_check,
}


def main():
    if len(sys.argv) < 3:
        print("Usage: python update_state.py <db_path> <event_type>")
        print(f"Supported types: {', '.join(REDUCERS.keys())}")
        sys.exit(1)

    db_path = sys.argv[1]
    event_type = sys.argv[2]

    reducer = REDUCERS.get(event_type)
    if not reducer:
        print(f"Unknown event type: {event_type}")
        print(f"Supported: {', '.join(REDUCERS.keys())}")
        sys.exit(1)

    reducer(db_path)
    print(f"State updated from {event_type} event")


if __name__ == "__main__":
    main()

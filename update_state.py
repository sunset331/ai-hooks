#!/usr/bin/env python
"""
update_state.py — 从事件增量更新 state

用法:
    python update_state.py <db_path> <event_type>          # 自动取最近 event
    python update_state.py <db_path> <event_type> <event_id>  # 指定 event id

依赖 reducer.py 的纯函数 reduce()，同一逻辑被 rebuild_state 共享。
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, set_all_state, get_recent_events
from reducer import reduce, validate_event


def _read_current_state(conn) -> dict:
    rows = conn.execute("SELECT key, value FROM state").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def apply_event(db_path: str, event_type: str, event_id: int = None):
    """获取一条 event → reduce → 批量原子写 state。

    如果指定 event_id，只处理该事件。
    如果不指定，取最近一条指定类型的事件（向后兼容）。
    """
    conn = get_conn(db_path)

    if event_id:
        row = conn.execute(
            "SELECT id, event_version, created_at, type, payload, project FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        event = dict(row) if row else None
        if event:
            event["payload"] = json.loads(event["payload"])
    else:
        events = get_recent_events(db_path, limit=1, event_type=event_type)
        event = events[0] if events else None

    if not event:
        conn.close()
        print(f"No {event_type} event to apply")
        return

    missing = validate_event(event)
    if missing:
        print(f"Warning: event #{event['id']} missing fields: {missing}")

    current = _read_current_state(conn)
    conn.close()

    new_state = reduce(current, event)
    set_all_state(db_path, new_state)
    print(f"State updated from {event_type} event #{event['id']}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python update_state.py <db_path> <event_type> [event_id]")
        print("Supported types: commit, checkout, ai_session, scheduler_check")
        sys.exit(1)

    db_path = sys.argv[1]
    event_type = sys.argv[2]
    event_id = int(sys.argv[3]) if len(sys.argv) >= 4 else None

    apply_event(db_path, event_type, event_id)


if __name__ == "__main__":
    main()

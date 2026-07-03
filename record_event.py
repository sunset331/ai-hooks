#!/usr/bin/env python
"""
record_event.py — CLI 入口: 写入一条事件到 project.db

用法:
    python record_event.py <db_path> <type> <payload_json> <project>

示例:
    python record_event.py /path/project.db commit '{"sha":"abc","message":"fix bug","date":"2026-07-01"}' music-player
"""
import json
import sys
import os

# 确保能找到 db.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import record_event


def main():
    if len(sys.argv) < 5:
        print("Usage: python record_event.py <db_path> <type> <payload_json> <project>")
        sys.exit(1)

    db_path = sys.argv[1]
    event_type = sys.argv[2]
    payload = json.loads(sys.argv[3])
    project = sys.argv[4]

    result = record_event(db_path, event_type, payload, project)
    print(f"event_id={result['id']} created_at={result['created_at']}")

    # 自动链: update_state + render_state
    db_dir = os.path.dirname(db_path)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from update_state import apply_event
        from render_state import render

        apply_event(db_path, event_type, result["id"])

        status_path = os.path.join(db_dir, "STATUS.md")
        with open(status_path, "w", encoding="utf-8") as f:
            f.write(render(db_path))
            f.write("\n")
        print(f"state updated, STATUS rendered to {status_path}")
    except Exception as e:
        print(f"state/render chain warning: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

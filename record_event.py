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


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
rebuild_state.py — 从 events 全量重放重建 state

把数据库当作 Event Sourcing 的真相源：events → reduce → state。

用法:
    python rebuild_state.py <db_path>              # 正常重建
    python rebuild_state.py <db_path> --strict     # debug: 不允许 fallback / IO / 默认值
    python rebuild_state.py <db_path> --diff       # 只显示差异，不写入

输出重建前后的 state 差异摘要。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, set_all_state, get_all_state
from reducer import reduce, validate_event


def rebuild(db_path: str, strict: bool = False, dry_run: bool = False) -> dict:
    """从 events 全量重建 state。

    Args:
        db_path: SQLite 路径
        strict: debug 模式 — 不允许 IO/fallback/missing field 自动补全
        dry_run: 只显示差异，不写入

    Returns:
        重建后的 state dict
    """
    conn = get_conn(db_path)

    rows = conn.execute(
        "SELECT id, event_version, created_at, type, payload, project FROM events ORDER BY id"
    ).fetchall()

    if not rows:
        conn.close()
        print("No events to replay")
        return {}

    state: dict = {}
    for row in rows:
        event = dict(row)
        event["payload"] = json.loads(event["payload"])

        if strict:
            missing = validate_event(event)
            if missing:
                conn.close()
                print(f"STRICT FAIL: event #{event['id']} ({event['type']}) missing: {missing}")
                sys.exit(2)

        state = reduce(state, event)

    conn.close()

    if not dry_run:
        set_all_state(db_path, state)
        print(f"State rebuilt from {len(rows)} events ({len(state)} keys)")
    else:
        print(f"Dry-run: would write {len(state)} keys from {len(rows)} events")

    return state


def _diff_dicts(old: dict, new: dict) -> list[str]:
    """比较两个 dict，返回差异行列表"""
    lines = []
    all_keys = set(old) | set(new)
    for k in sorted(all_keys):
        if k in ("schema_version",):
            continue
        ov = json.dumps(old.get(k), ensure_ascii=False, default=str)
        nv = json.dumps(new.get(k), ensure_ascii=False, default=str)
        if ov != nv:
            lines.append(f"  {k}: {ov[:60]} → {nv[:60]}")
    if not lines:
        lines.append("  (no differences)")
    return lines


def main():
    if len(sys.argv) < 2:
        print("Usage: python rebuild_state.py <db_path> [--strict] [--diff]")
        sys.exit(1)

    db_path = sys.argv[1]
    strict = "--strict" in sys.argv
    dry_run = "--diff" in sys.argv

    old_state = get_all_state(db_path)

    new_state = rebuild(db_path, strict=strict, dry_run=dry_run)

    if old_state:
        diffs = _diff_dicts(old_state, new_state)
        print("Diff (before → after):")
        for line in diffs:
            print(line)
    else:
        print("(no previous state to compare)")


if __name__ == "__main__":
    main()

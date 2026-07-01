#!/usr/bin/env python
"""
test_concurrency.py — SQLite 并发测试

场景:
  1. 10 线程同时 record_event — 验证无 SQLITE_BUSY、数据不丢、id 不冲突
  2. 2 线程同时 set_state 同一个 key — 验证 UPSERT 原子性

用法:
    pytest test_concurrency.py -v
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import init, record_event, set_state, get_state, get_conn


def test_10_threads_record_event():
    """并发 10 线程写 events，验证无异常、id 不冲突"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init(db_path)

        results_lock = threading.Lock()
        results = []
        errors = []

        def writer(i):
            try:
                r = record_event(db_path, "test", {"thread": i, "data": f"thread_{i}"}, "test-concurrency")
                with results_lock:
                    results.append(r)
            except Exception as e:
                with results_lock:
                    errors.append((i, str(e)))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # 验证 id 不冲突
        ids = [r["id"] for r in results]
        assert len(set(ids)) == 10, f"Duplicate IDs: {ids}"

        # 验证所有事件都在 DB 中
        conn = get_conn(db_path)
        count = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()["cnt"]
        conn.close()
        assert count == 10, f"Expected 10 events in DB, got {count}"

        print(f"  [PASS] 10 线程并发写 events: 10 条全部写入，id 无冲突")
    finally:
        os.unlink(db_path)


def test_2_threads_same_state_key():
    """并发 2 线程写同一个 state key，验证 UPSERT 原子性"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init(db_path)

        errors = []

        def writer(value):
            try:
                set_state(db_path, "race_key", {"value": value})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # 最终值应该是 0 或 1（不可能两个都生效，但也不应该炸）
        final = get_state(db_path, "race_key")
        assert final is not None, "State key should exist"
        assert final["value"] in [0, 1], f"Unexpected final value: {final}"

        print(f"  [PASS] 2 线程并发写同一 state key: 无异常，最终值={final['value']}")
    finally:
        os.unlink(db_path)


def test_10_threads_sequential_ids():
    """并发 10 线程后，id 应该是连续的（无空洞）"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init(db_path)

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=record_event,
                args=(db_path, "test", {"n": i}, "seq-test"),
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conn = get_conn(db_path)
        ids = [r["id"] for r in conn.execute("SELECT id FROM events ORDER BY id").fetchall()]
        conn.close()

        assert ids == list(range(1, 11)), f"IDs not sequential: {ids}"

        print(f"  [PASS] 10 线程 id 连续: {ids[0]}..{ids[-1]}")
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    print("=== .ai-hooks 并发测试 ===")
    print()
    test_10_threads_record_event()
    test_2_threads_same_state_key()
    test_10_threads_sequential_ids()
    print()
    print("=== 全部通过 ===")

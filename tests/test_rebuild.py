"""rebuild_state + idempotent 集成测试"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import init, record_event, set_all_state, get_all_state, set_state
from reducer import reduce


def _make_project_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    init(f.name)
    return f.name


class TestRebuild:
    def test_rebuild_empty_db(self):
        db = _make_project_db()
        from rebuild_state import rebuild
        state = rebuild(db)
        assert state == {}
        os.unlink(db)

    def test_rebuild_single_commit(self):
        db = _make_project_db()
        from rebuild_state import rebuild

        record_event(db, "commit", {"sha": "abc", "message": "first"}, "test")
        state = rebuild(db)

        assert state["last_commit"]["sha"] == "abc"
        assert state["dirty_files"] == 0
        os.unlink(db)

    def test_rebuild_multiple_events(self):
        db = _make_project_db()
        from rebuild_state import rebuild

        record_event(db, "commit", {"sha": "c1", "message": "first"}, "test")
        record_event(db, "checkout", {"branch": "feature"}, "test")
        record_event(db, "ai_session", {"summary": "working"}, "test")

        state = rebuild(db)

        assert state["last_commit"]["sha"] == "c1"
        assert state["current_branch"] == "feature"
        assert state["last_ai_action"] == "working"
        os.unlink(db)

    def test_rebuild_after_state_deleted(self):
        """删掉 state 表内容 → rebuild 应恢复所有 state"""
        db = _make_project_db()
        from rebuild_state import rebuild

        record_event(db, "commit", {"sha": "abc", "message": "fix"}, "test")
        record_event(db, "checkout", {"branch": "main"}, "test")

        # 模拟 state 损坏：删了
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM state WHERE key != 'schema_version'")
        conn.commit()
        conn.close()

        state = rebuild(db)

        assert state["last_commit"]["sha"] == "abc"
        assert state["current_branch"] == "main"
        os.unlink(db)

    def test_rebuild_dry_run_does_not_write(self):
        """--diff 不应修改 state"""
        db = _make_project_db()
        from rebuild_state import rebuild

        record_event(db, "commit", {"sha": "abc", "message": "x"}, "test")
        set_state(db, "manual_key", "should_persist")

        old = get_all_state(db)
        rebuild(db, dry_run=True)
        after = get_all_state(db)

        assert after.get("manual_key") == "should_persist"
        assert after == old
        os.unlink(db)


class TestIdempotent:
    def test_reduce_idempotent_same_event(self):
        """同一 event id reduce 两次应产生相同 state"""
        state = {}
        event = {
            "id": 1,
            "type": "commit",
            "payload": {"sha": "abc", "message": "fix"},
            "created_at": "2026-07-02T12:00:00",
        }

        s1 = reduce(state, event)
        s2 = reduce(state, event)
        assert s1 == s2

    def test_reduce_last_event_id_stable(self):
        """连续 reduce 应产生递增的 last_event_id"""
        state = {}
        e1 = {"id": 1, "type": "commit", "payload": {"sha": "a", "message": "1"}, "created_at": ""}
        e2 = {"id": 2, "type": "commit", "payload": {"sha": "b", "message": "2"}, "created_at": ""}
        e3 = {"id": 3, "type": "checkout", "payload": {"branch": "feat"}, "created_at": ""}

        s = reduce(state, e1)
        assert s["last_event_id"] == 1
        s = reduce(s, e2)
        assert s["last_event_id"] == 2
        s = reduce(s, e3)
        assert s["last_event_id"] == 3

    def test_rebuild_equals_sequential_reduce(self):
        """全量 rebuild 结果应等同连续 reduce"""
        db = _make_project_db()
        from rebuild_state import rebuild

        record_event(db, "commit", {"sha": "c1", "message": "first"}, "test")
        record_event(db, "commit", {"sha": "c2", "message": "second"}, "test")
        record_event(db, "checkout", {"branch": "dev"}, "test")

        state_from_rebuild = rebuild(db)

        # 手动连续 reduce
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()
        conn.close()
        manual_state = {}
        for r in rows:
            evt = dict(r)
            evt["payload"] = json.loads(evt["payload"])
            manual_state = reduce(manual_state, evt)

        assert state_from_rebuild == manual_state
        os.unlink(db)

    def test_set_all_state_idempotent(self):
        """相同 KV 写入两次应稳定"""
        db = _make_project_db()

        kv1 = {"alpha": "first", "beta": 42}
        set_all_state(db, kv1)
        s1 = get_all_state(db)

        kv2 = {"alpha": "first", "beta": 42}
        set_all_state(db, kv2)
        s2 = get_all_state(db)

        assert s1["alpha"] == s2["alpha"]
        assert s1["beta"] == s2["beta"]
        os.unlink(db)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

"""reducer 单元测试 — 纯函数，无 IO，毫秒级完成"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reducer import reduce, validate_event


def make_event(event_type, payload, event_id=1, created_at="2026-07-02T12:00:00"):
    return {"id": event_id, "type": event_type, "payload": payload, "created_at": created_at}


class TestValidateEvent:
    def test_valid_commit(self):
        e = make_event("commit", {"sha": "abc", "message": "fix"})
        assert validate_event(e) == []

    def test_commit_missing_payload(self):
        e = make_event("commit", {})
        missing = validate_event(e)
        assert "payload.sha" in missing
        assert "payload.message" in missing

    def test_missing_branch_on_checkout(self):
        e = make_event("checkout", {})
        assert validate_event(e) == ["payload.branch"]

    def test_valid_checkout(self):
        e = make_event("checkout", {"branch": "main"})
        assert validate_event(e) == []

    def test_ai_session_missing_summary(self):
        e = make_event("ai_session", {})
        assert validate_event(e) == ["payload.summary"]

    def test_scheduler_check_missing_dirty_count(self):
        e = make_event("scheduler_check", {})
        assert validate_event(e) == ["payload.dirty_count"]

    def test_unknown_type_no_validation(self):
        e = make_event("unknown_type", {"foo": "bar"})
        assert validate_event(e) == []


class TestReduce:
    def test_commit_sets_last_commit_and_clears_dirty(self):
        state = {"dirty_files": 3}
        event = make_event("commit", {"sha": "abc123", "message": "fix bug", "date": "2026-07-02"})
        result = reduce(state, event)
        assert result["last_commit"]["sha"] == "abc123"
        assert result["last_commit"]["message"] == "fix bug"
        assert result["dirty_files"] == 0
        assert result["status_health"]["healthy"] is True

    def test_commit_missing_date_uses_created_at(self):
        state = {}
        event = make_event("commit", {"sha": "abc", "message": "fix"})
        result = reduce(state, event)
        assert result["last_commit"]["date"] == event["created_at"]

    def test_checkout_sets_branch(self):
        state = {"current_branch": "old-branch"}
        event = make_event("checkout", {"branch": "new-feature"})
        result = reduce(state, event)
        assert result["current_branch"] == "new-feature"

    def test_ai_session_sets_last_action(self):
        state = {}
        event = make_event("ai_session", {"summary": "重构 shuffle 算法"})
        result = reduce(state, event)
        assert result["last_ai_action"] == "重构 shuffle 算法"

    def test_scheduler_check_healthy(self):
        state = {}
        event = make_event("scheduler_check", {"status": "ok", "dirty_count": 0, "warnings": []})
        result = reduce(state, event)
        assert result["dirty_files"] == 0
        assert result["status_health"]["healthy"] is True

    def test_scheduler_check_unhealthy(self):
        state = {}
        event = make_event("scheduler_check",
                           {"status": "warn", "dirty_count": 2, "warnings": ["uncommitted files"]})
        result = reduce(state, event)
        assert result["dirty_files"] == 2
        assert result["status_health"]["healthy"] is False
        assert result["status_health"]["warnings"] == ["uncommitted files"]

    def test_last_event_id_recorded(self):
        state = {}
        event = make_event("commit", {"sha": "abc", "message": "x"}, event_id=42)
        result = reduce(state, event)
        assert result["last_event_id"] == 42

    def test_unknown_event_type_preserves_state(self):
        state = {"current_branch": "main"}
        event = make_event("unknown_type", {"foo": "bar"})
        result = reduce(state, event)
        assert result["current_branch"] == "main"

    def test_purity_no_mutation(self):
        """验证 reduce 不修改入参"""
        original_state = {"dirty_files": 3}
        original_state_copy = dict(original_state)
        event = make_event("commit", {"sha": "a", "message": "b"})
        reduce(original_state, event)
        assert original_state == original_state_copy

    def test_commit_without_author_fallback(self):
        """payload 缺少 author 字段时应正常降级"""
        state = {}
        event = make_event("commit", {"sha": "abc", "message": "no author"})
        result = reduce(state, event)
        assert result["last_commit"]["sha"] == "abc"
        # author 不会出现在 payload.get() 的 fallback 中（没设默认值）→ None
        assert result["last_commit"].get("author") is None

    def test_multiple_events_in_sequence(self):
        """模拟连续多个事件：commit → checkout → ai_session"""
        base = make_event("commit", {"sha": "c1", "message": "first"}, event_id=1)
        checkout = make_event("checkout", {"branch": "feature"}, event_id=2)
        ai = make_event("ai_session", {"summary": "working on feature"}, event_id=3)

        s1 = reduce({}, base)
        s2 = reduce(s1, checkout)
        s3 = reduce(s2, ai)

        assert s3["last_commit"]["sha"] == "c1"
        assert s3["current_branch"] == "feature"
        assert s3["last_ai_action"] == "working on feature"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

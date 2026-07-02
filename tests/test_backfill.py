"""ai-backfill 测试：过滤逻辑 + 补全逻辑"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import init, get_conn


def _create_test_repo_with_commits():
    """创建临时 git repo，写入 5 个混合类型 commit，返回 (repo_dir, 有效个数)"""
    repo_dir = tempfile.mkdtemp()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo_dir, capture_output=True)

    commits = [
        ("WIP: testing", False),
        ("feat: add login", True),
        ("fix: handle edge case", True),
        ("Merge branch dev", False),
        ("refactor: split utils", True),
        ("format: black reformat", False),
        ("docs: update README", True),
        ("style: line length", False),
    ]

    for msg, _ in commits:
        fpath = os.path.join(repo_dir, "dummy.txt")
        with open(fpath, "w") as f:
            f.write(f"{msg}\n")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True)

    ai_dir = os.path.join(repo_dir, ".ai")
    os.makedirs(ai_dir, exist_ok=True)
    db_path = os.path.join(ai_dir, "project.db")
    init(db_path)

    valid_count = sum(1 for _, inc in commits if inc)
    return repo_dir, db_path, valid_count


def _cleanup(repo_dir):
    """Windows 安全清理：git 持有文件句柄，用 bash rm -rf 绕过"""
    import subprocess as sp
    sp.run(["bash", "-c", f"rm -rf '{repo_dir}'"], capture_output=True)
    # fallback
    if os.path.isdir(repo_dir):
        import shutil
        shutil.rmtree(repo_dir, ignore_errors=True)


class TestBackfill:
    def _get_event_count(self, db_path, event_type="commit"):
        conn = sqlite3.connect(db_path)
        c = conn.execute("SELECT COUNT(*) FROM events WHERE type=?", (event_type,)).fetchone()[0]
        conn.close()
        return c

    def test_filter_skip_patterns(self):
        repo_dir, db_path, expected = _create_test_repo_with_commits()
        try:
            subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"), db_path],
                capture_output=True, cwd=repo_dir,
            )
            count = self._get_event_count(db_path)
            assert count == expected, f"Expected {expected} events, got {count}"
        finally:
            _cleanup(repo_dir)

    def test_idempotent(self):
        repo_dir, db_path, expected = _create_test_repo_with_commits()
        try:
            subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"), db_path],
                capture_output=True, cwd=repo_dir,
            )
            subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"), db_path],
                capture_output=True, cwd=repo_dir,
            )
            count = self._get_event_count(db_path)
            assert count == expected, f"Idempotent: expected {expected}, got {count}"
        finally:
            _cleanup(repo_dir)

    def test_backfilled_flag(self):
        repo_dir, db_path, _ = _create_test_repo_with_commits()
        try:
            subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"), db_path],
                capture_output=True, cwd=repo_dir,
            )
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT payload FROM events WHERE type='commit'"
            ).fetchall()
            conn.close()
            for r in rows:
                p = json.loads(r[0])
                assert p.get("backfilled") is True, f"Missing backfilled flag: {p}"
        finally:
            _cleanup(repo_dir)

    def test_audit_no_gaps(self):
        repo_dir, db_path, _ = _create_test_repo_with_commits()
        try:
            subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"), db_path],
                capture_output=True, cwd=repo_dir,
            )
            result = subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "bin", "ai-backfill"),
                 db_path, "--audit"],
                capture_output=True, text=True, cwd=repo_dir,
            )
            assert "no gaps" in result.stdout
        finally:
            _cleanup(repo_dir)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

"""
.ai/ Event System — SQLite封装

提供原子事件写入、状态读写、一致性检查、schema 升级。

用法:
    python db.py init <db_path>              # 初始化数据库
    python db.py migrate <db_path>           # 升级到最新 schema
    python db.py query <db_path> <sql>       # 执行查询
"""
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = 1


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """读取当前 schema 版本，0 表示未初始化"""
    try:
        row = conn.execute(
            "SELECT value FROM state WHERE key='schema_version'"
        ).fetchone()
        if row:
            return int(json.loads(row["value"]))
    except (sqlite3.OperationalError, sqlite3.DatabaseError, ValueError, TypeError):
        pass
    return 0


def _set_schema_version(conn: sqlite3.Connection, version: int):
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
        (
            "schema_version",
            json.dumps(version, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def init(db_path: str):
    conn = get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            project TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
        CREATE INDEX IF NOT EXISTS idx_events_project ON events(project);
    """)
    _set_schema_version(conn, SCHEMA_VERSION)
    conn.commit()
    conn.close()


def migrate(db_path: str):
    """检测并自动升级 schema 版本。未来 v2/v3 的 ALTER TABLE 加在此处。"""
    conn = get_conn(db_path)
    current = _get_schema_version(conn)
    if current >= SCHEMA_VERSION:
        print(f"Schema up to date (v{current})")
        conn.close()
        return

    print(f"Migrating schema v{current} → v{SCHEMA_VERSION}...")

    if current < 1:
        # 从 0 到 1：初始建表（兼容 init 后的空 DB）
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                project TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
            CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
            CREATE INDEX IF NOT EXISTS idx_events_project ON events(project);
        """)

    _set_schema_version(conn, SCHEMA_VERSION)
    conn.commit()
    conn.close()
    print(f"Schema upgraded to v{SCHEMA_VERSION}")


def record_event(
    db_path: str,
    event_type: str,
    payload: dict,
    project: str,
    event_version: int = 1,
) -> dict:
    conn = get_conn(db_path)
    created_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO events (event_version, created_at, type, payload, project) VALUES (?, ?, ?, ?, ?)",
        (event_version, created_at, event_type, json.dumps(payload, ensure_ascii=False), project),
    )
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": event_id, "created_at": created_at}


def set_state(db_path: str, key: str, value):
    conn = get_conn(db_path)
    updated_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(value, ensure_ascii=False), updated_at),
    )
    conn.commit()
    conn.close()


def get_state(db_path: str, key: str):
    conn = get_conn(db_path)
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["value"])
    return None


def get_recent_events(db_path: str, limit: int = 5, event_type: str = None):
    conn = get_conn(db_path)
    if event_type:
        rows = conn.execute(
            "SELECT id, event_version, created_at, type, payload, project FROM events WHERE type = ? ORDER BY id DESC LIMIT ?",
            (event_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, event_version, created_at, type, payload, project FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "event_version": r["event_version"],
            "created_at": r["created_at"],
            "type": r["type"],
            "payload": json.loads(r["payload"]),
            "project": r["project"],
        })
    return result


def check_consistency(db_path: str) -> list:
    """检查 events 和 state 的一致性，返回 warning 列表。
    所有时间比较使用 UTC，与 events 表中的 stored_at 一致。"""
    warnings = []
    conn = get_conn(db_path)

    # 1. state 中有 last_commit 但 events 中没有任何 commit 事件？
    last_commit = conn.execute("SELECT value FROM state WHERE key='last_commit'").fetchone()
    commit_events = conn.execute("SELECT COUNT(*) as cnt FROM events WHERE type='commit'").fetchone()
    if last_commit and commit_events["cnt"] == 0:
        warnings.append("state has last_commit but no commit events")

    # 2. 最近 3 天有 events 吗？（使用 UTC 与 stored_at 一致）
    utc_now = datetime.now(timezone.utc).isoformat()
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    recent = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE created_at > ?",
        (three_days_ago,),
    ).fetchone()
    if recent["cnt"] == 0:
        warnings.append("no events in the last 3 days")

    # 3. state 健康状态检查
    health = conn.execute("SELECT value FROM state WHERE key='status_health'").fetchone()
    if health:
        h = json.loads(health["value"])
        if not h.get("healthy", True):
            warnings.append(f"status_health reported unhealthy: {h}")

    conn.close()
    return warnings


def get_all_state(db_path: str) -> dict:
    """获取所有 state KV 对"""
    conn = get_conn(db_path)
    rows = conn.execute("SELECT key, value FROM state").fetchall()
    conn.close()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def summary(db_path: str) -> str:
    """生成人类可读的状态摘要"""
    state = get_all_state(db_path)
    events = get_recent_events(db_path, 5)

    lines = []
    if "current_branch" in state:
        lines.append(f"分支: {state['current_branch']}")
    if "last_commit" in state:
        c = state["last_commit"]
        lines.append(f"最后提交: {c.get('message', '?')} ({c.get('sha', '?')[:8]})")
    if "dirty_files" in state:
        dirty = state["dirty_files"]
        if dirty:
            lines.append(f"未提交变更: {dirty}")
        else:
            lines.append("工作区干净")
    if "last_ai_action" in state:
        lines.append(f"上次 AI 操作: {state['last_ai_action']}")

    lines.append("")
    lines.append("最近事件:")
    for e in events:
        t = e["created_at"][:19]
        p = e["payload"]
        if e["type"] == "commit":
            lines.append(f"  [{t}] commit: {p.get('message', '?')}")
        elif e["type"] == "checkout":
            lines.append(f"  [{t}] checkout → {p.get('branch', '?')}")
        elif e["type"] == "ai_session":
            lines.append(f"  [{t}] AI: {p.get('summary', '?')}")
        elif e["type"] == "scheduler_check":
            lines.append(f"  [{t}] 检查: {p.get('status', '?')}")
        else:
            lines.append(f"  [{t}] {e['type']}")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python db.py init <db_path>")
        print("       python db.py migrate <db_path>")
        print("       python db.py query <db_path> <sql>")
        print("       python db.py summary <db_path>")
        sys.exit(1)

    cmd = sys.argv[1]
    db_path = sys.argv[2]

    if cmd == "init":
        init(db_path)
        print(f"Initialized: {db_path}")
    elif cmd == "migrate":
        migrate(db_path)
    elif cmd == "query":
        sql = sys.argv[3]
        conn = get_conn(db_path)
        rows = conn.execute(sql).fetchall()
        for r in rows:
            print(dict(r))
        conn.close()
    elif cmd == "summary":
        print(summary(db_path))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

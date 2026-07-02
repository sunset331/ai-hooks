"""
.ai/ Event System — SQLite封装

提供原子事件写入、状态读写、一致性检查、schema 升级。

用法:
    python db.py init <db_path>              # 初始化数据库
    python db.py migrate <db_path>           # 升级到最新 schema
    python db.py query <db_path> <sql>       # 执行查询
"""
import json
import os
import sqlite3
import sys
import time
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


def set_all_state(db_path: str, kv: dict[str, object], retries: int = 1):
    """批量原子写 state。

    在单连接 + 单事务内写入所有 KV 对。
    使用较短 busy_timeout (1000ms) 避免阻塞 git hook 主流程。
    SQLITE_BUSY 时自动重试 1 次。

    Args:
        db_path: SQLite 路径
        kv: key-value 对
        retries: 剩余重试次数
    """
    updated_at = datetime.now(timezone.utc).isoformat()
    for attempt in range(retries + 1):
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA busy_timeout=1000")
            conn.execute("PRAGMA synchronous=NORMAL")
            with conn:
                for key, value in kv.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value, ensure_ascii=False), updated_at),
                    )
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries:
                time.sleep(0.05)
                continue
            raise


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


def _relative_time(iso_str: str) -> str:
    """把 ISO 时间转成"3 小时前"格式"""
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "刚刚"
        if seconds < 3600:
            return f"{seconds // 60} 分钟前"
        if seconds < 86400:
            return f"{seconds // 3600} 小时前"
        if seconds < 604800:
            return f"{seconds // 86400} 天前"
        return f"{seconds // 604800} 周前"
    except Exception:
        return iso_str[:19]


def generate_resume(db_path: str) -> str:
    """生成 Smart Resume — Claude 能直接用的 "你上次做到哪了"

    UX 约束:
        - "上次会话" 只取 1~3 条关键事件 (commit > checkout > ai_session)
        - "建议下一步" 最多 2 条
    """
    state = get_all_state(db_path)
    all_events = get_recent_events(db_path, limit=20)

    lines = []
    lines.append("== 项目摘要 ==")

    project = os.path.basename(os.path.dirname(os.path.dirname(db_path)))
    branch = state.get("current_branch", "?")
    lines.append(f"项目: {project} ({branch} 分支)")

    lc = state.get("last_commit", {})
    if lc:
        when = _relative_time(lc.get("date", ""))
        lines.append(f"最后提交: {lc.get('message', '?')} ({lc.get('sha', '?')[:7]}) — {when}")

    dirty = state.get("dirty_files", 0)
    lines.append(f"工作区: {'干净' if not dirty else f'{dirty} 个文件未提交'}")

    lines.append("")
    lines.append("== 上次会话 ==")

    # 只取关键事件：优先 commit，最多 3 条
    priority_events = [e for e in all_events if e["type"] in ("commit", "checkout", "ai_session")]
    key_events = sorted(priority_events, key=lambda e: e["id"], reverse=True)[:3]

    for e in key_events:
        when = _relative_time(e["created_at"])
        p = e["payload"]
        if e["type"] == "commit":
            lines.append(f"- 提交: {p.get('message', '?')} ({when})")
        elif e["type"] == "checkout":
            lines.append(f"- 切到分支: {p.get('branch', '?')} ({when})")
        elif e["type"] == "ai_session":
            lines.append(f"- AI操作: {p.get('summary', '?')} ({when})")

    # 来自 MEMORY.md 的遗留问题提示（如果有）
    memory_path = os.path.join(os.path.dirname(db_path), "MEMORY.md")
    if os.path.isfile(memory_path):
        lines.append(f"\n踩坑记录: MEMORY.md ({os.path.getsize(memory_path)} bytes)")

    lines.append("")
    lines.append("== 建议下一步 ==")
    ai_action = state.get("last_ai_action")
    if ai_action:
        lines.append(f"1. 继续上次工作: {ai_action}")
    else:
        lines.append("1. 查看 STATUS.md + MEMORY.md 同步上下文")
    lines.append("2. 完成后更新 MEMORY.md 记录新踩坑")

    return "\n".join(lines)


def summary(db_path: str) -> str:
    """生成人类可读的状态摘要"""
    state = get_all_state(db_path)
    events = get_recent_events(db_path, 5)

    lines = []
    if "current_branch" in state:
        lines.append(f"分支: {state['current_branch']}")
    if "last_commit" in state:
        c = state["last_commit"]
        when = _relative_time(c.get("date", ""))
        lines.append(f"最后提交: {c.get('message', '?')} ({c.get('sha', '?')[:8]}) — {when}")
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
        when = _relative_time(e["created_at"])
        p = e["payload"]
        if e["type"] == "commit":
            lines.append(f"  [{when}] commit: {p.get('message', '?')}")
        elif e["type"] == "checkout":
            lines.append(f"  [{when}] checkout → {p.get('branch', '?')}")
        elif e["type"] == "ai_session":
            lines.append(f"  [{when}] AI: {p.get('summary', '?')}")
        elif e["type"] == "scheduler_check":
            lines.append(f"  [{when}] 检查: {p.get('status', '?')}")
        else:
            lines.append(f"  [{when}] {e['type']}")

    return "\n".join(lines)


def display_events(db_path: str, since: str = None) -> str:
    """格式化显示事件时间线。

    Args:
        db_path: SQLite 路径
        since: ISO 时间起点，如 "2026-07-02"。None=最近 20 条

    用法:
        python db.py events <db_path>              # 最近 20 条
        python db.py events <db_path> --today       # 今天
        python db.py events <db_path> --since 2026-07-01  # 指定日期起
    """
    events = get_recent_events(db_path, limit=999)
    if since:
        events = [e for e in events if e["created_at"] >= since]

    if not events:
        return "No events recorded"

    lines = []
    seen_today = []
    prev_date = ""

    for e in reversed(events):  # 正序（最早的在前）
        date = e["created_at"][:10]
        time = e["created_at"][11:16]
        p = e["payload"]

        if date != prev_date:
            if lines:
                lines.append("")
            lines.append(f"── {date} ──")
            prev_date = date

        if e["type"] == "commit":
            msg = p.get("message", "?")
            tag = "backfilled" if p.get("backfilled") else ""
            suffix = f" [{tag}]" if tag else ""
            lines.append(f"  {time}  commit  {msg}{suffix}")
        elif e["type"] == "checkout":
            lines.append(f"  {time}  checkout → {p.get('branch', '?')}")
        elif e["type"] == "ai_session":
            summary = p.get("summary", "?")
            tag = "backfilled" if p.get("backfilled") else ""
            suffix = f" [{tag}]" if tag else ""
            lines.append(f"  {time}  {summary}{suffix}")

    total = len(events)
    if total == 1:
        lines.append(f"\n1 event")
    else:
        lines.append(f"\n{total} events")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python db.py init <db_path>")
        print("       python db.py migrate <db_path>")
        print("       python db.py query <db_path> <sql>")
        print("       python db.py summary <db_path>")
        print("       python db.py events <db_path> [--today|--since DATE]")
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
    elif cmd == "resume":
        print(generate_resume(db_path))
    elif cmd == "events":
        since = None
        if len(sys.argv) >= 4:
            if sys.argv[3] == "--today":
                since = datetime.now(timezone.utc).isoformat()[:10]
            elif sys.argv[3] == "--since" and len(sys.argv) >= 5:
                since = sys.argv[4]
        print(display_events(db_path, since))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

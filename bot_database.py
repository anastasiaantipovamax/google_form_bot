import sqlite3
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "bot_data.db"


def connect():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    return db


def _column_exists(db, table, column):
    rows = db.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(
        row["name"] == column
        for row in rows
    )


def init_db():
    with connect() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                role TEXT NOT NULL DEFAULT 'pending',
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by INTEGER NOT NULL,
                responses_planned INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                status TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT
            )
        """)

        # На случай уже существующей БД.
        if not _column_exists(
            db,
            "shifts",
            "minimum_gap_minutes"
        ):
            db.execute("""
                ALTER TABLE shifts
                ADD COLUMN minimum_gap_minutes
                INTEGER NOT NULL DEFAULT 6
            """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        db.execute("""
            INSERT OR IGNORE INTO settings
            (key, value)
            VALUES ('minimum_gap_minutes', '6')
        """)


# =========================================================
# USERS
# =========================================================

def register_user(
    telegram_id,
    username,
    full_name
):
    with connect() as db:

        existing = db.execute(
            """
            SELECT *
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        ).fetchone()

        if existing:

            db.execute("""
                UPDATE users
                SET username = ?,
                    full_name = ?
                WHERE telegram_id = ?
            """, (
                username,
                full_name,
                telegram_id
            ))

            return get_user(
                telegram_id
            )

        total = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"]

        # Первый пользователь — администратор.
        if total == 0:
            role = "admin"
            approved = 1
        else:
            role = "pending"
            approved = 0

        db.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                full_name,
                role,
                approved,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            telegram_id,
            username,
            full_name,
            role,
            approved,
            datetime.now().isoformat()
        ))

    return get_user(
        telegram_id
    )


def get_user(telegram_id):
    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )


def list_users():
    with connect() as db:

        rows = db.execute("""
            SELECT *
            FROM users
            ORDER BY
                approved ASC,
                created_at DESC
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]


def get_admins():
    with connect() as db:

        rows = db.execute("""
            SELECT *
            FROM users
            WHERE approved = 1
              AND role = 'admin'
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]


def approve_user(
    telegram_id,
    role="manager"
):
    with connect() as db:

        db.execute("""
            UPDATE users
            SET approved = 1,
                role = ?
            WHERE telegram_id = ?
        """, (
            role,
            telegram_id
        ))


def reject_user(
    telegram_id
):
    with connect() as db:

        db.execute("""
            DELETE FROM users
            WHERE telegram_id = ?
              AND role != 'admin'
        """, (
            telegram_id,
        ))


def set_user_role(
    telegram_id,
    role
):
    if role not in (
        "admin",
        "manager",
        "viewer"
    ):
        raise ValueError(
            "Некорректная роль"
        )

    with connect() as db:

        db.execute("""
            UPDATE users
            SET role = ?,
                approved = 1
            WHERE telegram_id = ?
        """, (
            role,
            telegram_id
        ))


# =========================================================
# SETTINGS
# =========================================================

def get_setting(
    key,
    default=None
):
    with connect() as db:

        row = db.execute(
            """
            SELECT value
            FROM settings
            WHERE key = ?
            """,
            (key,)
        ).fetchone()

        if not row:
            return default

        return row["value"]


def set_setting(
    key,
    value
):
    with connect() as db:

        db.execute("""
            INSERT INTO settings (
                key,
                value
            )
            VALUES (?, ?)

            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value
        """, (
            key,
            str(value)
        ))


# =========================================================
# SHIFTS
# =========================================================

def create_shift(
    created_by,
    count,
    start_time,
    end_time,
    minimum_gap_minutes=6
):
    with connect() as db:

        cursor = db.execute("""
            INSERT INTO shifts (
                created_by,
                responses_planned,
                start_time,
                end_time,
                minimum_gap_minutes,
                status,
                completed,
                skipped,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'created',
                0,
                0,
                ?
            )
        """, (
            created_by,
            count,
            start_time,
            end_time,
            minimum_gap_minutes,
            datetime.now().isoformat()
        ))

        return cursor.lastrowid


def get_shift(
    shift_id
):
    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM shifts
            WHERE id = ?
            """,
            (shift_id,)
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )


def get_active_shift():
    with connect() as db:

        row = db.execute("""
            SELECT *
            FROM shifts
            WHERE status IN (
                'created',
                'running',
                'paused'
            )
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        return (
            dict(row)
            if row
            else None
        )


def update_shift_status(
    shift_id,
    status
):
    with connect() as db:

        if status == "running":

            db.execute("""
                UPDATE shifts
                SET status = ?,
                    started_at =
                        COALESCE(
                            started_at,
                            ?
                        )
                WHERE id = ?
            """, (
                status,
                datetime.now().isoformat(),
                shift_id
            ))

        elif status in (
            "completed",
            "cancelled"
        ):

            db.execute("""
                UPDATE shifts
                SET status = ?,
                    ended_at = ?
                WHERE id = ?
            """, (
                status,
                datetime.now().isoformat(),
                shift_id
            ))

        else:

            db.execute("""
                UPDATE shifts
                SET status = ?
                WHERE id = ?
            """, (
                status,
                shift_id
            ))


def update_shift_progress(
    shift_id,
    completed,
    skipped
):
    with connect() as db:

        db.execute("""
            UPDATE shifts
            SET completed = ?,
                skipped = ?
            WHERE id = ?
        """, (
            completed,
            skipped,
            shift_id
        ))


def list_shifts(
    limit=10
):
    with connect() as db:

        rows = db.execute("""
            SELECT
                shifts.*,
                users.full_name
                    AS creator_name

            FROM shifts

            LEFT JOIN users
                ON users.telegram_id =
                   shifts.created_by

            ORDER BY shifts.id DESC

            LIMIT ?
        """, (
            limit,
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]


def get_last_shift():
    with connect() as db:

        row = db.execute("""
            SELECT *
            FROM shifts
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        return (
            dict(row)
            if row
            else None
        )
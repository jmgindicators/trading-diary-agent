"""SQLite storage for trades, analyses, and summaries."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Trade, TradeAnalysis, TradeDirection

DEFAULT_DB = Path("data/trades.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    pnl REAL NOT NULL,
    commission REAL DEFAULT 0,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL UNIQUE,
    setup_type TEXT,
    quality_score INTEGER,
    entry_quality TEXT,
    exit_quality TEXT,
    lesson_learned TEXT,
    pattern_tags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_value TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_type, period_value)
);

CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_analyses_trade_id ON analyses(trade_id);
"""


def init_db(db_path: Path = DEFAULT_DB) -> None:
    """Create the database schema if it doesn't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_db(db_path: Path = DEFAULT_DB):
    """Open a database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_trade(trade: Trade, db_path: Path = DEFAULT_DB) -> int:
    """Insert a trade and return its id."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO trades (instrument, entry_time, exit_time, direction,
                                entry_price, exit_price, quantity, pnl, commission, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.instrument,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat(),
                trade.direction.value,
                trade.entry_price,
                trade.exit_price,
                trade.quantity,
                trade.pnl,
                trade.commission,
                trade.notes,
            ),
        )
        return cur.lastrowid


def fetch_trade(trade_id: int, db_path: Path = DEFAULT_DB) -> Trade | None:
    """Fetch a single trade by id."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        return _row_to_trade(row) if row else None


def fetch_trades(
    db_path: Path = DEFAULT_DB,
    date_prefix: str | None = None,
    limit: int | None = None,
) -> list[Trade]:
    """Fetch trades, optionally filtered by date prefix (YYYY-MM-DD or YYYY-MM)."""
    query = "SELECT * FROM trades"
    params: tuple = ()
    if date_prefix:
        query += " WHERE entry_time LIKE ?"
        params = (f"{date_prefix}%",)
    query += " ORDER BY entry_time"
    if limit:
        query += f" LIMIT {int(limit)}"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_trade(r) for r in rows]


def fetch_unanalyzed_trades(db_path: Path = DEFAULT_DB) -> list[Trade]:
    """Fetch trades that have not yet been analyzed."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT t.* FROM trades t
            LEFT JOIN analyses a ON a.trade_id = t.id
            WHERE a.id IS NULL
            ORDER BY t.entry_time
            """
        ).fetchall()
        return [_row_to_trade(r) for r in rows]


def upsert_analysis(analysis: TradeAnalysis, db_path: Path = DEFAULT_DB) -> None:
    """Insert or replace an analysis for a trade."""
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO analyses (trade_id, setup_type, quality_score, entry_quality,
                                  exit_quality, lesson_learned, pattern_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_id) DO UPDATE SET
                setup_type=excluded.setup_type,
                quality_score=excluded.quality_score,
                entry_quality=excluded.entry_quality,
                exit_quality=excluded.exit_quality,
                lesson_learned=excluded.lesson_learned,
                pattern_tags=excluded.pattern_tags
            """,
            (
                analysis.trade_id,
                analysis.setup_type.value,
                analysis.quality_score,
                analysis.entry_quality,
                analysis.exit_quality,
                analysis.lesson_learned,
                json.dumps(analysis.pattern_tags),
            ),
        )


def fetch_analysis(trade_id: int, db_path: Path = DEFAULT_DB) -> TradeAnalysis | None:
    """Fetch the analysis for a given trade."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE trade_id = ?", (trade_id,)
        ).fetchone()
        if not row:
            return None
        return TradeAnalysis(
            trade_id=row["trade_id"],
            setup_type=row["setup_type"],
            quality_score=row["quality_score"],
            entry_quality=row["entry_quality"],
            exit_quality=row["exit_quality"],
            lesson_learned=row["lesson_learned"],
            pattern_tags=json.loads(row["pattern_tags"] or "[]"),
        )


def save_summary(period_type: str, period_value: str, content: str,
                 db_path: Path = DEFAULT_DB) -> None:
    """Persist a generated summary (day/week/month)."""
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO summaries (period_type, period_value, content)
            VALUES (?, ?, ?)
            ON CONFLICT(period_type, period_value) DO UPDATE SET
                content=excluded.content,
                created_at=CURRENT_TIMESTAMP
            """,
            (period_type, period_value, content),
        )


def _row_to_trade(row: sqlite3.Row) -> Trade:
    return Trade(
        id=row["id"],
        instrument=row["instrument"],
        entry_time=row["entry_time"],
        exit_time=row["exit_time"],
        direction=TradeDirection(row["direction"]),
        entry_price=row["entry_price"],
        exit_price=row["exit_price"],
        quantity=row["quantity"],
        pnl=row["pnl"],
        commission=row["commission"],
        notes=row["notes"] or "",
    )

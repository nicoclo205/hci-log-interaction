"""Database manager for HCI Logger"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any


class Database:
    """Simple SQLite database manager"""

    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "hci_logger.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Access columns by name

        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        return self.conn

    def initialize(self):
        """Initialize database with schema"""
        if self.conn is None:
            self.connect()

        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            schema = f.read()

        self.conn.executescript(schema)
        self.conn.commit()

        print(f"✓ Database initialized at {self.db_path}")

    def create_session(
        self,
        session_uuid: str,
        participant_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        target_url: Optional[str] = None,
        screen_width: Optional[int] = None,
        screen_height: Optional[int] = None
    ) -> int:
        """Create a new session and return its ID"""
        cursor = self.conn.execute(
            """
            INSERT INTO sessions
            (session_uuid, start_time, participant_id, experiment_id,
             target_url, screen_width, screen_height, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (session_uuid, time.time(), participant_id, experiment_id,
             target_url, screen_width, screen_height)
        )
        self.conn.commit()
        return cursor.lastrowid

    def end_session(self, session_id: int):
        """Mark session as completed"""
        self.conn.execute(
            """
            UPDATE sessions
            SET end_time = ?, status = 'completed', updated_at = ?
            WHERE id = ?
            """,
            (time.time(), time.time(), session_id)
        )
        self.conn.commit()

    def insert_mouse_event(
        self,
        session_id: int,
        timestamp: float,
        event_type: str,
        x: int,
        y: int,
        button: Optional[str] = None,
        pressed: Optional[bool] = None,
        scroll_dx: Optional[float] = None,
        scroll_dy: Optional[float] = None
    ):
        """Insert a single mouse event"""
        self.conn.execute(
            """
            INSERT INTO mouse_events
            (session_id, timestamp, event_type, x, y, button, pressed, scroll_dx, scroll_dy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, event_type, x, y, button, pressed, scroll_dx, scroll_dy)
        )

    def insert_mouse_events_batch(self, events: list):
        """Insert multiple mouse events in batch"""
        self.conn.executemany(
            """
            INSERT INTO mouse_events
            (session_id, timestamp, event_type, x, y, button, pressed, scroll_dx, scroll_dy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            events
        )
        self.conn.commit()

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_mouse_events(self, session_id: int) -> list:
        """Get all mouse events for a session"""
        cursor = self.conn.execute(
            """
            SELECT * FROM mouse_events
            WHERE session_id = ?
            ORDER BY timestamp
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_event_count(self, session_id: int) -> int:
        """Get total event count for session"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM mouse_events WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()['count']

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

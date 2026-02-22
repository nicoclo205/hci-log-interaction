# -*- coding: utf-8 -*-
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
        # check_same_thread=False permite usar la conexión desde múltiples threads
        # Esto es seguro porque ya usamos WAL mode que soporta concurrencia
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        return self.conn

    def initialize(self):
        """Initialize database with schema and run migrations"""
        if self.conn is None:
            self.connect()

        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            schema = f.read()

        self.conn.executescript(schema)
        self.conn.commit()

        # Migrations: add task_id to existing tables if missing
        migrations = [
            "ALTER TABLE mouse_events ADD COLUMN task_id INTEGER DEFAULT 0",
            "ALTER TABLE screenshots ADD COLUMN task_id INTEGER DEFAULT 0",
            "ALTER TABLE emotion_events ADD COLUMN task_id INTEGER DEFAULT 0",
            "ALTER TABLE audio_segments ADD COLUMN task_id INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                self.conn.execute(sql)
                self.conn.commit()
            except Exception:
                pass  # Column already exists

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
        """Insert multiple mouse events in batch.

        Accepts tuples of 9 elements (legacy) or 10 elements (with task_id).
        """
        if not events:
            return
        if len(events[0]) == 10:
            self.conn.executemany(
                """
                INSERT INTO mouse_events
                (session_id, timestamp, event_type, x, y, button, pressed,
                 scroll_dx, scroll_dy, task_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                events
            )
        else:
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

    def insert_screenshot(
        self,
        session_id: int,
        timestamp: float,
        file_path: str,
        file_size: int,
        width: int,
        height: int,
        format: str = 'png',
        trigger_event_type: str = None,
        trigger_x: int = None,
        trigger_y: int = None,
        trigger_metadata: str = None,
        task_id: int = 0
    ):
        """Insert a screenshot record"""
        self.conn.execute(
            """
            INSERT INTO screenshots
            (session_id, timestamp, file_path, file_size, width, height, format,
             trigger_event_type, trigger_x, trigger_y, trigger_metadata, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, file_path, file_size, width, height, format,
             trigger_event_type, trigger_x, trigger_y, trigger_metadata, task_id)
        )
        self.conn.commit()

    def get_screenshots(self, session_id: int) -> list:
        """Get all screenshots for a session"""
        cursor = self.conn.execute(
            """
            SELECT * FROM screenshots
            WHERE session_id = ?
            ORDER BY timestamp
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_screenshot_count(self, session_id: int) -> int:
        """Get total screenshot count for session"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM screenshots WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()['count']

    def insert_audio_segment(
        self,
        session_id: int,
        start_timestamp: float,
        end_timestamp: float,
        duration: float,
        file_path: str,
        sample_rate: int,
        channels: int,
        file_size: int,
        task_id: int = 0
    ):
        """Insert an audio segment record"""
        self.conn.execute(
            """
            INSERT INTO audio_segments
            (session_id, start_timestamp, end_timestamp, duration,
             file_path, sample_rate, channels, file_size, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, start_timestamp, end_timestamp, duration,
             file_path, sample_rate, channels, file_size, task_id)
        )
        self.conn.commit()

    def get_audio_segments(self, session_id: int) -> list:
        """Get all audio segments for a session"""
        cursor = self.conn.execute(
            """
            SELECT * FROM audio_segments
            WHERE session_id = ?
            ORDER BY start_timestamp
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_audio_segment_count(self, session_id: int) -> int:
        """Get total audio segment count for session"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM audio_segments WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()['count']

    def get_total_audio_duration(self, session_id: int) -> float:
        """Get total audio duration for session in seconds"""
        cursor = self.conn.execute(
            "SELECT SUM(duration) as total FROM audio_segments WHERE session_id = ?",
            (session_id,)
        )
        result = cursor.fetchone()['total']
        return result if result else 0.0

    def insert_emotion_event(
        self,
        session_id: int,
        timestamp: float,
        angry: float,
        disgust: float,
        fear: float,
        happy: float,
        sad: float,
        surprise: float,
        neutral: float,
        dominant_emotion: str,
        face_confidence: float = None,
        age: int = None,
        gender: str = None,
        task_id: int = 0
    ):
        """Insert an emotion detection event"""
        self.conn.execute(
            """
            INSERT INTO emotion_events
            (session_id, timestamp, angry, disgust, fear, happy, sad, surprise, neutral,
             dominant_emotion, face_confidence, age, gender, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, angry, disgust, fear, happy, sad, surprise, neutral,
             dominant_emotion, face_confidence, age, gender, task_id)
        )
        self.conn.commit()

    def get_emotion_events(self, session_id: int) -> list:
        """Get all emotion events for a session"""
        cursor = self.conn.execute(
            """
            SELECT * FROM emotion_events
            WHERE session_id = ?
            ORDER BY timestamp
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_emotion_event_count(self, session_id: int) -> int:
        """Get total emotion event count for session"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM emotion_events WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()['count']

    def get_dominant_emotions_summary(self, session_id: int) -> dict:
        """Get summary of dominant emotions for session"""
        cursor = self.conn.execute(
            """
            SELECT dominant_emotion, COUNT(*) as count
            FROM emotion_events
            WHERE session_id = ?
            GROUP BY dominant_emotion
            ORDER BY count DESC
            """,
            (session_id,)
        )
        return {row['dominant_emotion']: row['count'] for row in cursor.fetchall()}

    def insert_eye_event(
        self,
        session_id: int,
        timestamp: float,
        left_pupil_x: float = None,
        left_pupil_y: float = None,
        right_pupil_x: float = None,
        right_pupil_y: float = None,
        gaze_x: float = None,
        gaze_y: float = None,
        left_eye_open: bool = None,
        right_eye_open: bool = None,
        head_pose_x: float = None,
        head_pose_y: float = None,
        head_pose_z: float = None,
        is_calibrated: bool = False
    ):
        """Insert an eye tracking event"""
        self.conn.execute(
            """
            INSERT INTO eye_events
            (session_id, timestamp, left_pupil_x, left_pupil_y, right_pupil_x, right_pupil_y,
             gaze_x, gaze_y, left_eye_open, right_eye_open,
             head_pose_x, head_pose_y, head_pose_z, is_calibrated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, timestamp, left_pupil_x, left_pupil_y, right_pupil_x, right_pupil_y,
             gaze_x, gaze_y, left_eye_open, right_eye_open,
             head_pose_x, head_pose_y, head_pose_z, is_calibrated)
        )
        self.conn.commit()

    def get_eye_events(self, session_id: int, calibrated_only: bool = False) -> list:
        """Get all eye tracking events for a session"""
        query = """
            SELECT * FROM eye_events
            WHERE session_id = ?
        """
        if calibrated_only:
            query += " AND is_calibrated = 1"
        query += " ORDER BY timestamp"

        cursor = self.conn.execute(query, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_eye_event_count(self, session_id: int) -> int:
        """Get total eye event count for session"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM eye_events WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()['count']

    def insert_transcription(
        self,
        session_id: int,
        task_id: int,
        timestamp: float,
        text: str,
        audio_file: str = None
    ):
        """Insert a Whisper transcription result"""
        self.conn.execute(
            """
            INSERT INTO transcriptions (session_id, task_id, timestamp, text, audio_file)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, task_id, timestamp, text, audio_file)
        )
        self.conn.commit()

    def get_transcriptions(self, session_id: int) -> list:
        """Get all transcriptions for a session"""
        cursor = self.conn.execute(
            """
            SELECT * FROM transcriptions
            WHERE session_id = ?
            ORDER BY timestamp
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

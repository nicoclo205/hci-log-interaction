-- Schema para HCI Logger
-- Versión: 1.0.0

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uuid TEXT UNIQUE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    participant_id TEXT,
    experiment_id TEXT,
    target_url TEXT,
    screen_width INTEGER,
    screen_height INTEGER,
    status TEXT CHECK(status IN ('active', 'completed', 'error')) DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_uuid ON sessions(session_uuid);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_sessions_participant ON sessions(participant_id);

-- Mouse events table
CREATE TABLE IF NOT EXISTS mouse_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    event_type TEXT CHECK(event_type IN ('move', 'click', 'scroll')) NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    button TEXT,  -- 'left', 'right', 'middle', null for moves
    pressed BOOLEAN,
    scroll_dx REAL,
    scroll_dy REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mouse_session ON mouse_events(session_id);
CREATE INDEX IF NOT EXISTS idx_mouse_timestamp ON mouse_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_mouse_type ON mouse_events(event_type);

-- Database metadata
CREATE TABLE IF NOT EXISTS db_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('version', '1.0.0');
INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('created_at', datetime('now'));

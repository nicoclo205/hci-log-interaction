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
    task_id INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mouse_session ON mouse_events(session_id);
CREATE INDEX IF NOT EXISTS idx_mouse_timestamp ON mouse_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_mouse_type ON mouse_events(event_type);

-- Screenshot captures table
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    format TEXT,
    -- Metadata del evento que triggereó el screenshot
    trigger_event_type TEXT,  -- 'click', 'scroll', 'periodic', null
    trigger_x INTEGER,        -- Coordenada X del evento trigger
    trigger_y INTEGER,        -- Coordenada Y del evento trigger
    trigger_metadata TEXT,    -- JSON con metadata adicional del evento
    task_id INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_screenshot_session ON screenshots(session_id);
CREATE INDEX IF NOT EXISTS idx_screenshot_timestamp ON screenshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_screenshot_trigger_type ON screenshots(trigger_event_type);

-- Audio segments table
CREATE TABLE IF NOT EXISTS audio_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    start_timestamp REAL NOT NULL,
    end_timestamp REAL NOT NULL,
    duration REAL NOT NULL,
    file_path TEXT NOT NULL,
    sample_rate INTEGER,
    channels INTEGER,
    file_size INTEGER,
    task_id INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audio_session ON audio_segments(session_id);
CREATE INDEX IF NOT EXISTS idx_audio_start ON audio_segments(start_timestamp);

-- Emotion detection events table
CREATE TABLE IF NOT EXISTS emotion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    angry REAL CHECK(angry >= 0 AND angry <= 1),
    disgust REAL CHECK(disgust >= 0 AND disgust <= 1),
    fear REAL CHECK(fear >= 0 AND fear <= 1),
    happy REAL CHECK(happy >= 0 AND happy <= 1),
    sad REAL CHECK(sad >= 0 AND sad <= 1),
    surprise REAL CHECK(surprise >= 0 AND surprise <= 1),
    neutral REAL CHECK(neutral >= 0 AND neutral <= 1),
    dominant_emotion TEXT,
    face_confidence REAL,
    age INTEGER,
    gender TEXT,
    task_id INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emotion_session ON emotion_events(session_id);
CREATE INDEX IF NOT EXISTS idx_emotion_timestamp ON emotion_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_emotion_dominant ON emotion_events(dominant_emotion);

-- Eye tracking events table
CREATE TABLE IF NOT EXISTS eye_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    left_pupil_x REAL,
    left_pupil_y REAL,
    right_pupil_x REAL,
    right_pupil_y REAL,
    gaze_x REAL,
    gaze_y REAL,
    left_eye_open BOOLEAN,
    right_eye_open BOOLEAN,
    head_pose_x REAL,
    head_pose_y REAL,
    head_pose_z REAL,
    is_calibrated BOOLEAN DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eye_session ON eye_events(session_id);
CREATE INDEX IF NOT EXISTS idx_eye_timestamp ON eye_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_eye_calibrated ON eye_events(is_calibrated);

-- Transcriptions (Whisper output)
CREATE TABLE IF NOT EXISTS transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    task_id INTEGER DEFAULT 0,
    timestamp REAL NOT NULL,
    text TEXT NOT NULL,
    audio_file TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcription_session ON transcriptions(session_id);
CREATE INDEX IF NOT EXISTS idx_transcription_task ON transcriptions(task_id);

-- Database metadata
CREATE TABLE IF NOT EXISTS db_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('version', '1.0.0');
INSERT OR IGNORE INTO db_metadata (key, value) VALUES ('created_at', datetime('now'));

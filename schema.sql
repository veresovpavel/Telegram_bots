CREATE TABLE IF NOT EXISTS events (
  chat_id INTEGER,
  message_id INTEGER,
  event_name TEXT,
  has_keepers INTEGER,
  is_closed INTEGER,
  PRIMARY KEY (chat_id, message_id)
);

CREATE TABLE IF NOT EXISTS participants (
  chat_id INTEGER,
  message_id INTEGER,
  user_id INTEGER,
  user_name TEXT,
  status TEXT,
  plus_count INTEGER DEFAULT 0,
  keeper_plus_count INTEGER DEFAULT 0,
  status_seq INTEGER DEFAULT 0,
  PRIMARY KEY (chat_id, message_id, user_id)
);

CREATE TABLE IF NOT EXISTS bot_admins (
  user_id INTEGER PRIMARY KEY,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  added_by INTEGER
);
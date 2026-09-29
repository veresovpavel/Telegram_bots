-- Telegram Event Bot: schema for Cloudflare D1
-- Применение: wrangler d1 execute events-db --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS events (
  message_id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  event_name TEXT,
  has_keepers INTEGER,
  is_closed INTEGER
);

CREATE TABLE IF NOT EXISTS participants (
  message_id INTEGER,
  user_id INTEGER,
  user_name TEXT,
  status TEXT,
  plus_count INTEGER DEFAULT 0,
  keeper_plus_count INTEGER DEFAULT 0,
  PRIMARY KEY (message_id, user_id)
);

CREATE TABLE IF NOT EXISTS bot_admins (
  user_id INTEGER PRIMARY KEY,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  added_by INTEGER
);
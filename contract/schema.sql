CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY,
  captured_paise INTEGER NOT NULL,
  refunded_paise INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE ledger (
  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('capture','refund')),
  amount_paise INTEGER NOT NULL,
  event_id TEXT
);

CREATE TABLE reports (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,
  report_day TEXT NOT NULL,
  variant TEXT NOT NULL,
  plate_key TEXT NOT NULL,
  plate_dish_ids TEXT NOT NULL,
  tapped_dish_id TEXT NOT NULL,
  device_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX reports_device_day ON reports(device_id, report_day);
CREATE INDEX reports_date_plate ON reports(date, plate_key, device_id);

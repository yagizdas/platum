ALTER TABLE reports ADD COLUMN campus TEXT NOT NULL DEFAULT 'arcisstr';
CREATE INDEX reports_campus_date_plate ON reports(campus, date, plate_key, device_id);

-- Clean ANSI escape codes from room names and descriptions
-- Run this to fix room names like: ␛[0;33mThe Entrance To The Newbie Zone␛[0m

-- Remove color codes [0;33m, [31m, etc.
UPDATE rooms SET name = TRIM(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  name,
  '[0;33m', ''), '[0;31m', ''), '[0;32m', ''), '[0;34m', ''), '[0;35m', ''),
  '[0;36m', ''), '[0;37m', ''), '[1;33m', ''), '[1;31m', ''), '[1;32m', ''),
  '[1;34m', ''), '[1;35m', ''), '[1;36m', ''), '[1;37m', ''), '[33m', ''),
  '[31m', ''), '[32m', ''), '[34m', ''), '[35m', ''), '[36m', ''), '[37m', ''),
  '[0m', '')
);

UPDATE rooms SET description = TRIM(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  description,
  '[0;33m', ''), '[0;31m', ''), '[0;32m', ''), '[0;34m', ''), '[0;35m', ''),
  '[0;36m', ''), '[0;37m', ''), '[1;33m', ''), '[1;31m', ''), '[1;32m', ''),
  '[1;34m', ''), '[1;35m', ''), '[1;36m', ''), '[1;37m', ''), '[33m', ''),
  '[31m', ''), '[32m', ''), '[34m', ''), '[35m', ''), '[36m', ''), '[37m', ''),
  '[0m', '')
);

UPDATE rooms SET summary = TRIM(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
  summary,
  '[0;33m', ''), '[0;31m', ''), '[0;32m', ''), '[0;34m', ''), '[0;35m', ''),
  '[0;36m', ''), '[0;37m', ''), '[1;33m', ''), '[1;31m', ''), '[1;32m', ''),
  '[1;34m', ''), '[1;35m', ''), '[1;36m', ''), '[1;37m', ''), '[33m', ''),
  '[31m', ''), '[32m', ''), '[34m', ''), '[35m', ''), '[36m', ''), '[37m', ''),
  '[0m', '')
);

-- Verify changes
SELECT COUNT(*) as cleaned_rooms FROM rooms WHERE name LIKE '%[%m%';

-- Clean ANSI escape codes including ESC character (␛) from room names
-- Handles both: ␛[0;33mText␛[0m and [0;33mText[0m patterns

-- First, remove ESC character (hex 1B or octal 033)
UPDATE rooms SET name = REPLACE(name, CHAR(27), '');
UPDATE rooms SET description = REPLACE(description, CHAR(27), '');
UPDATE rooms SET summary = REPLACE(summary, CHAR(27), '');

-- Then remove bracket codes [0;33m, [31m, etc.
UPDATE rooms SET name = REPLACE(name, '[0;33m', '');
UPDATE rooms SET name = REPLACE(name, '[0;31m', '');
UPDATE rooms SET name = REPLACE(name, '[0;32m', '');
UPDATE rooms SET name = REPLACE(name, '[0;34m', '');
UPDATE rooms SET name = REPLACE(name, '[0;35m', '');
UPDATE rooms SET name = REPLACE(name, '[0;36m', '');
UPDATE rooms SET name = REPLACE(name, '[0;37m', '');
UPDATE rooms SET name = REPLACE(name, '[1;33m', '');
UPDATE rooms SET name = REPLACE(name, '[1;31m', '');
UPDATE rooms SET name = REPLACE(name, '[1;32m', '');
UPDATE rooms SET name = REPLACE(name, '[1;34m', '');
UPDATE rooms SET name = REPLACE(name, '[1;35m', '');
UPDATE rooms SET name = REPLACE(name, '[1;36m', '');
UPDATE rooms SET name = REPLACE(name, '[1;37m', '');
UPDATE rooms SET name = REPLACE(name, '[33m', '');
UPDATE rooms SET name = REPLACE(name, '[31m', '');
UPDATE rooms SET name = REPLACE(name, '[32m', '');
UPDATE rooms SET name = REPLACE(name, '[34m', '');
UPDATE rooms SET name = REPLACE(name, '[35m', '');
UPDATE rooms SET name = REPLACE(name, '[36m', '');
UPDATE rooms SET name = REPLACE(name, '[37m', '');
UPDATE rooms SET name = REPLACE(name, '[0m', '');

-- Same for descriptions
UPDATE rooms SET description = REPLACE(description, '[0;33m', '');
UPDATE rooms SET description = REPLACE(description, '[0;31m', '');
UPDATE rooms SET description = REPLACE(description, '[0;32m', '');
UPDATE rooms SET description = REPLACE(description, '[0;34m', '');
UPDATE rooms SET description = REPLACE(description, '[0;35m', '');
UPDATE rooms SET description = REPLACE(description, '[0;36m', '');
UPDATE rooms SET description = REPLACE(description, '[0;37m', '');
UPDATE rooms SET description = REPLACE(description, '[1;33m', '');
UPDATE rooms SET description = REPLACE(description, '[1;31m', '');
UPDATE rooms SET description = REPLACE(description, '[1;32m', '');
UPDATE rooms SET description = REPLACE(description, '[1;34m', '');
UPDATE rooms SET description = REPLACE(description, '[1;35m', '');
UPDATE rooms SET description = REPLACE(description, '[1;36m', '');
UPDATE rooms SET description = REPLACE(description, '[1;37m', '');
UPDATE rooms SET description = REPLACE(description, '[33m', '');
UPDATE rooms SET description = REPLACE(description, '[31m', '');
UPDATE rooms SET description = REPLACE(description, '[32m', '');
UPDATE rooms SET description = REPLACE(description, '[34m', '');
UPDATE rooms SET description = REPLACE(description, '[35m', '');
UPDATE rooms SET description = REPLACE(description, '[36m', '');
UPDATE rooms SET description = REPLACE(description, '[37m', '');
UPDATE rooms SET description = REPLACE(description, '[0m', '');

-- Same for summaries
UPDATE rooms SET summary = REPLACE(summary, '[0;33m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;31m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;32m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;34m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;35m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;36m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0;37m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;33m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;31m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;32m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;34m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;35m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;36m', '');
UPDATE rooms SET summary = REPLACE(summary, '[1;37m', '');
UPDATE rooms SET summary = REPLACE(summary, '[33m', '');
UPDATE rooms SET summary = REPLACE(summary, '[31m', '');
UPDATE rooms SET summary = REPLACE(summary, '[32m', '');
UPDATE rooms SET summary = REPLACE(summary, '[34m', '');
UPDATE rooms SET summary = REPLACE(summary, '[35m', '');
UPDATE rooms SET summary = REPLACE(summary, '[36m', '');
UPDATE rooms SET summary = REPLACE(summary, '[37m', '');
UPDATE rooms SET summary = REPLACE(summary, '[0m', '');

-- Trim whitespace
UPDATE rooms SET name = TRIM(name);
UPDATE rooms SET description = TRIM(description);
UPDATE rooms SET summary = TRIM(summary);

-- Verify cleanup
SELECT 'Cleanup complete! Cleaned' as message;
SELECT COUNT(*) as rooms_with_escape_codes FROM rooms WHERE name LIKE '%' || CHAR(27) || '%';

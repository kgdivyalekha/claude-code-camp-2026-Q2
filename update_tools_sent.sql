-- Update tools_sent column by extracting tool_count from prompt event details
-- This script updates the existing events.db without rebuilding

UPDATE events
SET tools_sent = (
  SELECT json_extract(e.details, '$.tool_count')
  FROM events e
  WHERE e.session_id = events.session_id
    AND e.turn = events.turn
    AND e.iteration = events.iteration
    AND e.phase = 'prompt'
  LIMIT 1
)
WHERE phase = 'response'
  AND session_id = '20260803T220918Z-7975a5d3'
  AND tools_sent IS NULL;

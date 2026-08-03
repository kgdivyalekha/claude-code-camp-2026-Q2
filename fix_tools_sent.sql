-- Fix tools_sent by copying tool_count from prompt events to response events
-- This requires parsing the JSON details column

BEGIN TRANSACTION;

-- Create a temporary table to hold tool_count extracted from prompt events
CREATE TEMP TABLE prompt_tools AS
SELECT
  session_id,
  turn,
  iteration,
  json_extract(details, '$.tool_count') as tool_count
FROM events
WHERE phase = 'prompt'
  AND json_extract(details, '$.tool_count') IS NOT NULL;

-- Update response events with tool_count from matching prompt events
UPDATE events
SET tools_sent = (
  SELECT tool_count
  FROM prompt_tools
  WHERE prompt_tools.session_id = events.session_id
    AND prompt_tools.turn = events.turn
    AND prompt_tools.iteration = events.iteration
  LIMIT 1
)
WHERE phase = 'response'
  AND tools_sent IS NULL;

COMMIT;

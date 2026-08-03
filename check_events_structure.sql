.mode line
.headers on

-- Check first few prompt and response events from the session
SELECT 'PROMPT EVENTS' as type;
SELECT session_id, turn, iteration, json_extract(details, '$.tool_count') as tool_count
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'prompt'
LIMIT 5;

SELECT 'RESPONSE EVENTS' as type;
SELECT session_id, turn, iteration, tools_sent, json_extract(details, '$.tool_count') as tool_count_in_json
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'response'
LIMIT 5;

-- Count how many response events have NULL tools_sent
SELECT 'SUMMARY' as type;
SELECT COUNT(*) as total_response_events,
       COUNT(CASE WHEN tools_sent IS NULL THEN 1 END) as null_tools_sent
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'response';

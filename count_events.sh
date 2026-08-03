#!/bin/bash
# Count events for the session

echo "Events in database:"
echo "20260803T220918Z-7975a5d3:"
grep -c '"20260803T220918Z-7975a5d3"' .boukensha/sessions/*.jsonl 2>/dev/null || echo "  0 (JSONL file doesn't exist)"

echo ""
echo "Available sessions with event counts:"
for file in .boukensha/sessions/*.jsonl; do
  sid=$(basename "$file" .jsonl)
  count=$(grep -c "\"$sid\"" "$file" 2>/dev/null || echo "0")
  echo "  $sid: $count events"
done

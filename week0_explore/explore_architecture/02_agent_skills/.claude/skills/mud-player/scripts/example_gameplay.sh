#!/bin/bash
# Example MUD gameplay session using mud_connection.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "=== MUD Player Skill Example ==="
echo ""

# Step 1: Initialize session
echo "1. Initializing session with queen/password..."
INIT_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --action init --login queen --password password)
SESSION_ID=$(echo "$INIT_RESULT" | grep -o '"session_id": "[^"]*' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
    echo "Failed to initialize session:"
    echo "$INIT_RESULT"
    exit 1
fi

echo "✓ Session created: $SESSION_ID"
echo ""
echo "Initial state:"
echo "$INIT_RESULT" | python3 -m json.tool 2>/dev/null | head -30
echo ""

# Step 2: Check inventory
echo "2. Checking inventory..."
INV_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action execute --command "inventory")
echo "$INV_RESULT" | python3 -m json.tool 2>/dev/null
echo ""

# Step 3: Move north
echo "3. Moving north..."
NORTH_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action execute --command "north")
echo "$NORTH_RESULT" | python3 -m json.tool 2>/dev/null | head -20
echo ""

# Step 4: Look around
echo "4. Looking around the new room..."
LOOK_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action execute --command "look")
echo "$LOOK_RESULT" | python3 -m json.tool 2>/dev/null | head -20
echo ""

# Step 5: Move south (back)
echo "5. Moving south (back to original room)..."
SOUTH_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action execute --command "south")
echo "$SOUTH_RESULT" | python3 -m json.tool 2>/dev/null | head -20
echo ""

# Step 6: Try an invalid command
echo "6. Trying invalid command (should return error)..."
INVALID_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action execute --command "cast nonexistent_spell")
echo "$INVALID_RESULT" | python3 -m json.tool 2>/dev/null
echo ""

# Step 7: Close session
echo "7. Closing session..."
CLOSE_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --session-id "$SESSION_ID" --action close)
echo "$CLOSE_RESULT" | python3 -m json.tool 2>/dev/null
echo ""

# Step 8: Verify session is closed
echo "8. Checking active sessions..."
STATUS_RESULT=$($PYTHON "$SCRIPT_DIR/mud_connection.py" --action status)
echo "$STATUS_RESULT" | python3 -m json.tool 2>/dev/null
echo ""

echo "✓ Example gameplay complete!"

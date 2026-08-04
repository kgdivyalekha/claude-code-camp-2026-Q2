#!/bin/bash
# M6 Integration Verification Script
# Run this from week2_capable/log_viz to verify everything is in place

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 M6 World Map Integration Verification"
echo "=========================================="
echo ""

# Check 1: world_db.rb exists
echo -n "✓ Checking world_db.rb... "
if [ -f "lib/log_viz/world_db.rb" ]; then
    echo -e "${GREEN}found${NC}"
    lines=$(wc -l < "lib/log_viz/world_db.rb")
    echo "  └─ $lines lines"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 2: map.erb exists
echo -n "✓ Checking map.erb... "
if [ -f "views/map.erb" ]; then
    echo -e "${GREEN}found${NC}"
    lines=$(wc -l < "views/map.erb")
    echo "  └─ $lines lines"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 3: map_empty.erb exists
echo -n "✓ Checking map_empty.erb... "
if [ -f "views/map_empty.erb" ]; then
    echo -e "${GREEN}found${NC}"
    lines=$(wc -l < "views/map_empty.erb")
    echo "  └─ $lines lines"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 4: app.rb has world_db require
echo -n "✓ Checking app.rb require... "
if grep -q 'require_relative "world_db"' lib/log_viz/app.rb; then
    echo -e "${GREEN}found${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 5: app.rb has /map route
echo -n "✓ Checking /map route... "
if grep -q 'get "/sessions/:id/map"' lib/log_viz/app.rb; then
    echo -e "${GREEN}found${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 6: session.erb has map link
echo -n "✓ Checking session.erb link... "
if grep -q 'World Map' views/session.erb; then
    echo -e "${GREEN}found${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

# Check 7: Test endpoint in app.rb
echo -n "✓ Checking /test/m6 endpoint... "
if grep -q 'get "/test/m6"' lib/log_viz/app.rb; then
    echo -e "${GREEN}found${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ All checks passed!${NC}"
echo ""
echo "Next steps:"
echo "1. Start log_viz: bundle exec ruby bin/log_viz"
echo "2. Test M6 is loaded: http://localhost:4567/test/m6"
echo "3. View a session: http://localhost:4567/sessions/ID"
echo "4. Click [🗺️ World Map] button"
echo ""
echo "If you see 'world database not found', run an agent with M6"
echo "enabled to build the map."

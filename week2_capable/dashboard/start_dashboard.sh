#!/bin/bash
set -e

echo "🚀 Starting Boukensha Token Dashboard..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_VIZ_DIR="$PROJECT_ROOT/log_viz"

# Navigate to log_viz
cd "$LOG_VIZ_DIR"

echo "📦 Installing dependencies..."
bundle install --quiet

cd "$PROJECT_ROOT"

# Setup events.db and load all sessions
echo "📊 Setting up events database..."
cd "$LOG_VIZ_DIR"

# Use the setup script to initialize database and load all sessions
bundle exec ruby ../dashboard/setup_events_db.rb

# Start the server
echo "✅ Starting log_viz on http://localhost:9292"
echo ""
echo "Views:"
echo "  • Sessions list: http://localhost:9292/"
echo "  • Token dashboard: http://localhost:9292/sessions/baseline-fixture-001/tokens"
echo "  • Live session: http://localhost:9292/sessions/20260729T204852Z-46a0bf1f/tokens"
echo ""
echo "Press Ctrl+C to stop"
echo ""

bundle exec rackup

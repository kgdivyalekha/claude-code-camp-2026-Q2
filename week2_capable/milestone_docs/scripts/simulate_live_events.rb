#!/usr/bin/env ruby
# Simulate adding events to the database during a live session

require "sqlite3"
require "json"

db_path = ".boukensha/events.db"
unless File.exist?(db_path)
  puts "Database not found at #{db_path}"
  puts "Run: bash week2_capable/dashboard/start_dashboard.sh"
  exit 1
end

session_id = "live-simulation-001"

# Connect to the database
db = SQLite3::Database.new(db_path)
db.results_as_hash = true
db.execute("PRAGMA busy_timeout = 5000")

# Check if we need to create the events table
begin
  db.execute("SELECT 1 FROM events LIMIT 1")
rescue SQLite3::SQLException
  puts "Events table not found. Creating..."
  db.execute(<<~SQL)
    CREATE TABLE events (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id          TEXT NOT NULL,
      actor               TEXT,
      turn                INTEGER,
      iteration           INTEGER,
      at                  TEXT NOT NULL,
      phase               TEXT NOT NULL,
      tool                TEXT,
      ok                  INTEGER,
      input_tokens        INTEGER,
      output_tokens       INTEGER,
      cache_read_tokens   INTEGER,
      cache_write_tokens  INTEGER,
      tools_sent          INTEGER,
      cost_usd            REAL,
      model               TEXT,
      provider            TEXT,
      room                TEXT,
      details             TEXT NOT NULL
    )
  SQL
end

puts "Simulating live session events for: #{session_id}"
puts "Starting in 5 seconds... (Press Ctrl+C to stop)"
sleep 5

turn = 1
iteration = 1
cumulative_cost = 0.0

loop do
  # Simulate a response event
  input_tokens = 1000 + rand(1000)
  output_tokens = 100 + rand(200)
  model = ["claude-3-5-sonnet", "claude-haiku-4-5"].sample

  # Calculate cost based on model
  cost_usd = if model == "claude-haiku-4-5"
    (input_tokens * 0.8 / 1_000_000.0) + (output_tokens * 4.0 / 1_000_000.0)
  else
    (input_tokens * 3.0 / 1_000_000.0) + (output_tokens * 15.0 / 1_000_000.0)
  end

  cumulative_cost += cost_usd

  db.execute(
    "INSERT INTO events (session_id, phase, model, turn, iteration, input_tokens, output_tokens, cost_usd, at, details, provider, tools_sent) " \
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [session_id, "response", model, turn, iteration, input_tokens, output_tokens, cost_usd,
     Time.now.iso8601, '{}', "anthropic", 26]
  )

  puts "[Turn #{turn}, Iter #{iteration}] Added event: #{input_tokens} input, #{output_tokens} output, $#{cost_usd.round(4)} cost (total: $#{cumulative_cost.round(4)})"

  # Randomly increment turn
  if rand < 0.3
    turn += 1
    iteration = 1
  else
    iteration += 1
  end

  # Wait before next event
  sleep 3
end

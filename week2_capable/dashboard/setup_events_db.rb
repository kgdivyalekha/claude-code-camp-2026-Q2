#!/usr/bin/env ruby
# Quick setup: rebuild events.db from baseline fixture JSONL

$LOAD_PATH.unshift(File.expand_path("log_viz/lib", __dir__))

require "json"
require "sqlite3"

# Add Python's observability modules to load path
sys_path = ENV["PYTHONPATH"] || ""
ENV["PYTHONPATH"] = "#{File.expand_path("src", __dir__)}:#{sys_path}"

# For now, manually create events.db from fixture using SQL

fixture_path = File.expand_path("test/fixtures/sessions/baseline_fixture.jsonl", __dir__)
db_path = File.expand_path(".boukensha/events.db", __dir__)

puts "Setting up events.db from fixture..."
puts "Fixture: #{fixture_path}"
puts "Database: #{db_path}"

# Create .boukensha directory
db_dir = File.dirname(db_path)
Dir.mkdir(db_dir) unless Dir.exist?(db_dir)

# Remove old database
File.delete(db_path) if File.exist?(db_path)

# Create connection
db = SQLite3.open(db_path)
db.results_as_hash = true
db.execute("PRAGMA journal_mode = WAL")
db.execute("PRAGMA synchronous = NORMAL")
db.execute("PRAGMA mmap_size = #{256 * 1024 * 1024}")
db.execute("PRAGMA busy_timeout = 5000")
db.execute("PRAGMA foreign_keys = ON")

# Create schema
db.execute(<<~SQL)
  CREATE TABLE IF NOT EXISTS events (
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

db.execute("CREATE INDEX IF NOT EXISTS idx_events_session_phase ON events(session_id, phase)")
db.execute("CREATE INDEX IF NOT EXISTS idx_events_session_turn ON events(session_id, turn)")
db.execute("CREATE INDEX IF NOT EXISTS idx_events_actor ON events(session_id, actor)")

# Load fixture JSONL
File.foreach(fixture_path) do |line|
  next if line.strip.empty?
  event = JSON.parse(line)

  phase = event["phase"]
  session_id = event["session_id"]
  actor = event["actor"]
  turn = event["turn"]
  at = event["at"]

  iteration = event["iteration"]
  tool = event["name"] || event["tool"]
  ok = event["ok"]

  input_tokens = event["input_tokens"]
  output_tokens = event["output_tokens"]
  cache_read_tokens = event["cache_read_input_tokens"]
  cache_write_tokens = event["cache_creation_input_tokens"]
  cost_usd = event["cost_usd"]

  model = event["model"]
  provider = event["provider"]
  tools_sent = event["tools_sent"]
  room = event["room"]

  details = JSON.generate(event)

  db.execute(
    "INSERT INTO events (session_id, actor, turn, iteration, at, phase, tool, ok, " \
    "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, " \
    "tools_sent, cost_usd, model, provider, room, details) " \
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [session_id, actor, turn, iteration, at, phase, tool, ok,
     input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
     tools_sent, cost_usd, model, provider, room, details]
  )
end

db.close

puts "✓ events.db created at #{db_path}"
puts "✓ Token dashboard ready at http://localhost:9292/sessions/baseline-fixture-001/tokens"

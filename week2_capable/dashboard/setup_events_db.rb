#!/usr/bin/env ruby
# Setup: load events.db from fixture and all sessions in .boukensha/sessions

require "json"
require "sqlite3"
require "fileutils"

# Helper function to load events from a JSONL file
def load_events(db, file_path)
  return unless File.exist?(file_path)

  tools_sent_cache = {}

  File.foreach(file_path) do |line|
    next if line.strip.empty?
    event = JSON.parse(line)

    phase = event["phase"]
    session_id = event["session_id"]
    actor = event["actor"]
    turn = event["turn"] || event["n"]
    at = event["at"]
    iteration = event["iteration"]
    tool = event["name"] || event["tool"]
    ok = case event["ok"]
         when true then 1
         when false then 0
         else event["ok"]
         end
    input_tokens = event["input_tokens"]
    output_tokens = event["output_tokens"]
    cache_read_tokens = event["cache_read_input_tokens"]
    cache_write_tokens = event["cache_creation_input_tokens"]
    cost_usd = event["cost_usd"]
    model = event["model"]
    provider = event["provider"]
    room = event["room"]
    details = JSON.generate(event)

    # Track tool_count from prompt events and apply to response events
    cache_key = [session_id, turn, iteration]
    if phase == "prompt"
      tool_count = event["tool_count"]
      tools_sent_cache[cache_key] = tool_count if tool_count
    end

    tools_sent = event["tools_sent"]
    if tools_sent.nil? && phase == "response"
      tools_sent = tools_sent_cache[cache_key]
    end

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
rescue => e
  puts "Error loading #{file_path}: #{e.message}"
end

project_root = File.dirname(__dir__)  # Parent of dashboard directory
db_path = File.expand_path(".boukensha/events.db", project_root)
sessions_dir = File.expand_path(".boukensha/sessions", project_root)
fixture_path = File.expand_path("test/fixtures/sessions/baseline_fixture.jsonl", project_root)

puts "Setting up events database..."
puts "Database: #{db_path}"
puts "Sessions dir: #{sessions_dir}"

# Create .boukensha and sessions directory
db_dir = File.dirname(db_path)
FileUtils.mkdir_p(db_dir)
FileUtils.mkdir_p(sessions_dir)

# Create fresh database
File.delete(db_path) if File.exist?(db_path)

# Create connection
db = SQLite3::Database.new(db_path)
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

# Load fixture if it exists
if File.exist?(fixture_path)
  puts "  Loading fixture: #{File.basename(fixture_path)}"
  load_events(db, fixture_path)
end

# Load all JSONL files from sessions directory(ies)
session_files = Dir.glob(File.join(sessions_dir, "*.jsonl")).sort

# Also load from root project sessions if different
root_sessions_dir = File.expand_path("../.boukensha/sessions", project_root)
if root_sessions_dir != sessions_dir
  session_files.concat(Dir.glob(File.join(root_sessions_dir, "*.jsonl")).sort)
  session_files.uniq!
  session_files.sort!
end

if session_files.any?
  session_files.each do |file|
    puts "  Loading session: #{File.basename(file)}"
    load_events(db, file)
  end
else
  puts "  No sessions found in #{sessions_dir}"
end

db.close

puts "✓ events.db created at #{db_path}"
puts "✓ Token dashboard ready"

#!/usr/bin/env ruby
# Test script to verify cost calculation in the analytics

$LOAD_PATH.unshift(File.expand_path("log_viz/lib", __dir__))

require "json"
require "sqlite3"
require_relative "log_viz/lib/log_viz/analytics"

# Setup test database
test_db = ".boukensha/test_events.db"
File.delete(test_db) if File.exist?(test_db)

# Create connection
db = SQLite3::Database.new(test_db)
db.results_as_hash = true
db.execute("PRAGMA journal_mode = WAL")
db.execute("PRAGMA foreign_keys = ON")

# Create schema
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

# Insert test events with known costs
session_id = "test-session-001"
events_to_insert = [
  {
    session_id: session_id,
    phase: "response",
    model: "claude-3-5-sonnet",
    input_tokens: 2000,
    output_tokens: 100,
    cost_usd: 0.0063,
    at: Time.now.iso8601,
    details: "{}"
  },
  {
    session_id: session_id,
    phase: "response",
    model: "claude-3-5-sonnet",
    input_tokens: 2100,
    output_tokens: 150,
    cost_usd: 0.0072,
    at: Time.now.iso8601,
    details: "{}"
  },
  {
    session_id: session_id,
    phase: "response",
    model: "claude-haiku-4-5",
    input_tokens: 1000,
    output_tokens: 50,
    cost_usd: 0.001,
    at: Time.now.iso8601,
    details: "{}"
  }
]

events_to_insert.each do |event|
  db.execute(
    "INSERT INTO events (session_id, phase, model, input_tokens, output_tokens, cost_usd, at, details) " \
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    [event[:session_id], event[:phase], event[:model], event[:input_tokens], event[:output_tokens],
     event[:cost_usd], event[:at], event[:details]]
  )
end

db.close

# Now test the analytics
$LOAD_PATH.unshift(File.expand_path(".", __dir__))
analytics = LogViz::Analytics.new(test_db)

puts "Testing Analytics Cost Calculation"
puts "=" * 50

cost_summary = analytics.cost_summary(session_id)

puts "Session ID: #{session_id}"
puts "Total Cost: $#{cost_summary[:total_usd].round(4)}"
puts "Turns: #{cost_summary[:turns]}"
puts "Cost Per Turn: $#{cost_summary[:cost_per_turn_usd].round(4)}"
puts "Total Input Tokens: #{cost_summary[:input_tokens]}"
puts "Total Output Tokens: #{cost_summary[:output_tokens]}"
puts ""

# Verify the calculation
expected_cost = events_to_insert.sum { |e| e[:cost_usd] }
actual_cost = cost_summary[:total_usd]

puts "Expected total cost: $#{expected_cost.round(4)}"
puts "Actual total cost: $#{actual_cost.round(4)}"

if (actual_cost - expected_cost).abs < 0.0001
  puts "✓ Cost calculation is correct!"
else
  puts "✗ Cost calculation is INCORRECT!"
  puts "  Difference: $#{(actual_cost - expected_cost).round(4)}"
end

analytics.close

# Cleanup
File.delete(test_db)

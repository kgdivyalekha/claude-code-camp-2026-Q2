#!/usr/bin/env ruby
# Cleanup duplicate rooms in world.db

require 'sqlite3'

DB_PATH = File.expand_path('.boukensha/world.db', __dir__)

unless File.exist?(DB_PATH)
  puts "❌ Database not found: #{DB_PATH}"
  exit 1
end

puts "🔍 Scanning for duplicate rooms in #{DB_PATH}..."

conn = SQLite3::Database.new(DB_PATH)
conn.results_as_hash = true
conn.execute("PRAGMA busy_timeout = 10000")

# Find duplicates
duplicates = conn.execute(<<~SQL)
  SELECT name, GROUP_CONCAT(id, ',') as ids, COUNT(*) as count
  FROM rooms
  GROUP BY name
  HAVING COUNT(*) > 1
  ORDER BY count DESC
SQL

if duplicates.empty?
  puts "✓ No duplicates found!"
  conn.close
  exit 0
end

puts "\n📊 Found #{duplicates.length} duplicate room names:\n"
duplicates.each do |row|
  puts "  • #{row['name']} (#{row['count']} copies)"
end

total_merged = 0

puts "\n🔗 Merging duplicates...\n"

duplicates.each do |group|
  name = group['name']
  room_ids = group['ids'].split(',').map(&:strip)

  next if room_ids.length < 2

  primary_id = room_ids[0]
  secondary_ids = room_ids[1..-1]

  puts "  📍 #{name}"
  puts "     Primary: #{primary_id}"
  puts "     Secondary: #{secondary_ids.join(', ')}"

  # For each secondary room
  secondary_ids.each do |secondary_id|
    # Redirect all exits pointing to secondary to primary
    updated = conn.execute(
      "UPDATE exits SET target_room_id = ? WHERE target_room_id = ?",
      [primary_id, secondary_id]
    )

    # Delete the secondary room
    conn.execute("DELETE FROM rooms WHERE id = ?", [secondary_id])

    total_merged += 1
    puts "     ✓ Deleted #{secondary_id}"
  end

  puts ""
end

conn.close

puts "✅ Done! Merged #{total_merged} duplicate room entries."
puts "   Map will show clean duplicates on next refresh."

require "sqlite3"
require "sqlite3/database"

module LogViz
  class WorldDB
    def initialize(world_db_path)
      @db_path = world_db_path
    end

    def ready?
      File.file?(@db_path)
    end

    def close
      @db.close if @db
    end

    private

    def conn
      @db ||= begin
        db = SQLite3::Database.new(@db_path)
        db.results_as_hash = true
        db.execute("PRAGMA synchronous = FULL")
        db
      end
    end

    public

    # Add or update a room
    def save_room(room_data)
      return false unless conn

      id = room_data[:id]
      name = room_data[:name]
      signature = room_data[:signature]
      description = room_data[:description]
      summary = room_data[:summary]
      confidence = room_data[:confidence] || "probable"
      discovered_by = room_data[:discovered_by]
      first_seen = room_data[:first_seen] || Time.now.iso8601
      last_seen = room_data[:last_seen] || Time.now.iso8601

      conn.execute(<<~SQL, [id, name, signature, description, summary, confidence, 0, first_seen, last_seen, discovered_by])
        INSERT OR REPLACE INTO rooms (id, name, signature, description, summary, confidence, is_safe, first_seen, last_seen, discovered_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      SQL

      true
    rescue SQLite3::Exception => e
      warn "Failed to save room: #{e.message}"
      false
    end

    # Increment visit count for a room
    def visit_room(room_id)
      return false unless conn

      conn.execute(<<~SQL, [Time.now.iso8601, room_id])
        UPDATE rooms SET visit_count = visit_count + 1, last_seen = ? WHERE id = ?
      SQL

      true
    rescue SQLite3::Exception => e
      warn "Failed to update visit: #{e.message}"
      false
    end

    # Add an exit between rooms
    def save_exit(from_room_id, direction, to_room_id, confidence = "probable")
      return false unless conn

      conn.execute(<<~SQL, [from_room_id, direction, to_room_id, confidence])
        INSERT OR REPLACE INTO exits (room_id, direction, target_room_id, confidence)
        VALUES (?, ?, ?, ?)
      SQL

      true
    rescue SQLite3::Exception => e
      warn "Failed to save exit: #{e.message}"
      false
    end

    # Fetch all rooms with their connected exits
    def all_rooms
      return [] unless ready?

      sql = <<~SQL
        SELECT
          r.id, r.name, r.signature, r.description, r.summary,
          r.confidence, r.visit_count, r.first_seen, r.last_seen,
          r.discovered_by, GROUP_CONCAT(e.direction || ':' || COALESCE(e.target_room_id, '')) as exits_raw
        FROM rooms r
        LEFT JOIN exits e ON r.id = e.room_id
        WHERE e.blocked_reason IS NULL
        GROUP BY r.id
        ORDER BY r.last_seen DESC
      SQL

      conn.execute(sql).map do |row|
        {
          id: row["id"],
          name: strip_ansi(row["name"]),
          signature: row["signature"],
          description: strip_ansi(row["description"]),
          summary: strip_ansi(row["summary"]),
          confidence: row["confidence"],
          visit_count: row["visit_count"],
          first_seen: row["first_seen"],
          last_seen: row["last_seen"],
          discovered_by: row["discovered_by"],
          exits: parse_exits(row["exits_raw"])
        }
      end
    rescue SQLite3::Exception => e
      warn "WorldDB query failed: #{e.message}"
      []
    end

    # Get all exits for a room
    def exits_for(room_id)
      return {} unless ready?

      sql = <<~SQL
        SELECT direction, target_room_id, confidence, blocked_reason
        FROM exits
        WHERE room_id = ?
      SQL

      conn.execute(sql, [room_id]).each_with_object({}) do |row, acc|
        acc[row["direction"]] = {
          target: row["target_room_id"],
          confidence: row["confidence"],
          blocked: row["blocked_reason"]
        }
      end
    rescue SQLite3::Exception
      {}
    end

    # Count total rooms discovered
    def room_count
      return 0 unless ready?

      conn.execute("SELECT COUNT(*) as cnt FROM rooms").first["cnt"]
    rescue SQLite3::Exception
      0
    end

    # Get a specific room
    def get_room(room_id)
      return nil unless ready?

      sql = <<~SQL
        SELECT
          id, name, signature, description, summary,
          confidence, visit_count, first_seen, last_seen, discovered_by
        FROM rooms
        WHERE id = ?
      SQL

      row = conn.execute(sql, [room_id]).first
      return nil unless row

      {
        id: row["id"],
        name: strip_ansi(row["name"]),
        signature: row["signature"],
        description: strip_ansi(row["description"]),
        summary: strip_ansi(row["summary"]),
        confidence: row["confidence"],
        visit_count: row["visit_count"],
        first_seen: row["first_seen"],
        last_seen: row["last_seen"],
        discovered_by: row["discovered_by"],
        exits: exits_for(room_id)
      }
    rescue SQLite3::Exception
      nil
    end

    # BFS layout: compute positions for rendering
    def layout_rooms
      rooms = all_rooms
      return {} if rooms.empty?

      # Start with first room (by first_seen, or just first in list)
      start_room = rooms.min_by { |r| r[:first_seen] || "" }
      start_id = start_room[:id]

      # BFS to compute distances and directions
      positions = {}
      queue = [[start_id, 0, 0]]  # [room_id, x, y]
      visited = Set.new([start_id])
      room_map = {}
      rooms.each { |r| room_map[r[:id]] = r }

      # Direction vectors for layout (simple compass layout)
      directions = {
        "north" => [0, -1],
        "n" => [0, -1],
        "south" => [0, 1],
        "s" => [0, 1],
        "east" => [1, 0],
        "e" => [1, 0],
        "west" => [-1, 0],
        "w" => [-1, 0],
        "northeast" => [1, -1],
        "ne" => [1, -1],
        "northwest" => [-1, -1],
        "nw" => [-1, -1],
        "southeast" => [1, 1],
        "se" => [1, 1],
        "southwest" => [-1, 1],
        "sw" => [-1, 1],
        "up" => [0, -2],
        "u" => [0, -2],
        "down" => [0, 2],
        "d" => [0, 2]
      }

      while queue.any?
        room_id, x, y = queue.shift
        positions[room_id] = { x: x, y: y }

        room = get_room(room_id)
        next unless room

        room[:exits].each do |direction, exit_info|
          # exit_info is {target: id, confidence: ..., blocked: ...}
          target_id = exit_info.is_a?(Hash) ? exit_info[:target] : exit_info
          next if target_id.nil? || visited.include?(target_id)

          dx, dy = directions[direction.downcase] || [0, 0]
          new_x = x + dx
          new_y = y + dy

          visited.add(target_id)
          queue.push([target_id, new_x, new_y])
        end
      end

      # Add unvisited rooms in empty grid spaces
      unvisited = rooms.select { |r| !visited.include?(r[:id]) }
      if unvisited.any?
        max_x = positions.any? ? positions.values.map { |p| p[:x] }.max : 0
        max_y = positions.any? ? positions.values.map { |p| p[:y] }.max : 0

        unvisited.each_with_index do |room, idx|
          # Place in a grid below/right of existing rooms
          col = idx % 3
          row = idx / 3
          new_x = max_x + 2 + col
          new_y = max_y + 2 + row
          positions[room[:id]] = { x: new_x, y: new_y }
        end
      end

      # Normalize coordinates to positive space
      if positions.any?
        min_x = positions.values.map { |p| p[:x] }.min
        min_y = positions.values.map { |p| p[:y] }.min

        positions.each do |room_id, pos|
          pos[:x] -= min_x
          pos[:y] -= min_y
        end
      end

      positions
    end

    private

    def parse_exits(exits_raw)
      return {} unless exits_raw && exits_raw.to_s.strip != ""

      exits_raw.split(",").each_with_object({}) do |pair, acc|
        parts = pair.split(":")
        next unless parts.length == 2
        direction = parts[0].to_s.strip
        target_id = parts[1].to_s.strip
        acc[direction] = target_id if direction.length > 0
      end
    end

    private

    def strip_ansi(text)
      # Remove ANSI escape codes like \x1b[0;33m
      text.to_s.gsub(/\x1b\[[0-9;]*m|\[[0-9;]*m/, "").strip
    end
  end
end

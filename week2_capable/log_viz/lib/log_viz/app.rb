require "sinatra/base"
require "time"
require "sqlite3"
require "sqlite3/database"
require "json"
require "set"

require_relative "session"
require_relative "ansi"
require_relative "analytics"
require_relative "metrics"  # M9 token metrics dashboard
require_relative "audit_db"  # M5 integration
require_relative "world_db"  # M6 integration

module LogViz
  class App < Sinatra::Base
    set :root, File.expand_path("../..", __dir__)
    set :sessions_dir, ENV.fetch("LOG_VIZ_SESSIONS_DIR") {
      File.expand_path("../../../../.boukensha/sessions", __dir__)
    }

    helpers do
      def session_paths
        Dir.glob(File.join(settings.sessions_dir, "*.jsonl")).sort.reverse
      end

      def format_time(iso)
        return "?" unless iso

        Time.parse(iso).strftime("%Y-%m-%d %H:%M:%S %z")
      rescue ArgumentError
        iso
      end

      def truncate(text, length = 100)
        flat = text.to_s.gsub(/\s+/, " ").strip
        flat.length > length ? "#{flat[0, length]}…" : flat
      end

      def format_args(args)
        return "" if args.nil? || args.empty?

        args.map { |k, v| "#{k}: #{v.inspect}" }.join(", ")
      end

      def ansi_html(text)
        Ansi.to_html(text)
      end

      def text_html(text)
        Ansi.escape_html(text)
      end

      def fmt_tokens(n)
        n = n.to_i
        n >= 1000 ? format("%.1fk", n / 1000.0) : n.to_s
      end

      def pct(used, max)
        max.to_i.positive? ? [(used.to_f / max.to_i * 100).round, 100].min : 0
      end

      # Uncapped percentage for labels — shows >100% when a budget is exceeded
      # (bar widths still use the clamped `pct`).
      def pct_raw(used, max)
        max.to_i.positive? ? (used.to_f / max.to_i * 100).round : 0
      end

      # A small inline progress bar. `danger` paints it red (limit tripped).
      def progress_bar(used, max, label:, danger: false)
        width = pct(used, max)
        klass = danger ? "bar-fill danger" : "bar-fill"
        <<~HTML
          <div class="budget">
            <div class="budget-label">#{label}</div>
            <div class="bar"><div class="#{klass}" style="width: #{width}%"></div></div>
          </div>
        HTML
      end

      def fmt_cost(n)
        n.nil? ? "&mdash;" : format("$%.4f", n)
      end

      def fmt_cost_cell(cost, known: true)
        return "&mdash;" if cost.nil? || !known

        fmt_cost(cost)
      end

      # In-transcript chip (§2.3): live context size as a mini-bar scaled to the
      # context window, plus the turn spend accumulating toward its cap.
      def ctx_chip(usage, running, context_window:, max_turn_tokens:, model: nil, provider: nil, cost_usd: nil)
        return "" unless usage

        input = usage["input_tokens"].to_i
        out   = usage["output_tokens"].to_i
        cache = usage["cache_read_input_tokens"].to_i

        parts = []
        # Turn spend first and bar-backed — it's what trips max_tokens, so it's
        # the signal worth watching fill as you scroll.
        if max_turn_tokens.to_i.positive?
          danger = running.to_i > max_turn_tokens.to_i ? " danger" : ""
          parts << %(<span class="ctx-turn#{danger}">turn #{fmt_tokens(running)}/#{fmt_tokens(max_turn_tokens)}</span>)
          parts << %(<span class="ctx-bar"><span class="ctx-bar-fill#{danger}" style="width: #{pct(running, max_turn_tokens)}%"></span></span>)
        end
        # Live context size second, with a smaller mini-bar.
        parts << %(<span class="ctx-amt">ctx #{fmt_tokens(input)}</span>)
        if context_window.to_i.positive?
          parts << %(<span class="ctx-mini"><span class="ctx-mini-fill" style="width: #{pct(input, context_window)}%"></span></span>)
        end
        parts << %(<span class="ctx-out">+#{fmt_tokens(out)} out</span>)
        parts << %(<span class="ctx-cache">cached #{fmt_tokens(cache)}</span>) if cache.positive?
        parts << %(<span class="ctx-cost">#{fmt_cost(cost_usd)}</span>) unless cost_usd.nil?
        parts << %(<span class="ctx-model">#{[provider, model].compact.join(" / ")}</span>) if provider || model

        %(<span class="ctx-chip">#{parts.join("\n")}</span>)
      end

      # Inline SVG sparkline of per-iteration input_tokens across the session.
      # `points` is the Session#usage_series; faint vertical lines mark turn
      # boundaries, a notch marks compactions. No JS, no chart library.
      def sparkline(points, max:, width: 640, height: 48)
        return "" if points.length < 2

        max = 1 if max.to_i < 1
        step = width.to_f / (points.length - 1)

        coords = points.each_with_index.map do |p, i|
          x = (i * step).round(1)
          y = (height - (p.input.to_f / max * (height - 4)) - 2).round(1)
          "#{x},#{y}"
        end.join(" ")

        # Faint vertical rule at each turn's first iteration (after turn 1).
        boundaries = points.each_with_index.select { |p, i| i.positive? && p.iteration == 1 }
        rules = boundaries.map do |_p, i|
          x = (i * step).round(1)
          %(<line class="spark-turn" x1="#{x}" y1="0" x2="#{x}" y2="#{height}"/>)
        end.join

        <<~SVG
          <svg class="spark" viewBox="0 0 #{width} #{height}" preserveAspectRatio="none" role="img" aria-label="input tokens per iteration">
            #{rules}
            <polyline class="spark-line" points="#{coords}"/>
          </svg>
        SVG
      end
    end

    get "/" do
      @sessions = session_paths.map { |path| Session.load(path) }
      erb :index
    end

    # Sample data route for M6 testing — works with any session ID
    get "/sessions/:id/populate-sample-world" do
      session_id = File.basename(params[:id])
      world_db_path = File.expand_path("../.boukensha/world.db", settings.root)

      # Delete old empty database
      File.delete(world_db_path) if File.exist?(world_db_path) && File.size(world_db_path) == 0

      world = WorldDB.new(world_db_path)
      ensure_world_db_schema(world)

      # Verify schema was created
      db_size_after_schema = File.size(world_db_path) if File.exist?(world_db_path)

      # Create sample rooms
      rooms = [
        { id: "tavern", name: "The Tavern", signature: "A cozy tavern", description: "A warm tavern with a roaring fireplace", summary: "Tavern", confidence: "confirmed", discovered_by: "look" },
        { id: "forest", name: "Dark Forest", signature: "A dark forest path", description: "A winding path through dense trees", summary: "Forest path", confidence: "probable", discovered_by: "explore" },
        { id: "cave", name: "Entrance Cave", signature: "A cave entrance", description: "The entrance to a mysterious cave", summary: "Cave", confidence: "probable", discovered_by: "search" },
        { id: "village", name: "Small Village", signature: "A quaint village", description: "A peaceful village square", summary: "Village", confidence: "confirmed", discovered_by: "wander" },
        { id: "bridge", name: "Stone Bridge", signature: "An ancient bridge", description: "An old stone bridge over a river", summary: "Bridge", confidence: "confirmed", discovered_by: "traverse" }
      ]

      save_results = rooms.map { |r| world.save_room(r) }

      # Create exits
      world.save_exit("tavern", "north", "village", "confirmed")
      world.save_exit("tavern", "east", "forest", "probable")
      world.save_exit("tavern", "south", "bridge", "probable")
      world.save_exit("forest", "west", "tavern", "probable")
      world.save_exit("forest", "north", "cave", "probable")
      world.save_exit("cave", "south", "forest", "probable")
      world.save_exit("village", "south", "tavern", "confirmed")
      world.save_exit("bridge", "north", "tavern", "probable")

      # Simulate visits
      5.times { world.visit_room("tavern") }
      3.times { world.visit_room("forest") }
      2.times { world.visit_room("cave") }
      4.times { world.visit_room("village") }
      1.times { world.visit_room("bridge") }

      # Populate navigation_log so current room can be determined
      world.log_movement(
        session_id: session_id,
        actor: "test",
        turn: 1,
        from_room_id: "tavern",
        direction: "look",
        to_room_id: "tavern",
        success: 1
      )

      world.close

      db_size_final = File.size(world_db_path) if File.exist?(world_db_path)

      content_type :json
      {
        status: "populated",
        db_path: world_db_path,
        db_size_after_schema: db_size_after_schema,
        db_size_final: db_size_final,
        rooms_saved: save_results,
        redirect_to: "/sessions/#{session_id}/map"
      }.to_json
    end

    get "/sessions/:id" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      erb :session
    end

    # API endpoint for live updates
    get "/api/sessions/:id/cost" do
      id = File.basename(params[:id])
      db_path = File.expand_path("../.boukensha/events.db", settings.root)
      analytics = Analytics.new(db_path)

      halt 404, { error: "Session not found" }.to_json unless analytics.ready?

      cost_summary = analytics.cost_summary(id)

      # Fall back to session file if database has no data yet
      if cost_summary[:turns].to_i.zero?
        path = File.join(settings.sessions_dir, "#{id}.jsonl")
        if File.file?(path)
          session = Session.load(path)
          cost_summary = {
            total_usd: session.estimated_cost || 0.0,
            turns: session.turn_count_real,
            cost_per_turn_usd: session.estimated_cost && session.turn_count_real > 0 ? session.estimated_cost / session.turn_count_real : 0.0,
            input_tokens: session.total_input_tokens,
            output_tokens: session.total_output_tokens
          }
          $stderr.puts "Loaded session from file: #{id} -> cost: #{cost_summary[:total_usd]}"
        else
          $stderr.puts "Session file not found: #{path}"
        end
      end

      analytics.close

      content_type :json
      cost_summary.to_json
    end

    # Debug endpoint: show raw database data for a session
    get "/api/sessions/:id/debug" do
      id = File.basename(params[:id])
      db_path = File.expand_path("../.boukensha/events.db", settings.root)

      halt 404, { error: "Database not found" }.to_json unless File.exist?(db_path)

      conn = SQLite3::Database.new(db_path)
      conn.results_as_hash = true

      # Get sample events
      events = conn.execute(
        "SELECT id, phase, model, cost_usd, input_tokens, output_tokens FROM events WHERE session_id = ? LIMIT 10",
        [id]
      )

      # Get summary
      summary = conn.execute(
        "SELECT COUNT(*) as count, SUM(cost_usd) as total_cost FROM events WHERE session_id = ? AND phase = 'response'",
        [id]
      ).first

      conn.close

      content_type :json
      {
        session_id: id,
        sample_events: events,
        summary: summary
      }.to_json
    end

    # Test route to verify Sinatra routing works
    get "/sessions/:id/tokens_test" do
      "Token Dashboard Ready - Session: #{params[:id]}"
    end

    get "/sessions/:id/tokens" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      db_path = File.expand_path("../.boukensha/events.db", settings.root)
      @analytics = Analytics.new(db_path)

      unless @analytics.ready?
        @ready = false
        return erb :tokens_empty
      end

      @ready = true
      @token_breakdown = @analytics.token_breakdown(id)

      # Use database data if complete, otherwise use session file (source of truth)
      db_cost = @analytics.cost_summary(id)
      session_input = @session.total_input_tokens
      session_output = @session.total_output_tokens

      # Use DB data only if token counts match closely (within 10%)
      # If DB tokens are much lower, the database is incomplete and we should use session file
      db_has_complete_data = db_cost[:turns].to_i > 0 &&
        (db_cost[:input_tokens].to_i > 0 && session_input > 0 &&
         (db_cost[:input_tokens].to_f / session_input) > 0.9)

      if db_has_complete_data
        @cost_summary = db_cost
      else
        # Use session file as source of truth for cost calculation
        @cost_summary = {
          total_usd: @session.estimated_cost || 0.0,
          turns: @session.turn_count_real,
          cost_per_turn_usd: @session.estimated_cost && @session.turn_count_real > 0 ? @session.estimated_cost / @session.turn_count_real : 0.0,
          input_tokens: session_input,
          output_tokens: session_output
        }
      end

      @schema_overhead = @analytics.schema_overhead(id)
      @cache_effectiveness = @analytics.cache_effectiveness(id)
      @tokens_per_turn = @analytics.tokens_per_turn(id)
      @iterations_per_turn = @analytics.iterations_per_turn(id)
      @context_pressure = @analytics.context_pressure(id)
      @tool_usage = @analytics.tool_usage(id)
      @compression_metrics = @analytics.compression_metrics(id, settings.sessions_dir)

      erb :tokens
    end

    # M9 Comprehensive Metrics Dashboard — token economy, caching, M9 compression impact
    get "/sessions/:id/metrics" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      db_path = File.expand_path("../.boukensha/events.db", settings.root)
      @metrics = Metrics.new(db_path)

      unless @metrics.ready?
        @ready = false
        return erb :metrics_empty
      end

      @ready = true
      @dashboard = @metrics.dashboard_summary(id)
      @session_id = id

      erb :metrics
    end

    # Sessions analytics dashboard — shows all sessions with token breakdown
    get "/analytics" do
      db_path = File.expand_path("../.boukensha/events.db", settings.root)
      @analytics = Analytics.new(db_path)

      unless @analytics.ready?
        @ready = false
        return erb :analytics_empty
      end

      @ready = true

      # Get all unique session IDs from database
      conn = SQLite3::Database.new(db_path)
      conn.results_as_hash = true
      conn.execute("PRAGMA busy_timeout = 5000")

      sessions_data = conn.execute("""
        SELECT DISTINCT session_id FROM events ORDER BY session_id DESC
      """)

      @sessions = sessions_data.map do |row|
        session_id = row["session_id"]
        {
          id: session_id,
          breakdown: @analytics.token_breakdown(session_id),
          cost: @analytics.cost_summary(session_id),
          schema: @analytics.schema_overhead(session_id),
          cache: @analytics.cache_effectiveness(session_id),
          turns_data: @analytics.tokens_per_turn(session_id),
        }
      end

      conn.close
      erb :analytics
    end

    # M5 Permissions Dashboard — show permission decisions and audit trail
    get "/sessions/:id/permissions" do
      id = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      @audit = AuditDB.new

      unless @audit.available?
        @audit_available = false
        return erb :permissions_empty
      end

      @audit_available = true
      @summary = @audit.session_summary(id)
      @entries = @audit.entries(id, 50)
      @denied_calls = @audit.denied_calls(id)
      @tool_usage = @audit.tool_usage(id)
      @rate_violations = @audit.rate_limit_violations(id)

      erb :permissions
    end

    # M5 Actors Dashboard — show who played and their roles
    get "/sessions/:id/actors" do
      id = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      @audit = AuditDB.new

      unless @audit.available?
        @audit_available = false
        return erb :actors_empty
      end

      @audit_available = true
      @actors = @audit.actors_in_session(id)
      @decisions_by_actor = @audit.decisions_by_actor(id)

      @actor_details = @actors.map do |actor_id|
        {
          id: actor_id,
          entries: @audit.actor_entries(id, actor_id, 20),
          decisions: @audit.decisions_by_actor(id).select { |d| d["actor"] == actor_id }
        }
      end

      erb :actors
    end

    # M6 World Map Dashboard — show discovered rooms and connections
    get "/sessions/:id/map" do
      begin
        id = File.basename(params[:id])
        path = File.join(settings.sessions_dir, "#{id}.jsonl")
        halt 404, "Session not found: #{id}" unless File.file?(path)

        @session = Session.load(path)

        # Load world.db (auto-create if missing)
        world_db_path = File.expand_path("../.boukensha/world.db", settings.root)
        @world = WorldDB.new(world_db_path)

        # Ensure world.db schema exists (creates if needed)
        ensure_world_db_schema(@world)

        @world_available = @world.ready?
        @rooms = @world.all_rooms
        @room_count = @world.room_count
        @positions = @world.layout_rooms if @rooms.any?

        # Get the current room from navigation_log (most recent entry)
        @current_room_id = get_current_room_id(id) if @world_available

        # Debug: log exits and connections
        total_exits = @rooms.sum { |r| r[:exits] ? r[:exits].length : 0 }
        confirmed_connections = @rooms.sum do |r|
          (r[:exits] || {}).select { |_dir, target| target.to_s.strip != "" }.length
        end

        $stderr.puts "DEBUG MAP: room_count=#{@room_count}, rooms.length=#{@rooms.length}, positions.length=#{@positions.length}, current_room=#{@current_room_id}"
        $stderr.puts "DEBUG MAP: total_exits=#{total_exits}, confirmed_connections=#{confirmed_connections}"

        # Log exits data for debugging
        if @rooms.any?
          @rooms.first(3).each do |room|
            exits_str = room[:exits].map { |d, t| "#{d}->#{t.to_s.strip.empty? ? 'NULL' : t}" }.join(", ")
            $stderr.puts "DEBUG MAP ROOM: #{room[:name]} (#{room[:id]}): exits=[#{exits_str}]"
          end
        end

        erb :map_live
      rescue => e
        halt 500, "Error loading world map: #{e.message}\n#{e.backtrace.join("\n")}"
      end
    end

    # Get the current room ID from navigation_log (most recent successful move or look)
    def get_current_room_id(session_id)
      db_path = File.expand_path("../.boukensha/world.db", settings.root)
      return nil unless File.exist?(db_path)

      conn = SQLite3::Database.new(db_path)
      conn.results_as_hash = true

      # Get the most recent to_room from navigation_log for this session
      result = conn.execute(
        "SELECT to_room FROM navigation_log WHERE session_id = ? AND to_room IS NOT NULL ORDER BY id DESC LIMIT 1",
        [session_id]
      ).first

      conn.close

      result ? result["to_room"] : nil
    rescue => e
      $stderr.puts "Error getting current room: #{e.message}"
      nil
    end

    # Ensure world.db schema exists (helper for map route)
    def ensure_world_db_schema(world)
      return if world.ready?

      # Create schema if DB doesn't exist
      db_path = File.expand_path("../.boukensha/world.db", settings.root)
      conn = SQLite3::Database.new(db_path)

      sql = <<~SQL
        CREATE TABLE IF NOT EXISTS rooms (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          signature TEXT NOT NULL,
          description TEXT,
          summary TEXT,
          zone_guess TEXT,
          confidence TEXT NOT NULL DEFAULT 'probable',
          is_safe INTEGER,
          first_seen TEXT,
          last_seen TEXT,
          visit_count INTEGER DEFAULT 0,
          discovered_by TEXT,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS exits (
          room_id TEXT NOT NULL REFERENCES rooms(id),
          direction TEXT NOT NULL,
          target_room_id TEXT REFERENCES rooms(id),
          confidence TEXT NOT NULL DEFAULT 'probable',
          is_one_way INTEGER DEFAULT 0,
          blocked_reason TEXT,
          last_seen TEXT,
          PRIMARY KEY (room_id, direction)
        );

        CREATE TABLE IF NOT EXISTS items (
          id TEXT PRIMARY KEY,
          room_id TEXT REFERENCES rooms(id),
          name TEXT,
          item_type TEXT,
          properties TEXT,
          last_seen TEXT
        );

        CREATE TABLE IF NOT EXISTS npcs (
          id TEXT PRIMARY KEY,
          room_id TEXT REFERENCES rooms(id),
          name TEXT,
          level_guess INTEGER,
          is_hostile INTEGER,
          dialogue TEXT,
          last_seen TEXT
        );

        CREATE TABLE IF NOT EXISTS navigation_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT,
          actor TEXT,
          turn INTEGER,
          from_room TEXT REFERENCES rooms(id),
          direction TEXT,
          to_room TEXT REFERENCES rooms(id),
          success INTEGER,
          reason TEXT,
          at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_rooms_signature ON rooms(signature);
        CREATE INDEX IF NOT EXISTS idx_rooms_name ON rooms(name);
        CREATE INDEX IF NOT EXISTS idx_exits_target ON exits(target_room_id);
        CREATE INDEX IF NOT EXISTS idx_items_room ON items(room_id);
        CREATE INDEX IF NOT EXISTS idx_npcs_room ON npcs(room_id);
        CREATE INDEX IF NOT EXISTS idx_nav_log_session ON navigation_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_nav_log_from_room ON navigation_log(from_room);
      SQL

      sql.split(';').each do |statement|
        conn.execute(statement) if statement.strip.length > 0
      end

      conn.close
    end

    # Clean ANSI codes from all room names using pure SQL
    get "/sessions/:id/map/clean-ansi" do
      content_type :json

      begin
        world_db_path = File.expand_path("../.boukensha/world.db", settings.root)

        unless File.exist?(world_db_path)
          return { error: "Database not found", cleaned: 0, success: false }.to_json
        end

        conn = SQLite3::Database.new(world_db_path)
        conn.execute("PRAGMA busy_timeout = 5000")

        # List of common ANSI codes to remove
        # Just do direct string replacements
        ansi_codes = [
          "[0;33m", "[0;31m", "[0;32m", "[0;34m", "[0;35m", "[0;36m", "[0;37m",
          "[1;33m", "[1;31m", "[1;32m", "[1;34m", "[1;35m", "[1;36m", "[1;37m",
          "[33m", "[31m", "[32m", "[34m", "[35m", "[36m", "[37m", "[0m"
        ]

        ansi_codes.each do |code|
          conn.execute("UPDATE rooms SET name = REPLACE(name, ?, '') WHERE name LIKE ?", [code, "%#{code}%"])
          conn.execute("UPDATE rooms SET description = REPLACE(description, ?, '') WHERE description LIKE ?", [code, "%#{code}%"])
          conn.execute("UPDATE rooms SET summary = REPLACE(summary, ?, '') WHERE summary LIKE ?", [code, "%#{code}%"])
        end

        # Also remove ESC character if present (CHAR(27))
        esc_code = "\x1b"
        conn.execute("UPDATE rooms SET name = REPLACE(name, ?, '') WHERE name LIKE ?", [esc_code, "%#{esc_code}%"])
        conn.execute("UPDATE rooms SET description = REPLACE(description, ?, '') WHERE description LIKE ?", [esc_code, "%#{esc_code}%"])
        conn.execute("UPDATE rooms SET summary = REPLACE(summary, ?, '') WHERE summary LIKE ?", [esc_code, "%#{esc_code}%"])

        # Trim whitespace
        conn.execute("UPDATE rooms SET name = TRIM(name), description = TRIM(description), summary = TRIM(summary)")

        conn.close

        $stderr.puts "[MAP] ANSI cleanup completed"

        return { cleaned: 1, message: "Cleaned room names", success: true }.to_json

      rescue => e
        $stderr.puts "[MAP ERROR] #{e.class}: #{e.message}"
        return { error: e.message, cleaned: 0, success: false }.to_json
      end
    end

    # Reset world.db for a session (clear old data)
    get "/sessions/:id/map/reset" do
      id = File.basename(params[:id])
      world_db_path = File.expand_path("../.boukensha/world.db", settings.root)

      if File.exist?(world_db_path)
        File.delete(world_db_path)
        $stderr.puts "Deleted world.db: #{world_db_path}"
      end

      # Recreate empty schema
      world = WorldDB.new(world_db_path)
      conn = SQLite3::Database.new(world_db_path)
      conn.execute("PRAGMA synchronous = FULL")
      # Let it auto-create on next use
      conn.close

      redirect "/sessions/#{id}/map"
    end

    # Detect duplicate rooms (same name, likely same location)
    get "/sessions/:id/map/duplicates" do
      id = File.basename(params[:id])
      world_db_path = File.expand_path("../.boukensha/world.db", settings.root)

      halt 404, "Database not found" unless File.exist?(world_db_path)

      conn = SQLite3::Database.new(world_db_path)
      conn.results_as_hash = true

      # Find rooms with same name
      duplicates = conn.execute(<<~SQL)
        SELECT name, COUNT(*) as count, GROUP_CONCAT(id, ',') as ids
        FROM rooms
        GROUP BY name
        HAVING COUNT(*) > 1
        ORDER BY count DESC
      SQL

      conn.close

      content_type :json
      {
        session_id: id,
        duplicate_count: duplicates.length,
        duplicates: duplicates
      }.to_json
    end

    # Merge duplicate rooms (consolidate same-named rooms)
    post "/sessions/:id/map/merge-duplicates" do
      begin
        id = File.basename(params[:id])
        world_db_path = File.expand_path("../.boukensha/world.db", settings.root)

        unless File.exist?(world_db_path)
          content_type :json
          return { error: "Database not found", merged: 0 }.to_json
        end

        conn = SQLite3::Database.new(world_db_path)
        conn.results_as_hash = true
        conn.execute("PRAGMA busy_timeout = 5000")

        merged_count = 0

        # Find all duplicate groups
        duplicates = conn.execute(<<~SQL)
          SELECT name, GROUP_CONCAT(id, ',') as ids
          FROM rooms
          GROUP BY name
          HAVING COUNT(*) > 1
        SQL

        duplicates.each do |group|
          ids_str = group["ids"].to_s
          next if ids_str.empty?

          room_ids = ids_str.split(',').map(&:strip)
          if room_ids.length > 1
            # Keep first ID, merge all others into it
            primary_id = room_ids[0]
            room_ids[1..-1].each do |secondary_id|
              # Redirect all exits pointing to secondary to primary
              conn.execute(
                "UPDATE exits SET target_room_id = ? WHERE target_room_id = ?",
                [primary_id, secondary_id]
              )
              # Delete the secondary room
              conn.execute("DELETE FROM rooms WHERE id = ?", [secondary_id])
              merged_count += 1
            end
          end
        end

        conn.close

        $stderr.puts "[MAP] Merged #{merged_count} duplicate room entries"

        content_type :json
        { merged: merged_count, message: "Merged #{merged_count} duplicate rooms", success: true }.to_json

      rescue => e
        $stderr.puts "[MAP ERROR] Merge failed: #{e.class} - #{e.message}"
        $stderr.puts e.backtrace.first(5).join("\n")

        content_type :json
        {
          error: e.message,
          merged: 0,
          success: false
        }.to_json
      end
    end

    # Test route to verify M6 integration is loaded
    get "/test/m6" do
      content_type :json
      world_db_path = File.expand_path("../.boukensha/world.db", settings.root)
      world = WorldDB.new(world_db_path)

      begin
        db_size = File.exist?(world_db_path) ? File.size(world_db_path) : 0
        {
          status: "ok",
          world_db_class: WorldDB.class.name,
          world_db_path: world_db_path,
          world_db_exists: File.exist?(world_db_path),
          world_db_size: db_size,
          world_ready: world.ready?,
          room_count: world.room_count,
          rooms: world.all_rooms,
          error: nil
        }.to_json
      rescue => e
        {
          status: "error",
          error: e.message,
          backtrace: e.backtrace.first(5)
        }.to_json
      end
    end

    # M5 Audit API endpoint — live audit trail updates
    get "/api/sessions/:id/audit" do
      id = File.basename(params[:id])
      limit = (params[:limit] || 20).to_i
      actor_filter = params[:actor]

      @audit = AuditDB.new

      halt 404, { error: "Audit database not found" }.to_json unless @audit.available?

      entries = if actor_filter
                  @audit.actor_entries(id, actor_filter, limit)
                else
                  @audit.entries(id, limit)
                end

      content_type :json
      {
        session_id: id,
        entries: entries,
        summary: @audit.session_summary(id),
      }.to_json
    end

    # Clean ANSI escape codes from room names
    get "/sessions/:id/map/clean-ansi" do
      content_type :json
      id = File.basename(params[:id])

      begin
        world_db_path = File.expand_path("../.boukensha/world.db", settings.root)
        halt 404, { error: "Database not found", cleaned: 0, success: false }.to_json unless File.exist?(world_db_path)

        conn = SQLite3::Database.new(world_db_path)
        conn.execute("PRAGMA busy_timeout = 10000")

        # Remove ESC character (CHAR(27)) first
        esc_char = "\x1b"
        conn.execute("UPDATE rooms SET name = REPLACE(name, ?, '')", [esc_char])
        conn.execute("UPDATE rooms SET description = REPLACE(description, ?, '')", [esc_char])
        conn.execute("UPDATE rooms SET summary = REPLACE(summary, ?, '')", [esc_char])

        # Remove all ANSI bracket codes
        codes = [
          "[0;33m", "[0;31m", "[0;32m", "[0;34m", "[0;35m", "[0;36m", "[0;37m",
          "[1;33m", "[1;31m", "[1;32m", "[1;34m", "[1;35m", "[1;36m", "[1;37m",
          "[33m", "[31m", "[32m", "[34m", "[35m", "[36m", "[37m", "[0m"
        ]

        codes.each do |code|
          conn.execute("UPDATE rooms SET name = REPLACE(name, ?, '')", [code])
          conn.execute("UPDATE rooms SET description = REPLACE(description, ?, '')", [code])
          conn.execute("UPDATE rooms SET summary = REPLACE(summary, ?, '')", [code])
        end

        # Trim whitespace
        conn.execute("UPDATE rooms SET name = TRIM(name)")
        conn.execute("UPDATE rooms SET description = TRIM(description)")
        conn.execute("UPDATE rooms SET summary = TRIM(summary)")

        conn.close

        { cleaned: 1, message: "Cleaned ANSI codes from room names", success: true }.to_json

      rescue => e
        $stderr.puts "[CLEAN-ANSI ERROR] #{e.class}: #{e.message}"
        { error: e.message, cleaned: 0, success: false }.to_json
      end
    end
  end
end

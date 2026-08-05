require "sqlite3"
require "json"

module LogViz
  # Query events.db for token analytics and observability data.
  # M1 foundation: token breakdown, cost, cache effectiveness, etc.
  class Analytics
    # Graceful degradation: if events.db doesn't exist or is empty,
    # return empty results rather than crashing.

    def initialize(db_path = ".boukensha/events.db")
      @db_path = db_path
      @db = nil
    end

    def ready?
      File.exist?(@db_path)
    end

    def db
      return nil unless ready?

      @db ||= begin
        conn = SQLite3.open(@db_path)
        conn.results_as_hash = true
        conn.execute("PRAGMA busy_timeout = 5000")
        conn
      end
    end

    def close
      @db&.close
      @db = nil
    end

    # Token breakdown: schema vs history vs results vs output
    def token_breakdown(session_id)
      return {} unless db

      row = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read_tokens,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as cache_write_tokens
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      input_tokens = row["input_tokens"].to_i
      output_tokens = row["output_tokens"].to_i
      cache_read = row["cache_read_tokens"].to_i
      cache_write = row["cache_write_tokens"].to_i

      # Rough estimate of breakdown (not perfect but directional)
      response_count = db.execute(
        "SELECT COUNT(*) as count FROM events WHERE session_id = ? AND phase = 'response'",
        [session_id]
      ).first["count"].to_i

      schema_tokens = (response_count * 2200).to_i  # ~2200 per response
      total_input = input_tokens
      remaining = total_input - schema_tokens
      history_tokens = (remaining / 2).to_i
      result_tokens = remaining - history_tokens

      {
        schema_tokens:,
        history_tokens:,
        result_tokens:,
        output_tokens:,
        cache_read_tokens: cache_read,
        cache_write_tokens: cache_write,
        total_input_tokens: total_input,
        total_output_tokens: output_tokens,
      }
    end

    # Per-turn token breakdown
    def tokens_per_turn(session_id)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            turn,
            COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COUNT(DISTINCT iteration) as iterations,
            COALESCE(SUM(cost_usd), 0) as cost_usd
          FROM events
          WHERE session_id = ? AND phase = 'response'
          GROUP BY turn
          ORDER BY turn
        SQL
        [session_id]
      )
    end

    # Total cost and per-turn average
    def cost_summary(session_id)
      return {} unless db

      row = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(cost_usd), 0) as total_cost,
            COUNT(DISTINCT turn) as turn_count,
            COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0)), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      total_cost = row["total_cost"].to_f
      turn_count = row["turn_count"].to_i
      input_tokens = row["input_tokens"].to_i
      output_tokens = row["output_tokens"].to_i

      # Estimate if cost_usd not provided
      if total_cost.zero?
        input_cost = (input_tokens / 1_000_000.0) * 3.0
        output_cost = (output_tokens / 1_000_000.0) * 15.0
        total_cost = input_cost + output_cost
      end

      {
        total_usd: total_cost,
        turns: turn_count,
        cost_per_turn_usd: turn_count.positive? ? total_cost / turn_count : 0,
        input_tokens:,
        output_tokens:,
      }
    end

    # Schema overhead: tools_sent and estimated token cost
    def schema_overhead(session_id)
      return {} unless db

      row = db.execute(
        <<~SQL,
          SELECT
            COUNT(*) as response_count,
            COALESCE(AVG(tools_sent), 0) as avg_tools_sent,
            COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as total_input
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      response_count = row["response_count"].to_i
      avg_tools_sent = row["avg_tools_sent"].to_f
      total_input = row["total_input"].to_i

      schema_tokens = (response_count * avg_tools_sent * 85).to_i
      percent = total_input.positive? ? (schema_tokens.to_f / total_input * 100).round(1) : 0

      {
        tools_sent: avg_tools_sent.round(1),
        schema_tokens:,
        percent_of_input: percent,
      }
    end

    # Cache effectiveness
    def cache_effectiveness(session_id)
      return {} unless db

      row = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as cache_write,
            COALESCE(SUM(input_tokens), 0) as uncached_input
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      cache_read = row["cache_read"].to_i
      cache_write = row["cache_write"].to_i
      uncached_input = row["uncached_input"].to_i
      total_input = cache_read + cache_write + uncached_input

      hit_rate = total_input.positive? ? (cache_read.to_f / total_input * 100).round(1) : 0

      {
        cache_read_tokens: cache_read,
        cache_write_tokens: cache_write,
        hit_rate:,
      }
    end

    # Tool usage statistics
    def tool_usage(session_id)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            tool,
            COUNT(*) as call_count,
            SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) as error_count
          FROM events
          WHERE session_id = ? AND phase = 'tool_result'
          GROUP BY tool
          ORDER BY call_count DESC
          LIMIT 15
        SQL
        [session_id]
      )
    end

    # Iteration counts (cost scales ~N×context)
    def iterations_per_turn(session_id)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            turn,
            COUNT(DISTINCT iteration) as iterations,
            COALESCE(SUM(input_tokens), 0) as input_tokens
          FROM events
          WHERE session_id = ? AND phase = 'response'
          GROUP BY turn
          ORDER BY turn
        SQL
        [session_id]
      )
    end

    # Context pressure: input tokens vs window
    def context_pressure(session_id, context_window = 200_000)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            turn,
            COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as input_tokens
          FROM events
          WHERE session_id = ? AND phase = 'response'
          GROUP BY turn
          ORDER BY turn
        SQL
        [session_id]
      ).map do |row|
        input = row["input_tokens"].to_i
        row.merge("percent_of_window" => (input.to_f / context_window * 100).round(1))
      end
    end

    # M7 Compression metrics: repeat-visit room compression, banner stripping
    # Reads tokens.compressed events from the JSONL session file
    # Returns empty hash if no data available (graceful degradation)
    def compression_metrics(session_id, sessions_dir = ".boukensha/sessions")
      session_file = File.join(sessions_dir, "#{session_id}.jsonl")

      # Return empty hash if session file doesn't exist
      unless File.exist?(session_file)
        return {
          compressions: [],
          total_compressions: 0,
          total_tokens_saved: 0,
          total_before_tokens: 0,
          total_after_tokens: 0,
          average_compression_ratio: 0,
          average_savings_per_compression: 0,
        }
      end

      compressions = []
      total_saved = 0
      total_before = 0
      total_after = 0

      begin
        File.foreach(session_file) do |line|
          event = JSON.parse(line)
          next unless event["phase"] == "tokens.compressed"

          before = event["before_tokens"].to_i
          after = event["after_tokens"].to_i
          saved = event["saved"].to_i

          compressions << {
            tool: event["tool"],
            before_tokens: before,
            after_tokens: after,
            saved_tokens: saved,
            room_id: event["room_id"],
            visit_count: event["visit_count"],
            compression_ratio: before > 0 ? ((saved.to_f / before) * 100).round(1) : 0,
          }

          total_saved += saved
          total_before += before
          total_after += after
        end
      rescue StandardError => e
        # Log error but don't crash; return partial results
        warn("Error reading compression metrics: #{e.message}")
      end

      {
        compressions: compressions,
        total_compressions: compressions.length,
        total_tokens_saved: total_saved,
        total_before_tokens: total_before,
        total_after_tokens: total_after,
        average_compression_ratio: total_before > 0 ? ((total_saved.to_f / total_before) * 100).round(1) : 0,
        average_savings_per_compression: compressions.length > 0 ? (total_saved / compressions.length).round : 0,
      }
    end

    # All sessions with basic metrics
    def all_sessions(sessions_dir = ".boukensha/sessions")
      return [] unless db

      sessions = []
      Dir.glob(File.join(sessions_dir, "*.jsonl")).sort.reverse.each do |path|
        session_id = File.basename(path, ".jsonl")
        cost = cost_summary(session_id)
        next unless cost[:turns].positive?

        sessions << {
          id: session_id,
          turns: cost[:turns],
          total_cost_usd: cost[:total_usd],
          input_tokens: cost[:input_tokens],
        }
      end
      sessions
    end
  end
end

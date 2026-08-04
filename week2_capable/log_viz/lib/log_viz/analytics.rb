require "sqlite3"
require "sqlite3/database"
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
        conn = SQLite3::Database.new(@db_path)
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
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            model
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      total_cost = row["total_cost"].to_f
      turn_count = row["turn_count"].to_i
      input_tokens = row["input_tokens"].to_i
      output_tokens = row["output_tokens"].to_i
      model = row["model"].to_s

      # cost_usd is only populated on the final response event, causing
      # underestimation when there are multiple iterations. Always estimate
      # from all tokens to get the true cost of all API calls.
      rates = model_pricing_rates(model)
      input_cost = (input_tokens / 1_000_000.0) * rates[:input]
      output_cost = (output_tokens / 1_000_000.0) * rates[:output]
      actual_total = input_cost + output_cost

      {
        total_usd: actual_total,
        turns: turn_count,
        cost_per_turn_usd: turn_count.positive? ? actual_total / turn_count : 0,
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

    private

    def model_pricing_rates(model)
      # Current Claude pricing per 1M tokens (matches session.rb)
      case model&.downcase
      when /claude-fable-5/
        { input: 10.0, output: 50.0 }
      when /claude-opus-5/
        { input: 15.0, output: 75.0 }
      when /claude-opus-4-8/
        { input: 5.0, output: 25.0 }
      when /claude-opus-4-7/
        { input: 5.0, output: 25.0 }
      when /claude-opus-4-6/
        { input: 5.0, output: 25.0 }
      when /claude-sonnet-4-6/
        { input: 3.0, output: 15.0 }
      when /claude-sonnet-5/
        { input: 3.0, output: 15.0 }
      when /claude-haiku-4-5/
        { input: 1.0, output: 5.0 }
      when /claude-3-5-sonnet/
        { input: 3.0, output: 15.0 }
      when /claude-3-5-haiku/
        { input: 0.8, output: 4.0 }
      when /claude-3-opus/
        { input: 15.0, output: 75.0 }
      when /claude-3-sonnet/
        { input: 3.0, output: 15.0 }
      when /claude-3-haiku/
        { input: 0.8, output: 4.0 }
      when /claude-opus-4/
        { input: 5.0, output: 25.0 }
      else
        # Default fallback (Haiku 4.5)
        { input: 1.0, output: 5.0 }
      end
    end
  end
end

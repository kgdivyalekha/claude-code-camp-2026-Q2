require "sqlite3"
require "sqlite3/database"
require "json"

module LogViz
  # Comprehensive metrics dashboard for token economy, caching, and M9 impact.
  # Extends Analytics with detailed breakdowns for visualization.
  class Metrics
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

    # === SCHEMA OVERHEAD ===

    # Tool schema tokens: sum of tools_sent * cost per tool
    def schema_overhead(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(CASE WHEN tools_sent > 0 THEN tools_sent ELSE 0 END), 0) as total_tool_schemas,
            COALESCE(AVG(CASE WHEN tools_sent > 0 THEN tools_sent ELSE NULL END), 0) as avg_tools_per_call,
            COUNT(DISTINCT CASE WHEN tools_sent > 0 THEN 1 END) as calls_with_tools,
            COALESCE(SUM(CASE WHEN phase = 'tokens.gated' THEN 1 ELSE 0 END), 0) as gating_events,
            COALESCE(COUNT(DISTINCT CASE WHEN tools_sent IS NOT NULL THEN iteration END), 0) as total_iterations
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      total_schemas = result["total_tool_schemas"].to_i
      avg_tools = result["avg_tools_per_call"].to_f.round(1)
      calls_with_tools = result["calls_with_tools"].to_i
      gating_events = result["gating_events"].to_i
      total_iterations = result["total_iterations"].to_i

      # Estimate schema tokens: ~85 tokens per tool (median from week 1)
      schema_tokens_est = total_schemas * 85
      avg_cost_per_iteration = calls_with_tools > 0 ? schema_tokens_est.to_f / calls_with_tools : 0

      {
        total_tool_schemas:,
        avg_tools_per_call: avg_tools,
        calls_with_tools:,
        gating_events:,
        schema_tokens_estimated: schema_tokens_est,
        avg_schema_cost_per_iteration: avg_cost_per_iteration.round(0),
      }
    end

    # === CACHING EFFECTIVENESS ===

    def cache_effectiveness(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(CASE WHEN cache_read_tokens > 0 THEN 1 ELSE 0 END), 0) as cache_hits,
            COALESCE(SUM(CASE WHEN cache_write_tokens > 0 THEN 1 ELSE 0 END), 0) as cache_writes,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as total_cache_read_tokens,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as total_cache_write_tokens,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COUNT(*) as total_calls
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      cache_hits = result["cache_hits"].to_i
      cache_writes = result["cache_writes"].to_i
      cache_read_tokens = result["total_cache_read_tokens"].to_i
      cache_write_tokens = result["total_cache_write_tokens"].to_i
      total_input = result["total_input_tokens"].to_i
      total_calls = result["total_calls"].to_i

      # Cache effectiveness metrics
      hit_rate = total_calls > 0 ? (cache_hits.to_f / total_calls * 100).round(1) : 0
      cache_savings = cache_read_tokens > 0 ? (cache_read_tokens.to_f / total_input * 100).round(1) : 0

      # Cost: cached tokens are 90% cheaper
      cache_read_cost_savings = cache_read_tokens > 0 ? (cache_read_tokens * 0.9 / 1_000_000.0 * 0.80).round(4) : 0  # Assume $0.80 per 1M uncached

      {
        cache_hit_rate_pct: hit_rate,
        cache_hits:,
        cache_writes:,
        cache_read_tokens:,
        cache_write_tokens:,
        cache_cost_savings_usd: cache_read_cost_savings,
        total_calls:,
      }
    end

    # === M9 TOKEN REDUCTION ===

    def m9_compression_impact(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(CASE WHEN phase = 'tokens.compressed' THEN 1 ELSE 0 END), 0) as compression_events,
            COALESCE(SUM(CASE WHEN phase = 'tokens.compressed' THEN CAST(json_extract(details, '$.saved') AS INTEGER) ELSE 0 END), 0) as total_tokens_saved,
            COALESCE(SUM(CASE WHEN phase = 'tokens.compressed' THEN CAST(json_extract(details, '$.before_tokens') AS INTEGER) ELSE 0 END), 0) as before_compression,
            COALESCE(SUM(CASE WHEN phase = 'tokens.compressed' THEN CAST(json_extract(details, '$.after_tokens') AS INTEGER) ELSE 0 END), 0) as after_compression,
            COALESCE(SUM(CASE WHEN phase = 'tokens.compressed' THEN CAST(json_extract(details, '$.visit_count') AS INTEGER) ELSE 0 END), 0) as total_repeat_visits
          FROM events
          WHERE session_id = ? AND phase = 'tokens.compressed'
        SQL
        [session_id]
      ).first || {}

      compression_events = result["compression_events"].to_i
      tokens_saved = result["total_tokens_saved"].to_i
      before = result["before_compression"].to_i
      after = result["after_compression"].to_i
      repeat_visits = result["total_repeat_visits"].to_i

      # Calculate compression ratio
      compression_ratio = before > 0 ? ((before - after).to_f / before * 100).round(1) : 0

      # Estimate frontier queries impact (included in compression budget)
      frontier_queries = db.execute(
        "SELECT COUNT(*) as count FROM events WHERE session_id = ? AND phase = 'frontier_query_failed'",
        [session_id]
      ).first["count"].to_i

      {
        compression_events:,
        tokens_saved:,
        before_compression: before,
        after_compression: after,
        compression_ratio_pct: compression_ratio,
        total_repeat_visits:,
        frontier_queries_failed: frontier_queries,
        avg_savings_per_repeat: compression_events > 0 ? (tokens_saved.to_f / compression_events).round(0) : 0,
      }
    end

    # === TOKEN BREAKDOWN BY TYPE ===

    def token_breakdown_detailed(session_id)
      return {} unless db

      row = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read_tokens,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as cache_write_tokens,
            COUNT(*) as response_count
          FROM events
          WHERE session_id = ? AND phase = 'response'
        SQL
        [session_id]
      ).first || {}

      input = row["input_tokens"].to_i
      output = row["output_tokens"].to_i
      cache_read = row["cache_read_tokens"].to_i
      cache_write = row["cache_write_tokens"].to_i
      response_count = row["response_count"].to_i

      # Estimate breakdown
      schema_tokens = response_count > 0 ? (response_count * 2200).to_i : 0
      history_tokens = ((input - schema_tokens) / 2).to_i
      result_tokens = (input - schema_tokens) - history_tokens

      {
        schema_tokens:,
        history_tokens:,
        result_tokens:,
        uncached_input_tokens: input,
        output_tokens:,
        cache_read_tokens:,
        cache_write_tokens:,
        total_input_tokens: input + cache_read,
        total_tokens: input + output + cache_read + cache_write,
      }
    end

    # === CONTEXTCOMPACTION DATA ===

    def compaction_analysis(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            COALESCE(SUM(CASE WHEN phase = 'compaction' THEN 1 ELSE 0 END), 0) as compaction_events,
            COALESCE(SUM(CASE WHEN phase = 'compaction' THEN CAST(json_extract(details, '$.dropped') AS INTEGER) ELSE 0 END), 0) as total_dropped,
            COALESCE(AVG(CASE WHEN phase = 'compaction' THEN CAST(json_extract(details, '$.dropped') AS INTEGER) ELSE NULL END), 0) as avg_dropped
          FROM events
          WHERE session_id = ?
        SQL
        [session_id]
      ).first || {}

      compaction_events = result["compaction_events"].to_i
      total_dropped = result["total_dropped"].to_i
      avg_dropped = result["avg_dropped"].to_f.round(1)

      {
        compaction_events:,
        total_messages_dropped: total_dropped,
        avg_messages_per_compaction: avg_dropped,
      }
    end

    # === TOOL USAGE METRICS ===

    def tool_usage(session_id)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            tool,
            COUNT(*) as usage_count,
            COALESCE(SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END), 0) as successful,
            COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) as failed
          FROM events
          WHERE session_id = ? AND phase = 'tool_result'
          GROUP BY tool
          ORDER BY usage_count DESC
        SQL
        [session_id]
      ).map do |row|
        success_rate = row["usage_count"] > 0 ? (row["successful"].to_f / row["usage_count"] * 100).round(0) : 0
        {
          tool: row["tool"],
          count: row["usage_count"],
          successful: row["successful"],
          failed: row["failed"],
          success_rate_pct: success_rate,
        }
      end
    end

    # === ITERATION & COST TRENDS ===

    def iterations_per_turn(session_id)
      return [] unless db

      db.execute(
        <<~SQL,
          SELECT
            turn,
            COUNT(DISTINCT iteration) as iterations,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read_tokens
          FROM events
          WHERE session_id = ? AND phase = 'response'
          GROUP BY turn
          ORDER BY turn
        SQL
        [session_id]
      )
    end

    # === PERMISSION & AUDIT ===

    def permission_decisions(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            verdict,
            COUNT(*) as count,
            COUNT(DISTINCT rule) as unique_rules
          FROM audit_log
          WHERE session_id = ?
          GROUP BY verdict
        SQL
        [session_id]
      )

      decisions = {}
      result.each do |row|
        decisions[row["verdict"]] = {
          count: row["count"],
          unique_rules: row["unique_rules"],
        }
      end

      decisions
    end

    # === EXPLORATION PROGRESS ===

    def exploration_progress(session_id)
      return {} unless db

      result = db.execute(
        <<~SQL,
          SELECT
            COALESCE(COUNT(DISTINCT id), 0) as rooms_discovered,
            COALESCE(COUNT(DISTINCT CASE WHEN confidence = 'confirmed' THEN id END), 0) as rooms_confirmed,
            COALESCE(COUNT(DISTINCT CASE WHEN confidence = 'probable' THEN id END), 0) as rooms_probable,
            COALESCE(COUNT(DISTINCT CASE WHEN confidence = 'ambiguous' THEN id END), 0) as rooms_ambiguous
          FROM rooms
        SQL
      ).first || {}

      total = result["rooms_discovered"].to_i
      confirmed = result["rooms_confirmed"].to_i
      probable = result["rooms_probable"].to_i
      ambiguous = result["rooms_ambiguous"].to_i

      {
        total_rooms: total,
        confirmed: confirmed,
        probable:,
        ambiguous:,
        confirmed_pct: total > 0 ? (confirmed.to_f / total * 100).round(1) : 0,
      }
    end

    # === SUMMARY DASHBOARD ===

    def dashboard_summary(session_id)
      {
        token_breakdown: token_breakdown_detailed(session_id),
        schema_overhead: schema_overhead(session_id),
        cache_effectiveness: cache_effectiveness(session_id),
        m9_compression: m9_compression_impact(session_id),
        compaction: compaction_analysis(session_id),
        tool_usage: tool_usage(session_id),
        iterations: iterations_per_turn(session_id),
        permissions: permission_decisions(session_id),
        exploration: exploration_progress(session_id),
      }
    end
  end
end

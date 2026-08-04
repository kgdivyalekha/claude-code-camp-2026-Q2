require "sqlite3"
require "sqlite3/database"
require "json"

module LogViz
  # Read audit_log table from .boukensha/events.db
  # M5 integration: display permissions, audit trail, actors
  class AuditDB
    def initialize(db_path = ".boukensha/events.db")
      @db_path = db_path
      @db = nil
    end

    def db
      @db ||= SQLite3::Database.new(@db_path, readonly: true)
      @db.results_as_hash = true
      @db
    end

    def available?
      File.exist?(@db_path)
    end

    # Summary stats for a session
    def session_summary(session_id)
      return {} unless available?

      {
        total_decisions: total_decisions(session_id),
        allow_count: count_by_verdict(session_id, "allow"),
        deny_count: count_by_verdict(session_id, "deny"),
        ask_count: count_by_verdict(session_id, "ask"),
        rules_applied: rules_applied(session_id),
        actors: actors_in_session(session_id),
      }
    end

    def total_decisions(session_id)
      db.execute(
        "SELECT COUNT(*) as count FROM audit_log WHERE session_id = ?",
        [session_id]
      ).first["count"]
    rescue
      0
    end

    def count_by_verdict(session_id, verdict)
      db.execute(
        "SELECT COUNT(*) as count FROM audit_log WHERE session_id = ? AND verdict = ?",
        [session_id, verdict]
      ).first["count"]
    rescue
      0
    end

    # Which permission rules were used
    def rules_applied(session_id)
      db.execute(
        "SELECT rule, COUNT(*) as count FROM audit_log WHERE session_id = ? GROUP BY rule ORDER BY count DESC",
        [session_id]
      )
    rescue
      []
    end

    # Actors in this session
    def actors_in_session(session_id)
      db.execute(
        "SELECT DISTINCT actor FROM audit_log WHERE session_id = ? ORDER BY actor",
        [session_id]
      ).map { |row| row["actor"] }
    rescue
      []
    end

    # Audit log entries for a session
    def entries(session_id, limit = 50)
      db.execute(
        """
        SELECT id, at, actor, action, verdict, rule, reason, args
        FROM audit_log
        WHERE session_id = ?
        ORDER BY at DESC
        LIMIT ?
        """,
        [session_id, limit]
      )
    rescue
      []
    end

    # Entries for a specific actor
    def actor_entries(session_id, actor_id, limit = 50)
      db.execute(
        """
        SELECT id, at, actor, action, verdict, rule, reason
        FROM audit_log
        WHERE session_id = ? AND actor = ?
        ORDER BY at DESC
        LIMIT ?
        """,
        [session_id, actor_id, limit]
      )
    rescue
      []
    end

    # Denied calls (where verdict = 'deny')
    def denied_calls(session_id)
      db.execute(
        """
        SELECT at, actor, action, rule, reason
        FROM audit_log
        WHERE session_id = ? AND verdict = 'deny'
        ORDER BY at DESC
        """,
        [session_id]
      )
    rescue
      []
    end

    # Tools that were denied
    def denied_tools(session_id)
      db.execute(
        """
        SELECT DISTINCT action FROM audit_log
        WHERE session_id = ? AND verdict = 'deny'
        ORDER BY action
        """,
        [session_id]
      ).map { |row| row["action"] }
    rescue
      []
    end

    # Tool usage statistics
    def tool_usage(session_id)
      db.execute(
        """
        SELECT action, verdict, COUNT(*) as count
        FROM audit_log
        WHERE session_id = ?
        GROUP BY action, verdict
        ORDER BY action
        """,
        [session_id]
      )
    rescue
      []
    end

    # Rate limit violations
    def rate_limit_violations(session_id)
      db.execute(
        """
        SELECT actor, action, COUNT(*) as violations
        FROM audit_log
        WHERE session_id = ? AND rule = 'rate_limit'
        GROUP BY actor, action
        ORDER BY violations DESC
        """,
        [session_id]
      )
    rescue
      []
    end

    # Permission decisions by actor
    def decisions_by_actor(session_id)
      db.execute(
        """
        SELECT actor, verdict, COUNT(*) as count
        FROM audit_log
        WHERE session_id = ?
        GROUP BY actor, verdict
        ORDER BY actor
        """,
        [session_id]
      )
    rescue
      []
    end

    # Parse args JSON safely
    def parse_args(args_json)
      return {} if args_json.nil? || args_json.empty?

      JSON.parse(args_json)
    rescue JSON::ParserError
      {}
    end
  end
end

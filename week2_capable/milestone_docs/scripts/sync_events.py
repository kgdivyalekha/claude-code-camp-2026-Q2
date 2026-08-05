#!/usr/bin/env python3
"""Background sync service - Watches for new session files and loads events automatically."""

import os
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict
from event_store import EventStore


class EventSync:
    def __init__(self, sessions_dir: str = ".boukensha/sessions", db_path: str = ".boukensha/events.db"):
        self.sessions_dir = Path(sessions_dir)
        self.db_path = db_path
        self.store = EventStore(db_path)
        self.processed_events = {}

        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_session_event_count(self, session_id: str) -> int:
        """Get number of events for a session in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", [session_id])
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"Error getting event count: {e}")
            return 0

    def sync_session_file(self, session_file: Path) -> int:
        """Sync a single session file - load new events that aren't in DB yet."""
        session_id = session_file.stem
        new_events = 0

        try:
            with open(session_file) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        event_key = f"{session_id}:{line_num}"

                        if event_key in self.processed_events:
                            continue

                        if self.store.log_event(event):
                            self.processed_events[event_key] = True
                            new_events += 1

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"Error syncing {session_file}: {e}")

        return new_events

    def sync_all(self) -> Dict[str, int]:
        """Sync all session files - load any new events."""
        results = {}

        if not self.sessions_dir.exists():
            return results

        session_files = sorted(self.sessions_dir.glob("*.jsonl"))

        for session_file in session_files:
            new_count = self.sync_session_file(session_file)
            if new_count > 0:
                session_id = session_file.stem
                results[session_id] = new_count
                print(f"[{datetime.now().isoformat()}] {session_id}: +{new_count} events")

        return results

    def run_once(self):
        """Run sync once and report results."""
        print(f"[{datetime.now().isoformat()}] Syncing events...")
        results = self.sync_all()

        if results:
            print(f"[{datetime.now().isoformat()}] Synced {sum(results.values())} events")
            for session_id, count in results.items():
                stats = self.store.get_session_stats(session_id)
                print(f"  {session_id}: turns={stats.get('turns', 0)}, cost=${stats.get('total_cost', 0):.4f}")
        else:
            print(f"[{datetime.now().isoformat()}] No new events")

    def watch(self, interval: int = 2):
        """Watch for new events and sync periodically."""
        print(f"Watching {self.sessions_dir} for new events (every {interval}s)...")
        print("Press Ctrl+C to stop")

        try:
            while True:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nSync stopped")


if __name__ == "__main__":
    import sys

    watch_mode = "--watch" in sys.argv
    interval = 2

    for arg in sys.argv[1:]:
        if arg.startswith("--interval="):
            try:
                interval = int(arg.split("=")[1])
            except (ValueError, IndexError):
                pass

    sync = EventSync()

    if watch_mode:
        sync.watch(interval)
    else:
        sync.run_once()

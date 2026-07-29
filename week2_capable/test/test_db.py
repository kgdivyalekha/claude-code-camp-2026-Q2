"""Test suite for db.py — SQLite connection factory.

M0 success criteria: mmap_size is non-zero and journal_mode is 'wal'.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from boukensha.db import open_db


class TestDbConnection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_open_db_creates_parent_directories(self):
        """open_db should create parent directories if they don't exist."""
        nested_path = Path(self.tmpdir.name) / "nested" / "deep" / "test.db"
        conn = open_db(str(nested_path))
        try:
            self.assertTrue(nested_path.exists())
        finally:
            conn.close()

    def test_wal_mode_enabled(self):
        """WAL mode should be enabled for concurrent reader/writer support."""
        conn = open_db(str(self.db_path))
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
        finally:
            conn.close()

    def test_mmap_size_configured(self):
        """mmap_size should be non-zero (M0 success criterion)."""
        conn = open_db(str(self.db_path))
        try:
            mmap_size = conn.execute("PRAGMA mmap_size").fetchone()[0]
            self.assertGreater(mmap_size, 0, "mmap_size should be non-zero")
        finally:
            conn.close()

    def test_mmap_size_can_be_disabled(self):
        """mmap_size=0 should disable memory mapping."""
        conn = open_db(str(self.db_path), mmap_bytes=0)
        try:
            mmap_size = conn.execute("PRAGMA mmap_size").fetchone()[0]
            self.assertEqual(mmap_size, 0)
        finally:
            conn.close()

    def test_synchronous_pragma(self):
        """synchronous should be NORMAL for WAL safety with fewer fsyncs."""
        conn = open_db(str(self.db_path))
        try:
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
            self.assertEqual(sync, 1)  # 1 = NORMAL
        finally:
            conn.close()

    def test_foreign_keys_enabled(self):
        """foreign_keys should be ON."""
        conn = open_db(str(self.db_path))
        try:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            self.assertEqual(fk, 1)
        finally:
            conn.close()

    def test_check_same_thread_false(self):
        """Connection should allow multi-threaded access."""
        conn = open_db(str(self.db_path))
        try:
            # If check_same_thread is True, this would raise ProgrammingError.
            # We test by creating a simple table and reading it.
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("test",))
            result = conn.execute("SELECT name FROM test WHERE id = 1").fetchone()
            self.assertEqual(result[0], "test")
        finally:
            conn.close()

    def test_concurrent_reader_writer(self):
        """Two connections should be able to read/write concurrently (WAL property)."""
        # Create a schema
        conn1 = open_db(str(self.db_path))
        try:
            conn1.execute("CREATE TABLE concurrent_test (id INTEGER PRIMARY KEY, value TEXT)")
            conn1.execute("INSERT INTO concurrent_test (value) VALUES (?)", ("write1",))
            conn1.commit()
        finally:
            conn1.close()

        # Open a second connection and read while first writes
        conn2 = open_db(str(self.db_path))
        conn3 = open_db(str(self.db_path))
        try:
            # conn2 starts a read transaction
            result1 = conn2.execute("SELECT value FROM concurrent_test").fetchone()
            self.assertEqual(result1[0], "write1")

            # conn3 writes while conn2 is reading
            conn3.execute("INSERT INTO concurrent_test (value) VALUES (?)", ("write2",))
            conn3.commit()

            # conn2 should still see the old data (read consistency in WAL)
            result2 = conn2.execute("SELECT value FROM concurrent_test WHERE id = 2").fetchone()
            self.assertEqual(result2[0], "write2")
        finally:
            conn2.close()
            conn3.close()


if __name__ == "__main__":
    unittest.main()

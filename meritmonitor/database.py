import os
import sqlite3

from meritmonitor.logger import get_logger

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

        if not os.path.exists(self.db_path):
            self._initialize_database()

        self.conn = sqlite3.connect(self.db_path)

    def _initialize_database(self):
        """Create the database and tables if the file doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE discord (
            timestamp INTEGER NOT NULL PRIMARY KEY,
            message_id TEXT NOT NULL,
            message_hash TEXT NOT NULL
        );
        """)

        conn.commit()
        conn.close()

    def close(self):
        if self.conn:
            self.conn.close()

    def upsert_discord_message(self, timestamp: int, message_id: str, message_hash: str):
        logger = get_logger()
        logger.info(f"entered upsert_discord_message: {timestamp}, {message_id}, {message_hash}")
        self.conn.execute(
            "INSERT OR REPLACE INTO discord (timestamp, message_id, message_hash) VALUES (?, ?, ?)",
            (timestamp, message_id, message_hash)
        )
        self.conn.commit()

    def lookup_discord_message(self, timestamp: int):
        query = """
            SELECT message_id, message_hash
            FROM discord
            WHERE timestamp = ?
            LIMIT 1
        """

        cursor = self.conn.cursor()
        cursor.execute(query, (timestamp,))
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
        else:
            return None, None

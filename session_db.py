"""Session storage module using SQLite for persisting user interactions.

Supports:
- User star ratings (1.0 to 5.0)
- User favorites / bookmarks
- Session clearing and history
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "user_sessions.db"


class SessionStore:
    """SQLite-backed session repository for user interactions."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create interaction tables if not present."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_ratings (
                    session_id TEXT NOT NULL,
                    movie_id INTEGER NOT NULL,
                    rating REAL NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (session_id, movie_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    session_id TEXT NOT NULL,
                    movie_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (session_id, movie_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ratings_session ON user_ratings(session_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_session ON user_favorites(session_id);
            """)
            conn.commit()

    def set_rating(self, session_id: str, movie_id: int, rating: float) -> None:
        """Add or update a rating for a session."""
        rating_clamped = max(0.5, min(5.0, round(rating * 2) / 2))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_ratings (session_id, movie_id, rating, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id, movie_id) DO UPDATE SET
                    rating = excluded.rating,
                    updated_at = CURRENT_TIMESTAMP
            """, (session_id, movie_id, rating_clamped))
            conn.commit()

    def get_ratings(self, session_id: str) -> Dict[int, float]:
        """Get all ratings for a session as {movieId: rating}."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT movie_id, rating FROM user_ratings WHERE session_id = ?
                ORDER BY updated_at DESC
            """, (session_id,))
            rows = cursor.fetchall()
            return {int(row["movie_id"]): float(row["rating"]) for row in rows}

    def remove_rating(self, session_id: str, movie_id: int) -> None:
        """Remove a rating from session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_ratings WHERE session_id = ? AND movie_id = ?
            """, (session_id, movie_id))
            conn.commit()

    def clear_session(self, session_id: str) -> None:
        """Clear all ratings and favorites for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_ratings WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM user_favorites WHERE session_id = ?", (session_id,))
            conn.commit()

    def toggle_favorite(self, session_id: str, movie_id: int) -> bool:
        """Toggle favorite status of a movie. Returns True if now favorited, False if removed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM user_favorites WHERE session_id = ? AND movie_id = ?", (session_id, movie_id))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("DELETE FROM user_favorites WHERE session_id = ? AND movie_id = ?", (session_id, movie_id))
                conn.commit()
                return False
            else:
                cursor.execute("INSERT INTO user_favorites (session_id, movie_id) VALUES (?, ?)", (session_id, movie_id))
                conn.commit()
                return True

    def get_favorites(self, session_id: str) -> List[int]:
        """Get list of favorited movie IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT movie_id FROM user_favorites WHERE session_id = ?", (session_id,))
            return [int(row["movie_id"]) for row in cursor.fetchall()]

"""auth.py — SQLite-backed Authentication & User State Persistence for CineMood & Bites.

Features:
- User registration, password hashing (PBKDF2-HMAC-SHA256), and login.
- Secure, tamper-proof session tokens (HMAC-SHA256 signed payload).
- SQLite tables for:
  * users (id, username, password_hash, salt, display_name, active_mood, created_at)
  * user_ratings (user_id, movie_id, rating, updated_at)
  * user_watchlist (user_id, movie_id, added_at)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("CineMood.Auth")

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "users.db"
SECRET_KEY = os.environ.get("CINEMOOD_SECRET_KEY", "cinemood_super_secret_session_key_2026")


def get_db_connection() -> sqlite3.Connection:
    """Create SQLite database connection with Row factory."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite database tables."""
    conn = get_db_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                active_mood TEXT DEFAULT 'joyful',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_ratings (
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                rating REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (user_id, movie_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_watchlist (
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                added_at REAL NOT NULL,
                PRIMARY KEY (user_id, movie_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_ratings_user ON user_ratings(user_id);
            CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id);
        """)
    conn.close()
    logger.info("SQLite database initialized at %s", DB_PATH.name)


init_db()


# ---------------- Password Hashing & Token Helpers ----------------

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return dk.hex(), salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Verify password against expected hash."""
    dk, _ = hash_password(password, salt)
    return hmac.compare_digest(dk, expected_hash)


def create_token(user_id: int, username: str, expires_in_seconds: int = 86400 * 7) -> str:
    """Generate a tamper-proof HMAC-SHA256 signed session token."""
    payload = {
        "uid": user_id,
        "un": username,
        "exp": int(time.time()) + expires_in_seconds,
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode HMAC-signed session token."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Add base64 padding
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)

        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)

        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception as e:
        logger.debug("Token validation failed: %s", e)
        return None


# ---------------- User Account Operations ----------------

def register_user(username: str, password: str, display_name: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Register a new user in SQLite."""
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long.", None
    if len(password) < 4:
        return False, "Password must be at least 4 characters long.", None

    display_name = display_name.strip() if display_name and display_name.strip() else username

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            return False, "Username is already taken.", None

        pw_hash, salt = hash_password(password)
        now = time.time()
        cur.execute(
            """INSERT INTO users (username, password_hash, salt, display_name, active_mood, created_at)
               VALUES (?, ?, ?, ?, 'joyful', ?)""",
            (username, pw_hash, salt, display_name, now),
        )
        conn.commit()
        user_id = cur.lastrowid
        token = create_token(user_id, username)

        return True, "Account created successfully.", {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "active_mood": "joyful",
            "token": token,
        }
    except Exception as e:
        logger.error("Registration error: %s", e)
        return False, f"Registration failed: {str(e)}", None
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Authenticate existing user credentials."""
    username = username.strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, salt, display_name, active_mood FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return False, "Invalid username or password.", None

        if not verify_password(password, row["salt"], row["password_hash"]):
            return False, "Invalid username or password.", None

        token = create_token(row["id"], row["username"])
        return True, "Login successful.", {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "active_mood": row["active_mood"],
            "token": token,
        }
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user profile by ID."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, display_name, active_mood, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_mood(user_id: int, mood: str) -> None:
    """Persist active mood selection for logged-in user."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE users SET active_mood = ? WHERE id = ?", (mood, user_id))
    finally:
        conn.close()


# ---------------- Ratings & Watchlist Persistence ----------------

def save_user_rating(user_id: int, movie_id: int, rating: float) -> None:
    """Insert or update user movie star rating in SQLite."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO user_ratings (user_id, movie_id, rating, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, movie_id) DO UPDATE SET rating = ?, updated_at = ?""",
                (user_id, movie_id, rating, time.time(), rating, time.time()),
            )
    finally:
        conn.close()


def get_user_ratings(user_id: int) -> Dict[int, float]:
    """Fetch all ratings submitted by user as {movieId: rating}."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT movie_id, rating FROM user_ratings WHERE user_id = ?", (user_id,))
        return {row["movie_id"]: row["rating"] for row in cur.fetchall()}
    finally:
        conn.close()


def toggle_user_watchlist(user_id: int, movie_id: int) -> bool:
    """Toggle movie presence in user's SQLite watchlist.
    
    Returns True if added, False if removed.
    """
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM user_watchlist WHERE user_id = ? AND movie_id = ?",
                (user_id, movie_id),
            )
            exists = cur.fetchone()
            if exists:
                conn.execute(
                    "DELETE FROM user_watchlist WHERE user_id = ? AND movie_id = ?",
                    (user_id, movie_id),
                )
                return False
            else:
                conn.execute(
                    "INSERT INTO user_watchlist (user_id, movie_id, added_at) VALUES (?, ?, ?)",
                    (user_id, movie_id, time.time()),
                )
                return True
    finally:
        conn.close()


def get_user_watchlist_ids(user_id: int) -> List[int]:
    """Get list of movie IDs in user's watchlist."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT movie_id FROM user_watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        )
        return [row["movie_id"] for row in cur.fetchall()]
    finally:
        conn.close()

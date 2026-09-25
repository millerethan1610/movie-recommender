"""poster_service.py — 100% Visible Poster Pipeline for CineMood & Bites.

Guarantees ZERO broken posters:
1. Sheet direct image/poster URL (if present in dataset).
2. Live TMDB/OMDb API resolution with local caching in `poster_cache.json`.
3. High-resolution dynamic vector SVG generator matching the movie's primary genre gradient,
   with stylized film reel icon, clean wrapped typography, and release badge.
"""

import html
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("CineMood.PosterService")

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_FILE = PROJECT_ROOT / "poster_cache.json"

# In-memory poster cache
_poster_cache: Dict[str, str] = {}

# Shared requests session with retry logic (survives connection resets)
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Return a shared requests.Session with automatic retry on connection errors."""
    global _session
    if _session is None:
        _session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=0.4,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
        _session.headers.update({"User-Agent": "CineMoodBites/2.5", "Accept": "application/json"})
    return _session


def _load_cache() -> None:
    """Load cached poster URLs from disk."""
    global _poster_cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _poster_cache = json.load(f)
                logger.info("Loaded %d cached poster URLs.", len(_poster_cache))
        except Exception as e:
            logger.debug("Failed loading poster cache: %s", e)
            _poster_cache = {}


def _save_cache() -> None:
    """Save cached poster URLs to disk."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_poster_cache, f, indent=2)
    except Exception as e:
        logger.debug("Failed saving poster cache: %s", e)


_load_cache()

# Genre-to-gradient aesthetic themes for SVG generation
GENRE_PALETTES: Dict[str, Dict[str, str]] = {
    "Action": {"start": "#7f1d1d", "end": "#18181b", "accent": "#f97316", "symbol": "⚡"},
    "Adventure": {"start": "#064e3b", "end": "#022c22", "accent": "#10b981", "symbol": "🧭"},
    "Animation": {"start": "#4c1d95", "end": "#1e1b4b", "accent": "#a855f7", "symbol": "✨"},
    "Comedy": {"start": "#78350f", "end": "#1c1917", "accent": "#fbbf24", "symbol": "🎭"},
    "Crime": {"start": "#27272a", "end": "#09090b", "accent": "#ef4444", "symbol": "🔍"},
    "Documentary": {"start": "#1e293b", "end": "#0f172a", "accent": "#38bdf8", "symbol": "🎥"},
    "Drama": {"start": "#312e81", "end": "#0f172a", "accent": "#818cf8", "symbol": "🍷"},
    "Fantasy": {"start": "#581c87", "end": "#18181b", "accent": "#c084fc", "symbol": "🔮"},
    "Film-Noir": {"start": "#18181b", "end": "#09090b", "accent": "#e4e4e7", "symbol": "🕵️"},
    "Horror": {"start": "#450a0a", "end": "#000000", "accent": "#dc2626", "symbol": "💀"},
    "Musical": {"start": "#831843", "end": "#18181b", "accent": "#f472b6", "symbol": "🎵"},
    "Mystery": {"start": "#1e1b4b", "end": "#020617", "accent": "#6366f1", "symbol": "🗝️"},
    "Romance": {"start": "#881337", "end": "#1f172a", "accent": "#fb7185", "symbol": "🌹"},
    "Sci-Fi": {"start": "#0c4a6e", "end": "#022c22", "accent": "#06b6d4", "symbol": "🚀"},
    "Thriller": {"start": "#3b0764", "end": "#09090b", "accent": "#d946ef", "symbol": "⏳"},
    "War": {"start": "#292524", "end": "#0c0a09", "accent": "#a8a29e", "symbol": "🎖️"},
    "Western": {"start": "#451a03", "end": "#1c1917", "accent": "#f59e0b", "symbol": "🤠"},
    "Default": {"start": "#18181b", "end": "#09090b", "accent": "#f59e0b", "symbol": "🎬"},
}


def sanitize_title(title: str) -> Tuple[str, Optional[int]]:
    """Strip trailing year parentheses and invert MovieLens articles.
    
    Example:
    'Toy Story (1995)' -> ('Toy Story', 1995)
    'Dark Knight, The' -> ('The Dark Knight', None)
    """
    clean = title.strip()
    year: Optional[int] = None

    m = re.search(r"^(.*?)\s*(?:\((\d{4})\))?$", clean)
    if m:
        clean = m.group(1).strip()
        if m.group(2):
            year = int(m.group(2))

    for article in (", The", ", A", ", An", ", Il", ", Le", ", La"):
        if clean.endswith(article):
            prefix = article.replace(",", "").strip() + " "
            clean = prefix + clean[: -len(article)].strip()
            break

    return clean, year


def fetch_tmdb_poster(title: str, year: Optional[int] = None) -> Optional[str]:
    """Fetch movie poster URL from TMDB using requests with automatic retries."""
    tmdb_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not tmdb_key:
        return None

    clean_t, extracted_y = sanitize_title(title)
    search_year = year or extracted_y

    cache_key = f"tmdb:{clean_t}:{search_year}"
    if cache_key in _poster_cache:
        return _poster_cache[cache_key]

    queries_to_try = [clean_t]
    for prefix in ("The ", "A ", "An "):
        if clean_t.startswith(prefix):
            queries_to_try.append(clean_t[len(prefix):])

    # Strip common dataset suffixes (e.g. 'Film', 'Series', 'Season Two', 'TVF ...')
    v1 = re.sub(r"\s+(Film|Series|Extra|Legacy|Superfan)$", "", clean_t, flags=re.I).strip()
    if v1 not in queries_to_try:
        queries_to_try.append(v1)
    v2 = re.sub(r"\s+Season\s+\w+$", "", v1, flags=re.I).strip()
    if v2 not in queries_to_try:
        queries_to_try.append(v2)
    v3 = re.sub(r"^(TVF\s+)", "", v2, flags=re.I).strip()
    if v3 not in queries_to_try:
        queries_to_try.append(v3)
    v4 = re.sub(r"\s+(\d{1,4})$", "", v3).strip()
    if v4 not in queries_to_try:
        queries_to_try.append(v4)
    v5 = re.sub(r"\s+(The Bihar Chapter|Part One|India|Part 1)$", "", v4, flags=re.I).strip()
    if v5 not in queries_to_try:
        queries_to_try.append(v5)

    sess = _get_session()

    for q in queries_to_try:
        # Try both movie and multi/tv endpoints
        for endpoint in ("search/movie", "search/multi", "search/tv"):
            for params in [
                {"api_key": tmdb_key, "query": q, "year": str(search_year)} if (search_year and endpoint == "search/movie") else None,
                {"api_key": tmdb_key, "query": q},
            ]:
                if params is None:
                    continue
                try:
                    resp = sess.get(
                        f"https://api.themoviedb.org/3/{endpoint}",
                        params=params,
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        for r in results:
                            p_path = r.get("poster_path")
                            if p_path:
                                poster_url = f"https://image.tmdb.org/t/p/w500{p_path}"
                                _poster_cache[cache_key] = poster_url
                                _save_cache()
                                return poster_url
                except Exception as e:
                    logger.debug("TMDB query failed for '%s' on %s: %s", q, endpoint, e)

    return None



def fetch_omdb_poster(title: str, year: Optional[int] = None) -> Optional[str]:
    """Fetch movie poster from OMDb API as backup using requests."""
    omdb_key = os.environ.get("OMDB_API_KEY", "").strip()
    if not omdb_key:
        return None

    clean_t, extracted_y = sanitize_title(title)
    search_year = year or extracted_y

    cache_key = f"omdb:{clean_t}:{search_year}"
    if cache_key in _poster_cache:
        return _poster_cache[cache_key]

    params: Dict[str, str] = {"apikey": omdb_key, "t": clean_t}
    if search_year:
        params["y"] = str(search_year)

    try:
        resp = _get_session().get("https://www.omdbapi.com/", params=params, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            poster = data.get("Poster")
            if poster and poster != "N/A" and poster.startswith("http"):
                _poster_cache[cache_key] = poster
                _save_cache()
                return poster
    except Exception as e:
        logger.debug("OMDb query failed: %s", e)

    return None


def resolve_movie_poster(
    movie_id: int,
    title: str,
    release_year: Optional[int] = None,
    dataset_poster_url: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve poster URL using the guaranteed 3-tier pipeline.
    
    Returns:
    - (poster_url, source_type) where source_type is 'sheet', 'tmdb', 'omdb', or 'svg'
    """
    # Tier 1: Direct URL from uploaded dataset
    if dataset_poster_url and dataset_poster_url.strip().startswith("http"):
        return dataset_poster_url.strip(), "sheet"

    # Tier 2: TMDB API
    tmdb_url = fetch_tmdb_poster(title, release_year)
    if tmdb_url:
        return tmdb_url, "tmdb"

    # Tier 2b: OMDb API
    omdb_url = fetch_omdb_poster(title, release_year)
    if omdb_url:
        return omdb_url, "omdb"

    # Tier 3: Guaranteed dynamic SVG endpoint
    return f"/api/poster/{movie_id}", "svg"


def generate_svg_poster(
    title: str,
    year: Optional[int] = None,
    genres: Optional[List[str]] = None,
    mood: str = "joyful",
) -> str:
    """Generate high-resolution dynamic vector SVG movie poster.
    
    Guarantees zero broken images with:
    - Genre-curated deep atmospheric gradient.
    - Stylized film reel icon.
    - Clean wrapped typography with shadow glow.
    - Category pill badge and release year.
    """
    genres = genres or ["Cinema"]
    primary_genre = genres[0] if genres else "Cinema"
    palette = GENRE_PALETTES.get(primary_genre, GENRE_PALETTES["Default"])

    year_str = str(year) if year else ""
    genre_display = " • ".join(genres[:2]) if len(genres) > 1 else primary_genre

    # Text wrapping for SVG
    clean_title, _ = sanitize_title(title)
    words = clean_title.split()
    lines: List[str] = []
    cur_line: List[str] = []

    for w in words:
        if sum(len(x) for x in cur_line) + len(cur_line) + len(w) > 17:
            if cur_line:
                lines.append(" ".join(cur_line))
                cur_line = [w]
            else:
                lines.append(w)
        else:
            cur_line.append(w)
    if cur_line:
        lines.append(" ".join(cur_line))

    # Keep at most 3 title lines
    lines = lines[:3]

    # Calculate line Y positions
    start_y = 420 - (len(lines) - 1) * 22
    line_tspans = "".join(
        f'<tspan x="200" y="{start_y + i * 44}">{html.escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{palette['start']}"/>
      <stop offset="45%" stop-color="#141419"/>
      <stop offset="100%" stop-color="{palette['end']}"/>
    </linearGradient>

    <radialGradient id="ambientGlow" cx="50%" cy="30%" r="65%">
      <stop offset="0%" stop-color="{palette['accent']}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="goldBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{palette['accent']}" stop-opacity="0.7"/>
      <stop offset="50%" stop-color="{palette['accent']}" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="{palette['accent']}" stop-opacity="0.6"/>
    </linearGradient>

    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>

    <pattern id="filmStrip" x="0" y="0" width="400" height="20" patternUnits="userSpaceOnUse">
      <rect width="400" height="20" fill="rgba(0,0,0,0.4)"/>
      <rect x="10" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="40" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="70" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="100" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="130" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="160" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="190" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="220" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="250" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="280" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="310" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="340" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
      <rect x="370" y="4" width="14" height="12" rx="2" fill="rgba(255,255,255,0.08)"/>
    </pattern>
  </defs>

  <!-- Background Base -->
  <rect width="400" height="600" fill="url(#bgGrad)"/>
  <rect width="400" height="600" fill="url(#ambientGlow)"/>

  <!-- Top and Bottom Film Perforations -->
  <rect y="0" width="400" height="16" fill="url(#filmStrip)"/>
  <rect y="584" width="400" height="16" fill="url(#filmStrip)"/>

  <!-- Stylized Decorative Frame -->
  <rect x="16" y="24" width="368" height="552" rx="12" fill="none" stroke="url(#goldBorder)" stroke-width="1.5"/>

  <!-- Top Vibe Pill -->
  <g transform="translate(200, 60)">
    <rect x="-80" y="-14" width="160" height="28" rx="14" fill="rgba(0,0,0,0.6)" stroke="{palette['accent']}" stroke-width="1"/>
    <text text-anchor="middle" y="5" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="11" font-weight="700" fill="{palette['accent']}" letter-spacing="1.5">
      CINEMOOD &amp; BITES
    </text>
  </g>

  <!-- Center Film Reel Icon -->
  <g transform="translate(200, 210)" filter="url(#softGlow)">
    <!-- Reel Outer Ring -->
    <circle r="72" fill="rgba(10,10,12,0.6)" stroke="{palette['accent']}" stroke-width="3"/>
    <circle r="60" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
    <!-- Reel Holes -->
    <circle cx="0" cy="-36" r="14" fill="{palette['start']}"/>
    <circle cx="36" cy="0" r="14" fill="{palette['start']}"/>
    <circle cx="0" cy="36" r="14" fill="{palette['start']}"/>
    <circle cx="-36" cy="0" r="14" fill="{palette['start']}"/>
    <!-- Center Hub -->
    <circle r="18" fill="{palette['accent']}"/>
    <circle r="7" fill="#000000"/>
    <!-- Emoji symbol -->
    <text text-anchor="middle" y="6" font-size="16">{palette['symbol']}</text>
  </g>

  <!-- Movie Title Block -->
  <g id="titleGroup">
    <text text-anchor="middle" font-family="'Outfit', 'Plus Jakarta Sans', system-ui, sans-serif" font-size="28" font-weight="800" fill="#ffffff" letter-spacing="0.5">
      {line_tspans}
    </text>
  </g>

  <!-- Genre & Release Year Badge -->
  <g transform="translate(200, 520)">
    <rect x="-110" y="-16" width="220" height="32" rx="16" fill="rgba(0,0,0,0.7)" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
    <text text-anchor="middle" y="5" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="12" font-weight="600" fill="rgba(255,255,255,0.85)">
      {html.escape(genre_display)}{f'  •  {year_str}' if year_str else ''}
    </text>
  </g>
</svg>"""
    return svg

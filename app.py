"""app.py — FastAPI Application Server for CineMood & Bites.

Features:
- Dynamic Excel/CSV drag-and-drop upload endpoint with instant live re-indexing.
- 100% visible poster pipeline with TMDB lazy lookup and guaranteed dynamic SVG poster generator.
- Paginated catalog browsing, real-time debounced full-text search, and hybrid recommendations.
- Mood-aligned authentication suite backed by SQLite.
- Static file mounting and HTML5 frontend delivery.
"""

import logging
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
from data_loader import load_dataset, normalize_movies_dataframe, read_file_to_dataframe
from pairings import get_movie_pairings
from poster_service import generate_svg_poster, resolve_movie_poster
from recommender import MOOD_PROFILES, RecommenderEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CineMood.App")

PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"

# Global Recommender Engine Instance
engine: Optional[RecommenderEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize the ML models and data pipeline on startup."""
    global engine
    logger.info("Initializing CineMood & Bites backend & machine learning models...")
    try:
        movies_df, ratings_df, source_name = load_dataset()
        engine = RecommenderEngine(movies_df=movies_df, ratings_df=ratings_df, source_name=source_name)
        logger.info("CineMood engine ready with %d movies from %s!", len(engine.movie_meta), source_name)
        # Immediately apply cached TMDB posters synchronously (zero latency, zero broken images)
        _apply_cached_posters_to_engine()
        # Pre-resolve any remaining posters in background so they are available immediately
        threading.Thread(target=_prefetch_all_posters, daemon=True).start()
    except Exception as e:
        logger.error("Failed initializing recommender engine: %s", e)
        raise e
    yield
    logger.info("CineMood & Bites backend shutting down.")


def _apply_cached_posters_to_engine() -> None:
    """Immediately populate poster_url from in-memory cache without network latency."""
    from poster_service import _poster_cache, sanitize_title
    if not engine:
        return
    count = 0
    for mid, meta in engine.movie_meta.items():
        if meta.get("poster_url", "").startswith("http"):
            continue
        raw_title = meta.get("raw_title", meta["title"])
        year = meta.get("release_year")
        clean_t, extracted_y = sanitize_title(raw_title)
        search_year = year or extracted_y
        cache_key = f"tmdb:{clean_t}:{search_year}"
        if cache_key in _poster_cache and _poster_cache[cache_key].startswith("http"):
            engine.movie_meta[mid]["poster_url"] = _poster_cache[cache_key]
            count += 1
    if count > 0:
        logger.info("Pre-applied %d cached poster URLs to engine metadata on startup.", count)



def _prefetch_all_posters() -> None:
    """Resolve TMDB poster URLs for every movie and cache them in movie_meta.

    Runs concurrently in a thread pool so the server isn't blocked.
    Already-resolved or sheet-provided posters are skipped.
    """
    if not engine:
        return
    movies_needing_posters = [
        (mid, meta)
        for mid, meta in engine.movie_meta.items()
        if not meta.get("poster_url", "").startswith("http")
    ]
    if not movies_needing_posters:
        logger.info("All posters already resolved — skipping prefetch.")
        return

    logger.info("Prefetching TMDB posters for %d movies in background...", len(movies_needing_posters))
    resolved = 0

    def _resolve_one(mid: int, meta: Dict[str, Any]) -> None:
        nonlocal resolved
        poster_url, source = resolve_movie_poster(
            movie_id=mid,
            title=meta.get("raw_title", meta["title"]),
            release_year=meta.get("release_year"),
            dataset_poster_url=meta.get("poster_url"),
        )
        if source in ("tmdb", "omdb", "sheet"):
            engine.movie_meta[mid]["poster_url"] = poster_url
            resolved += 1

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_resolve_one, mid, meta): mid for mid, meta in movies_needing_posters}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.debug("Poster prefetch error for movie %s: %s", futures[future], exc)

    logger.info("Poster prefetch complete: %d/%d posters resolved via TMDB/OMDb.", resolved, len(movies_needing_posters))


app = FastAPI(
    title="CineMood & Bites API",
    description="Live Cinema Recommendations with Dynamic Mood Themes, Pairings & Excel Ingestion",
    version="2.5.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Auth Dependencies ----------------

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Optional authentication dependency: returns user dict if valid Bearer token provided."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    payload = auth.verify_token(token)
    if not payload:
        return None
    return auth.get_user_by_id(payload["uid"])


def require_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Mandatory authentication dependency: raises 401 if missing or invalid token."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )
    return user


# ---------------- Pydantic Request Models ----------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    display_name: Optional[str] = Field(None, max_length=50)


class LoginRequest(BaseModel):
    username: str
    password: str


class RecommendRequest(BaseModel):
    mood: str = "joyful"
    genres: Optional[List[str]] = None
    min_rating: float = 0.0
    decade: Optional[str] = None
    limit: int = Field(default=24, ge=1, le=100)
    cf_weight: float = Field(default=0.40, ge=0.0, le=1.0)
    mood_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    content_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    media_type: Optional[str] = None
    session_id: str = "guest_session"


class RateRequest(BaseModel):
    movie_id: int
    rating: float = Field(..., ge=0.5, le=5.0)


class MoodUpdateRequest(BaseModel):
    mood: str


class WatchlistToggleRequest(BaseModel):
    movie_id: int


# ---------------- Dataset & System Endpoints ----------------

@app.get("/api/health")
def health_check():
    """System health check and catalog statistics."""
    return {
        "status": "healthy",
        "app_name": "CineMood & Bites",
        "engine_ready": engine is not None,
        "movies_loaded": len(engine.movie_meta) if engine else 0,
        "source": engine.source_name if engine else "None",
    }


@app.post("/api/upload-dataset")
async def upload_custom_dataset(file: UploadFile = File(...)):
    """Dynamic Excel/CSV upload endpoint.
    
    Accepts .xlsx, .xls, or .csv files and instantly re-indexes the entire
    recommender system in-memory without server restart!
    """
    global engine
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    filename_lower = file.filename.lower()
    suffix = Path(filename_lower).suffix
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.",
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_target = DATA_DIR / f"uploaded_dataset{suffix}"

    try:
        with open(temp_target, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        raw_df = read_file_to_dataframe(temp_target)
        if raw_df.empty:
            raise HTTPException(status_code=400, detail="The uploaded sheet contains no data rows.")

        normalized_df = normalize_movies_dataframe(raw_df)
        ratings_df = engine.ratings_df if engine else None
        if ratings_df is None:
            import pandas as pd
            ratings_df = pd.DataFrame()

        source_name = f"Uploaded: {file.filename} ({len(normalized_df):,} movies)"

        if engine:
            engine.reindex(movies_df=normalized_df, ratings_df=ratings_df, source_name=source_name)
        else:
            engine = RecommenderEngine(movies_df=normalized_df, ratings_df=ratings_df, source_name=source_name)

        logger.info("Successfully re-indexed system with %d movies from %s", len(normalized_df), file.filename)
        return {
            "success": True,
            "message": f"Successfully loaded {len(normalized_df):,} movies from {file.filename}!",
            "movies_count": len(normalized_df),
            "source_name": source_name,
        }
    except Exception as e:
        logger.error("Dataset upload failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed processing sheet: {str(e)}")


# ---------------- Metadata Endpoints ----------------

@app.get("/api/moods")
def get_moods():
    """Return all 5 cinema mood profiles and their theme attributes."""
    return MOOD_PROFILES


@app.get("/api/genres")
def get_genres():
    """Return unique genre list indexed from current dataset."""
    if not engine:
        raise HTTPException(status_code=503, detail="Recommender engine is still initializing.")
    return engine.all_genres


# ---------------- Movie Catalog & Search ----------------

@app.get("/api/movies")
def get_movies(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
    genre: str = Query(default=""),
    mood: str = Query(default=""),
    search: str = Query(default="", alias="q"),
    media_type: str = Query(default=""),
):
    """Paginated catalog browser with real-time title, director, and genre search."""
    if not engine:
        raise HTTPException(status_code=503, detail="Recommender engine is still initializing.")

    return engine.get_paginated_catalog(
        page=page,
        limit=limit,
        genre=genre,
        mood=mood,
        search=search,
        media_type=media_type,
    )


@app.get("/api/movies/{movie_id}")
def get_movie_detail(
    movie_id: int,
    mood: str = Query(default="joyful"),
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Full movie details with food/drink pairings, Spotify player info, and 4 related films."""
    if not engine:
        raise HTTPException(status_code=503, detail="Recommender engine is still initializing.")

    if movie_id not in engine.movie_meta:
        raise HTTPException(status_code=404, detail="Movie ID not found in catalog.")

    meta = engine.movie_meta[movie_id].copy()
    pairings = get_movie_pairings(meta, mood)
    related = engine.get_related_movies(movie_id, limit=4, mood=mood)

    user_rating = None
    is_in_watchlist = False
    if user:
        ratings = auth.get_user_ratings(user["id"])
        user_rating = ratings.get(movie_id)
        watchlist_ids = set(auth.get_user_watchlist_ids(user["id"]))
        is_in_watchlist = movie_id in watchlist_ids

    return {
        "movie": {
            **meta,
            "pairings": pairings,
            "user_rating": user_rating,
            "is_in_watchlist": is_in_watchlist,
        },
        "related_movies": related,
    }


# ---------------- 100% Visible Poster Pipeline ----------------

@app.get("/api/poster/{movie_id}/url")
def get_poster_url(
    movie_id: int,
    mood: str = Query(default="joyful"),
):
    """Resolve poster URL via the 3-tier pipeline (sheet -> TMDB -> OMDb -> SVG)."""
    if not engine or movie_id not in engine.movie_meta:
        return {"poster_url": f"/api/poster/{movie_id}?mood={mood}", "source": "svg"}

    meta = engine.movie_meta[movie_id]
    poster_url, source = resolve_movie_poster(
        movie_id=movie_id,
        title=meta.get("raw_title", meta["title"]),
        release_year=meta.get("release_year"),
        dataset_poster_url=meta.get("poster_url"),
    )
    if source in ("tmdb", "omdb"):
        engine.movie_meta[movie_id]["poster_url"] = poster_url

    return {"poster_url": poster_url, "source": source}


@app.get("/api/poster/{movie_id}")
def get_dynamic_svg_poster(
    movie_id: int,
    mood: str = Query(default="joyful"),
):
    """Generate dynamic high-resolution SVG poster vector graphic (Zero Broken Images)."""
    if not engine or movie_id not in engine.movie_meta:
        title = "Featured Film"
        year = None
        genres = ["Cinema"]
    else:
        meta = engine.movie_meta[movie_id]
        title = meta["title"]
        year = meta.get("release_year")
        genres = meta.get("genres", ["Cinema"])

    svg_data = generate_svg_poster(title=title, year=year, genres=genres, mood=mood)
    return Response(
        content=svg_data,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------- Recommendations ----------------

@app.post("/api/recommend")
def get_recommendations(
    req: RecommendRequest,
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Compute personalized recommendations based on mood, user ratings, and filters."""
    if not engine:
        raise HTTPException(status_code=503, detail="Recommender engine is still initializing.")

    user_ratings = {}
    if user:
        user_ratings = auth.get_user_ratings(user["id"])

    recommendations = engine.recommend(
        mood=req.mood,
        selected_genres=req.genres,
        min_rating=req.min_rating,
        decade=req.decade,
        user_ratings=user_ratings,
        limit=req.limit,
        cf_weight=req.cf_weight,
        mood_weight=req.mood_weight,
        content_weight=req.content_weight,
        media_type=req.media_type,
    )

    watchlist_ids = set(auth.get_user_watchlist_ids(user["id"])) if user else set()
    for rec in recommendations:
        rec["user_rating"] = user_ratings.get(rec["movieId"])
        rec["is_in_watchlist"] = rec["movieId"] in watchlist_ids

    return {
        "mood": req.mood,
        "total_recommendations": len(recommendations),
        "results": recommendations,
    }


# ---------------- Authentication & User Operations ----------------

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    """Register a new user in SQLite."""
    success, message, user_data = auth.register_user(req.username, req.password, req.display_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "user": user_data}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Log in existing user and issue session token."""
    success, message, user_data = auth.authenticate_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=401, detail=message)
    return {"success": True, "message": message, "user": user_data}


@app.get("/api/auth/me")
def get_current_user_profile(user: Dict[str, Any] = Depends(require_current_user)):
    """Fetch profile of currently signed-in user."""
    ratings = auth.get_user_ratings(user["id"])
    watchlist_ids = auth.get_user_watchlist_ids(user["id"])
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "active_mood": user.get("active_mood", "joyful"),
        "ratings_count": len(ratings),
        "watchlist_count": len(watchlist_ids),
    }


@app.post("/api/rate")
def rate_movie(req: RateRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """Record user star rating (1.0 to 5.0) in SQLite or guest session."""
    if not engine or req.movie_id not in engine.movie_meta:
        raise HTTPException(status_code=404, detail="Movie not found.")

    if user:
        auth.save_user_rating(user["id"], req.movie_id, req.rating)
        total_rated = len(auth.get_user_ratings(user["id"]))
    else:
        total_rated = 1

    return {
        "success": True,
        "movie_id": req.movie_id,
        "rating": req.rating,
        "total_rated": total_rated,
    }


@app.get("/api/ratings")
def get_ratings(user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """Get all ratings recorded for the logged-in user."""
    if not user:
        return {}
    return auth.get_user_ratings(user["id"])


@app.post("/api/watchlist/toggle")
def toggle_watchlist(req: WatchlistToggleRequest, user: Dict[str, Any] = Depends(require_current_user)):
    """Add or remove movie from user's persistent SQLite watchlist."""
    if not engine or req.movie_id not in engine.movie_meta:
        raise HTTPException(status_code=404, detail="Movie not found.")

    is_added = auth.toggle_user_watchlist(user["id"], req.movie_id)
    return {
        "success": True,
        "movie_id": req.movie_id,
        "is_in_watchlist": is_added,
        "total_watchlist": len(auth.get_user_watchlist_ids(user["id"])),
    }


@app.get("/api/watchlist")
def get_watchlist(
    mood: str = Query(default="joyful"),
    user: Dict[str, Any] = Depends(require_current_user),
):
    """Retrieve full movie metadata and pairings for movies in user's watchlist."""
    if not engine:
        raise HTTPException(status_code=503, detail="Recommender engine is still initializing.")

    watchlist_ids = auth.get_user_watchlist_ids(user["id"])
    items = []
    for mid in watchlist_ids:
        if mid in engine.movie_meta:
            m = engine.movie_meta[mid].copy()
            m["pairings"] = get_movie_pairings(m, mood)
            items.append(m)

    return {"results": items, "total_count": len(items)}


@app.post("/api/user/mood")
def set_user_mood(req: MoodUpdateRequest, user: Dict[str, Any] = Depends(require_current_user)):
    """Save selected mood to user profile."""
    auth.update_user_mood(user["id"], req.mood)
    return {"success": True, "active_mood": req.mood}


# ---------------- Static Files & SPA Delivery ----------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    """Deliver index.html or static assets."""
    file_path = STATIC_DIR / full_path
    if full_path and file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail="Static frontend not found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5001, reload=True)
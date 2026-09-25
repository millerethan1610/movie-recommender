"""Automated test suite for CineMatch Movie Recommender System.

Tests:
- Data loader and preprocessing
- Recommender engine (IBCF, TF-IDF CBF, Hybrid Mood Scorer)
- Explainability reason generator
- Offline evaluation metrics (Precision@K, Recall@K, Coverage, Sparsity)
- Session database storage
- FastAPI REST endpoints
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd
from starlette.testclient import TestClient

from app import app
from data_loader import extract_year_and_clean_title, load_dataset
from recommender import MOOD_PROFILES, RecommenderEngine
from session_db import SessionStore


def test_clean_title_and_year_extraction():
    """Test title cleaning and release year extraction regex."""
    title, year = extract_year_and_clean_title("Toy Story (1995)")
    assert title == "Toy Story"
    assert year == 1995

    title2, year2 = extract_year_and_clean_title("Dark Knight, The (2008)")
    assert title2 == "The Dark Knight"
    assert year2 == 2008

    title3, year3 = extract_year_and_clean_title("Interstellar")
    assert title3 == "Interstellar"
    assert year3 is None


def test_data_loader_ingestion():
    """Test that dataset loads properly with required columns and Bayesian scores."""
    movies_df, ratings_df, source_name = load_dataset()
    assert len(movies_df) > 50
    assert len(ratings_df) > 100
    assert "clean_title" in movies_df.columns
    assert "release_year" in movies_df.columns
    assert "bayesian_score" in movies_df.columns
    assert "avg_rating" in movies_df.columns
    assert "genres" in movies_df.columns
    assert source_name in ["MovieLens Latest-Small", "Bundled Fallback Dataset"]


_shared_engine = None

def get_test_engine():
    global _shared_engine
    if _shared_engine is None:
        movies_df, ratings_df, source_name = load_dataset()
        _shared_engine = RecommenderEngine(movies_df, ratings_df, source_name=source_name)
    return _shared_engine


def test_recommender_engine_init():
    """Test recommender engine matrices and indexing."""
    engine = get_test_engine()
    assert len(engine.movie_meta) > 0
    assert engine.user_item_matrix is not None
    assert engine.item_similarity_matrix is not None
    assert engine.tfidf_matrix is not None
    assert len(engine.all_genres) > 0


def test_recommender_all_moods():
    """Test recommendations for all 5 moods and verify output structure."""
    engine = get_test_engine()
    moods = ["joyful", "melancholy", "thrilling", "adventurous", "cozy"]
    for mood in moods:
        recs = engine.recommend(mood=mood, limit=5)
        assert len(recs) == 5
        for r in recs:
            assert "movieId" in r
            assert "title" in r
            assert "match_score" in r
            assert 60 <= r["match_score"] <= 99
            assert "reasons" in r
            assert len(r["reasons"]) > 0


def test_collaborative_filtering_adaptation():
    """Test that giving high ratings to specific movies adapts the recommendations."""
    engine = get_test_engine()

    # Search for Inception
    search_results = engine.search_movies("Inception", limit=1)
    assert len(search_results) > 0
    inception_id = search_results[0]["movieId"]

    # User rates Inception 5.0
    user_ratings = {inception_id: 5.0}
    recs_after = engine.recommend(mood="thrilling", user_ratings=user_ratings, limit=10)

    # Inception itself must not appear in recommendations (already rated)
    rec_ids = [r["movieId"] for r in recs_after]
    assert inception_id not in rec_ids


def test_filter_genre_and_min_rating():
    """Test genre multi-select and min_rating threshold filters."""
    engine = get_test_engine()

    recs = engine.recommend(
        mood="adventurous",
        selected_genres=["Animation"],
        min_rating=3.5,
        limit=8
    )

    for r in recs:
        assert "Animation" in r["genres"]
        assert r["avg_rating"] >= 3.5


def test_offline_evaluation_metrics():
    """Test calculation of Precision@K, Recall@K, Coverage, and Sparsity."""
    engine = get_test_engine()
    metrics = engine.evaluate_model(k=10)
    assert "precision_at_k" in metrics
    assert "recall_at_k" in metrics
    assert "catalog_coverage" in metrics
    assert "matrix_sparsity" in metrics
    assert 0.0 <= metrics["precision_at_k"] <= 1.0
    assert 0.0 <= metrics["recall_at_k"] <= 1.0
    assert 0.8 <= metrics["matrix_sparsity"] <= 1.0


def test_session_store():
    """Test SQLite session persistence."""
    test_db_path = BASE_DIR / "data" / "test_sessions.db"
    if test_db_path.exists():
        test_db_path.unlink()

    store = SessionStore(db_path=test_db_path)
    session_id = "test_user_session_42"

    # Set rating
    store.set_rating(session_id, movie_id=10, rating=4.5)
    store.set_rating(session_id, movie_id=20, rating=5.0)

    ratings = store.get_ratings(session_id)
    assert len(ratings) == 2
    assert ratings[10] == 4.5
    assert ratings[20] == 5.0

    # Toggle favorite
    is_fav = store.toggle_favorite(session_id, movie_id=10)
    assert is_fav is True
    assert 10 in store.get_favorites(session_id)

    # Remove rating
    store.remove_rating(session_id, movie_id=10)
    ratings_after = store.get_ratings(session_id)
    assert len(ratings_after) == 1
    assert 10 not in ratings_after

    # Cleanup
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except OSError:
            pass


def test_fastapi_endpoints():
    """Test FastAPI endpoints using TestClient."""
    with TestClient(app) as client:
        # Health check
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        # Moods
        res = client.get("/api/moods")
        assert res.status_code == 200
        moods = res.json()
        assert len(moods) == 5

        # Genres
        res = client.get("/api/genres")
        assert res.status_code == 200
        assert len(res.json()) > 5

        # Search
        res = client.get("/api/movies?q=Toy&limit=5")
        assert res.status_code == 200
        assert len(res.json()) > 0

        # Rate movie
        res = client.post("/api/rate", json={
            "session_id": "test_fastapi_session",
            "movie_id": 1,
            "rating": 5.0
        })
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Get ratings
        res = client.get("/api/ratings?session_id=test_fastapi_session")
        assert res.status_code == 200
        assert res.json()["total"] >= 1

        # Recommendations
        res = client.post("/api/recommend", json={
            "session_id": "test_fastapi_session",
            "mood": "adventurous",
            "limit": 6
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 6

        # Movie Detail & Related Endpoint
        res = client.get("/api/movies/1?mood=joyful&session_id=test_fastapi_session")
        assert res.status_code == 200
        detail_data = res.json()
        assert "movie" in detail_data
        assert "related_movies" in detail_data
        assert "pairings" in detail_data["movie"]
        assert len(detail_data["related_movies"]) <= 4

        # Dynamic SVG Poster Generation (Zero broken images)
        res = client.get("/api/poster/1.svg?mood=joyful")
        assert res.status_code == 200
        assert "image/svg+xml" in res.headers.get("content-type", "")
        assert "<svg" in res.text
        assert "CINEMOOD &amp; BITES" in res.text

        # Metrics
        res = client.get("/api/metrics")
        assert res.status_code == 200
        assert "precision_at_k" in res.json()


def test_movie_pairings():
    """Test movie pairings engine for iconic Easter eggs, genres, and moods."""
    from pairings import get_movie_pairings
    
    # Test iconic Easter egg
    inception_pair = get_movie_pairings({"title": "Inception (2010)", "genres": ["Sci-Fi", "Action"]})
    assert "Mille-Feuille" in inception_pair["food"]
    assert "Espresso Martini" in inception_pair["drink"]

    # Test genre pairing
    scifi_pair = get_movie_pairings({"title": "Random Space Odyssey", "genres": ["Sci-Fi"]})
    assert len(scifi_pair["food"]) > 0
    assert len(scifi_pair["drink"]) > 0
    assert len(scifi_pair["ambiance"]) > 0

    # Test mood fallback
    mood_pair = get_movie_pairings({"title": "Unknown Title", "genres": []}, mood="cozy")
    assert "Grilled Cheese" in mood_pair["food"]


def test_search_by_director_and_actor():
    """Test searching by Director (Nolan) and Actor (DiCaprio)."""
    engine = get_test_engine()

    # Search by director
    dir_results = engine.search_movies("Nolan", limit=5)
    assert len(dir_results) > 0
    assert any(r["match_type"] == "director" or "Nolan" in r.get("director", "") for r in dir_results)

    # Search by actor
    actor_results = engine.search_movies("DiCaprio", limit=5)
    assert len(actor_results) > 0
    assert any(r["match_type"] == "actor" or "DiCaprio" in r.get("cast", "") for r in actor_results)


if __name__ == "__main__":
    tests = [
        test_clean_title_and_year_extraction,
        test_data_loader_ingestion,
        test_recommender_engine_init,
        test_recommender_all_moods,
        test_collaborative_filtering_adaptation,
        test_filter_genre_and_min_rating,
        test_offline_evaluation_metrics,
        test_session_store,
        test_fastapi_endpoints,
        test_movie_pairings,
        test_search_by_director_and_actor,
    ]
    print(f"Running {len(tests)} automated tests...")
    passed = 0
    for t in tests:
        name = t.__name__
        try:
            print(f"  [RUNNING] {name}...", end="", flush=True)
            t()
            print("  PASSED")
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nResult: {passed}/{len(tests)} tests passed successfully.")
    if passed != len(tests):
        sys.exit(1)


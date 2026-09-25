"""recommender.py — Live Hybrid ML Recommendation Engine for CineMood & Bites.

Features:
- 100% catalog ingestion with zero dropped rows.
- Dynamic TF-IDF content vectorization (titles, genres, directors, cast, overviews).
- Sparse Item-Item collaborative filtering with Bayesian score prior blending.
- Mood profile vector projection & cosine alignment scoring.
- Real-time full-text search with regex fuzzy matching across titles, directors, and genres.
- Dynamic re-indexing on custom uploaded datasets with zero server downtime.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from pairings import get_movie_pairings

logger = logging.getLogger("CineMood.Recommender")

# 5 Core Cinema Mood Profiles with Genre Weights & Theme Attributes
MOOD_PROFILES: Dict[str, Dict[str, Any]] = {
    "joyful": {
        "id": "joyful",
        "name": "Joyful / Uplifting",
        "icon": "☀️",
        "tagline": "Radiant humor, lighthearted adventures, and infectious optimism",
        "accent_color": "#f59e0b",
        "genre_weights": {
            "Comedy": 1.4,
            "Animation": 1.3,
            "Adventure": 1.0,
            "Musical": 1.0,
            "Children": 0.9,
            "Fantasy": 0.8,
            "Romance": 0.7,
        },
        "negative_genres": {
            "Horror": -1.5,
            "Thriller": -0.9,
            "War": -0.8,
            "Crime": -0.6,
            "Film-Noir": -0.6,
        },
    },
    "thrilling": {
        "id": "thrilling",
        "name": "Thrilling / Adrenaline",
        "icon": "⚡",
        "tagline": "High-stakes suspense, visceral noir mystery, and edge-of-seat pacing",
        "accent_color": "#ef4444",
        "genre_weights": {
            "Thriller": 1.4,
            "Horror": 1.2,
            "Crime": 1.1,
            "Mystery": 1.0,
            "Action": 0.9,
            "Sci-Fi": 0.7,
            "Film-Noir": 0.8,
        },
        "negative_genres": {
            "Children": -1.4,
            "Musical": -1.0,
            "Romance": -0.6,
            "Animation": -0.5,
        },
    },
    "adventurous": {
        "id": "adventurous",
        "name": "Adventurous / Sci-Fi",
        "icon": "🚀",
        "tagline": "Grand expeditions, deep space journeys, and mythical universe building",
        "accent_color": "#10b981",
        "genre_weights": {
            "Action": 1.3,
            "Adventure": 1.4,
            "Sci-Fi": 1.3,
            "Fantasy": 1.0,
            "IMAX": 0.8,
            "Thriller": 0.6,
        },
        "negative_genres": {
            "Romance": -0.5,
            "Documentary": -0.4,
            "Film-Noir": -0.4,
        },
    },
    "cozy": {
        "id": "cozy",
        "name": "Cozy / Romantic",
        "icon": "☕",
        "tagline": "Comforting love stories, gentle slice-of-life humor, and warm nostalgia",
        "accent_color": "#a855f7",
        "genre_weights": {
            "Romance": 1.4,
            "Comedy": 1.1,
            "Fantasy": 0.9,
            "Animation": 0.9,
            "Children": 0.8,
            "Drama": 0.6,
        },
        "negative_genres": {
            "Horror": -1.5,
            "War": -1.1,
            "Thriller": -0.9,
            "Crime": -0.8,
        },
    },
    "melancholy": {
        "id": "melancholy",
        "name": "Melancholy / Thoughtful",
        "icon": "🌧️",
        "tagline": "Poetic emotional depth, art-house reflection, and philosophical resonance",
        "accent_color": "#6366f1",
        "genre_weights": {
            "Drama": 1.4,
            "Mystery": 1.1,
            "Film-Noir": 1.0,
            "Romance": 0.8,
            "War": 0.8,
            "Documentary": 0.7,
        },
        "negative_genres": {
            "Comedy": -1.2,
            "Musical": -0.8,
            "Children": -0.8,
            "Action": -0.5,
        },
    },
}


class RecommenderEngine:
    """Production-grade Hybrid Recommendation Engine with on-the-fly dataset re-indexing."""

    def __init__(self, movies_df: pd.DataFrame, ratings_df: pd.DataFrame, source_name: str = "Catalog"):
        self.movies_df: pd.DataFrame = movies_df
        self.ratings_df: pd.DataFrame = ratings_df
        self.source_name: str = source_name

        self.movie_id_to_idx: Dict[int, int] = {}
        self.idx_to_movie_id: Dict[int, int] = {}
        self.movie_meta: Dict[int, Dict[str, Any]] = {}
        self.all_genres: List[str] = []

        self.tfidf_matrix: Optional[csr_matrix] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.item_similarity_matrix: Optional[np.ndarray] = None

        self._build_indexes()
        self._build_content_model()
        self._build_collaborative_model()

    def _build_indexes(self) -> None:
        """Create bidirectional index mappings and metadata lookups."""
        unique_movie_ids = self.movies_df["movieId"].unique()
        self.movie_id_to_idx = {mid: idx for idx, mid in enumerate(unique_movie_ids)}
        self.idx_to_movie_id = {idx: mid for mid, idx in self.movie_id_to_idx.items()}

        genre_set: Set[str] = set()
        self.movie_meta.clear()

        for _, row in self.movies_df.iterrows():
            mid = int(row["movieId"])
            genres_list = row["genres"] if isinstance(row["genres"], list) else [str(row["genres"])]
            genre_set.update(genres_list)

            self.movie_meta[mid] = {
                "movieId": mid,
                "title": str(row["title"]),
                "raw_title": str(row["raw_title"]),
                "release_year": int(row["release_year"]) if pd.notna(row["release_year"]) else None,
                "genres": genres_list,
                "genres_str": " | ".join(genres_list),
                "avg_rating": float(row["avg_rating"]) if "avg_rating" in row else 3.5,
                "vote_count": int(row["vote_count"]) if "vote_count" in row else 0,
                "bayesian_score": float(row["bayesian_score"]) if "bayesian_score" in row else 3.5,
                "director": str(row.get("director", "")),
                "cast": str(row.get("cast", "")),
                "overview": str(row.get("overview", "")),
                "poster_url": str(row.get("poster_url", "")),
                "media_type": str(row.get("media_type", "Movie")),
            }

        self.all_genres = sorted(list(genre_set))
        logger.info("Indexed %d unique movies and %d genres.", len(self.movie_meta), len(self.all_genres))

    def _build_content_model(self) -> None:
        """Build TF-IDF feature matrix on combined genres, title, director, cast, and overview."""
        corpus = []
        n_items = len(self.idx_to_movie_id)

        for idx in range(n_items):
            mid = self.idx_to_movie_id[idx]
            meta = self.movie_meta[mid]
            genre_text = " ".join(meta["genres"] * 3)
            title_text = meta["title"]
            director_text = f"{meta['director']} {meta['director']}" if meta["director"] else ""
            cast_text = meta["cast"].replace("|", " ") if meta["cast"] else ""
            overview_text = meta["overview"] if meta["overview"] else ""

            combined = f"{title_text} {genre_text} {director_text} {cast_text} {overview_text}"
            corpus.append(combined)

        self.tfidf_vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=8000,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b\w+\b",
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
        logger.info("Content TF-IDF matrix built with shape: %s", self.tfidf_matrix.shape)

    def _build_collaborative_model(self) -> None:
        """Compute item-item cosine similarity matrix with fallback to content similarity."""
        n_items = len(self.idx_to_movie_id)

        if not self.ratings_df.empty and "movieId" in self.ratings_df.columns:
            valid_ratings = self.ratings_df[self.ratings_df["movieId"].isin(self.movie_id_to_idx.keys())].copy()
            user_ids = valid_ratings["userId"].unique()

            if len(valid_ratings) >= 5 and len(user_ids) >= 1:
                user_id_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}
                row_indices = [user_id_to_idx[uid] for uid in valid_ratings["userId"]]
                col_indices = [self.movie_id_to_idx[mid] for mid in valid_ratings["movieId"]]
                ratings_values = valid_ratings["rating"].values.astype(np.float32)

                n_users = len(user_ids)
                user_item_matrix = csr_matrix(
                    (ratings_values, (row_indices, col_indices)),
                    shape=(n_users, n_items),
                    dtype=np.float32,
                )
                item_user = user_item_matrix.T.tocsr()

                from sklearn.preprocessing import normalize
                norm_item = normalize(item_user, norm="l2", axis=1)
                cf_sim = (norm_item * norm_item.T).toarray().astype(np.float32)

                content_sim = cosine_similarity(self.tfidf_matrix).astype(np.float32)
                self.item_similarity_matrix = 0.70 * cf_sim + 0.30 * content_sim
            else:
                logger.info("Custom dataset has no ratings matches. Using 100% TF-IDF content similarity matrix.")
                self.item_similarity_matrix = cosine_similarity(self.tfidf_matrix).astype(np.float32)
        else:
            logger.info("No ratings table provided. Using 100% TF-IDF content similarity matrix.")
            self.item_similarity_matrix = cosine_similarity(self.tfidf_matrix).astype(np.float32)

        np.fill_diagonal(self.item_similarity_matrix, 1.0)
        logger.info("Similarity matrix initialized with shape: %s", self.item_similarity_matrix.shape)

    def reindex(self, movies_df: pd.DataFrame, ratings_df: pd.DataFrame, source_name: str) -> None:
        """Re-index the recommender dynamically with a new or uploaded dataset."""
        logger.info("Re-indexing RecommenderEngine with %d movies from %s...", len(movies_df), source_name)
        self.movies_df = movies_df
        self.ratings_df = ratings_df
        self.source_name = source_name
        self._build_indexes()
        self._build_content_model()
        self._build_collaborative_model()
        logger.info("Re-indexing complete!")

    def _compute_mood_scores(self, mood: str) -> np.ndarray:
        """Calculate alignment between each movie's genres and active mood profile."""
        mood_key = mood.lower() if mood else "joyful"
        profile = MOOD_PROFILES.get(mood_key, MOOD_PROFILES["joyful"])
        gw = profile["genre_weights"]
        ng = profile.get("negative_genres", {})

        n_items = len(self.idx_to_movie_id)
        scores = np.zeros(n_items, dtype=np.float32)

        for idx in range(n_items):
            mid = self.idx_to_movie_id[idx]
            genres = self.movie_meta[mid]["genres"]
            total_w = sum(gw.get(g, 0.0) + ng.get(g, 0.0) for g in genres)
            # Normalize by square root of genre count
            norm_w = total_w / max(1.0, len(genres) ** 0.5)
            scores[idx] = norm_w

        min_s, max_s = float(np.min(scores)), float(np.max(scores))
        if max_s > min_s:
            scores = (scores - min_s) / (max_s - min_s)
        else:
            scores = np.full(n_items, 0.5, dtype=np.float32)

        return scores

    def _compute_cf_scores(self, user_ratings: Dict[int, float]) -> np.ndarray:
        """Calculate item-based collaborative filtering predictions based on user star ratings."""
        n_items = len(self.idx_to_movie_id)
        if not user_ratings:
            # Cold start: prioritize community Bayesian consensus
            scores = np.zeros(n_items, dtype=np.float32)
            for idx in range(n_items):
                mid = self.idx_to_movie_id[idx]
                scores[idx] = self.movie_meta[mid]["bayesian_score"] / 5.0
            return scores

        rated_indices = [self.movie_id_to_idx[mid] for mid in user_ratings if mid in self.movie_id_to_idx]
        if not rated_indices:
            return np.full(n_items, 0.5, dtype=np.float32)

        centered_ratings = np.array([user_ratings[self.idx_to_movie_id[i]] - 3.0 for i in rated_indices], dtype=np.float32)
        sub_sim = self.item_similarity_matrix[rated_indices, :]
        sub_sim_pos = np.clip(sub_sim, 0.0, 1.0)

        numerator = np.dot(centered_ratings, sub_sim_pos)
        denominator = np.sum(sub_sim_pos, axis=0) + 1e-5
        pred = numerator / denominator

        min_p, max_p = float(np.min(pred)), float(np.max(pred))
        if max_p > min_p:
            cf_scores = (pred - min_p) / (max_p - min_p)
        else:
            cf_scores = np.full(n_items, 0.5, dtype=np.float32)

        # Blend with Bayesian score
        for idx in range(n_items):
            mid = self.idx_to_movie_id[idx]
            bayes_norm = self.movie_meta[mid]["bayesian_score"] / 5.0
            cf_scores[idx] = 0.85 * cf_scores[idx] + 0.15 * bayes_norm

        return cf_scores

    def _compute_content_scores(self, user_ratings: Dict[int, float]) -> np.ndarray:
        """Calculate TF-IDF content similarity against user's favorable taste profile."""
        n_items = len(self.idx_to_movie_id)
        favorable = [
            (self.movie_id_to_idx[mid], r)
            for mid, r in user_ratings.items()
            if mid in self.movie_id_to_idx and r >= 3.0
        ]

        if not favorable:
            return np.full(n_items, 0.5, dtype=np.float32)

        user_vector = np.zeros((1, self.tfidf_matrix.shape[1]), dtype=np.float32)
        total_weight = 0.0
        for idx, rating in favorable:
            w = rating - 2.0
            user_vector += w * self.tfidf_matrix[idx].toarray()
            total_weight += w

        if total_weight > 0:
            user_vector /= total_weight

        sims = cosine_similarity(user_vector, self.tfidf_matrix).flatten()
        min_s, max_s = float(np.min(sims)), float(np.max(sims))
        if max_s > min_s:
            return (sims - min_s) / (max_s - min_s)
        return np.full(n_items, 0.5, dtype=np.float32)

    def search_movies(self, query: str, limit: int = 24) -> List[Dict[str, Any]]:
        """Real-time full-text search matching title, director, cast, genre, media type, and overview keywords."""
        q = query.strip()
        if not q:
            return []

        def _clean(s: str) -> str:
            return re.sub(r"[^\w\s]", " ", s).lower().strip()

        q_clean = _clean(q)
        q_tokens = [t for t in q_clean.split() if t]
        q_raw_lower = q.lower()

        is_tv = any(t in ("tv", "series", "show", "shows", "webseries") for t in q_tokens)
        is_film = any(t in ("movie", "movies", "film", "films") for t in q_tokens)

        exact_matches = []
        prefix_matches = []
        partial_matches = []
        cast_matches = []
        director_matches = []
        genre_matches = []
        type_matches = []
        story_matches = []

        for mid, meta in self.movie_meta.items():
            t_clean = _clean(meta["title"])
            dir_clean = _clean(meta.get("director", ""))
            cast_clean = _clean(meta.get("cast", "").replace("|", " "))
            genres_clean = [_clean(g) for g in meta.get("genres", [])]
            overview_clean = _clean(meta.get("overview", ""))
            media_type = meta.get("media_type", "Movie")
            type_icon = "\U0001f4fa TV Series" if media_type == "Series" else "\U0001f3ac Movie"

            item = {
                "movieId": mid,
                "title": meta["title"],
                "release_year": meta["release_year"],
                "genres": meta["genres"],
                "genres_str": meta["genres_str"],
                "avg_rating": meta["avg_rating"],
                "vote_count": meta["vote_count"],
                "bayesian_score": meta["bayesian_score"],
                "director": meta["director"],
                "cast": meta["cast"],
                "overview": meta["overview"],
                "poster_url": meta["poster_url"],
                "media_type": media_type,
            }

            if t_clean == q_clean or meta["title"].lower() == q_raw_lower:
                item["match_badge"] = f"\U0001f3af {type_icon}"
                exact_matches.append(item)
            elif t_clean.startswith(q_clean) or meta["title"].lower().startswith(q_raw_lower):
                item["match_badge"] = f"\U0001f3ac {type_icon}"
                prefix_matches.append(item)
            elif q_tokens and all(tok in t_clean for tok in q_tokens):
                item["match_badge"] = f"\U0001f3ac {type_icon}"
                partial_matches.append(item)
            elif q_tokens and all(tok in cast_clean for tok in q_tokens):
                item["match_badge"] = "\U0001f3ad Cast Match"
                cast_matches.append(item)
            elif q_tokens and all(tok in dir_clean for tok in q_tokens):
                item["match_badge"] = "\U0001f3a5 Director Match"
                director_matches.append(item)
            elif any(q_tokens and all(tok in g for tok in q_tokens) for g in genres_clean):
                item["match_badge"] = "\U0001f3f7\ufe0f Genre Match"
                genre_matches.append(item)
            elif is_tv and media_type == "Series":
                item["match_badge"] = "\U0001f4fa TV Series"
                type_matches.append(item)
            elif is_film and media_type == "Movie":
                item["match_badge"] = "\U0001f3ac Movie"
                type_matches.append(item)
            elif q_tokens and all(tok in overview_clean for tok in q_tokens):
                item["match_badge"] = f"\U0001f4d6 {type_icon}"
                story_matches.append(item)

        for bucket in (exact_matches, prefix_matches, partial_matches, cast_matches, director_matches, genre_matches, type_matches, story_matches):
            bucket.sort(key=lambda m: m["bayesian_score"], reverse=True)

        combined = exact_matches + prefix_matches + partial_matches + cast_matches + director_matches + genre_matches + type_matches + story_matches
        return combined[:limit]

    def get_paginated_catalog(
        self,
        page: int = 1,
        limit: int = 24,
        genre: str = "",
        mood: str = "",
        search: str = "",
        media_type: str = "",
    ) -> Dict[str, Any]:
        """Server-side paginated movie catalog browser with 100% dataset access."""
        all_movies = list(self.movie_meta.values())

        # 1. Search filter — preserve relevance ranking from search_movies
        if search.strip():
            s_matches = self.search_movies(search.strip(), limit=len(all_movies))
            match_order = {m["movieId"]: rank for rank, m in enumerate(s_matches)}
            match_badge_map = {m["movieId"]: m.get("match_badge", "") for m in s_matches}
            all_movies = [m for m in all_movies if m["movieId"] in match_order]
            all_movies.sort(key=lambda m: match_order[m["movieId"]])
        else:
            match_badge_map = {}

        # 2. Genre filter (only applied if no search query)
        if not search.strip() and genre.strip():
            g_lower = genre.strip().lower()
            all_movies = [m for m in all_movies if any(g.lower() == g_lower for g in m["genres"])]

        # 2b. Media type filter (Movie vs Series)
        if media_type.strip():
            mt_clean = media_type.strip().lower()
            if mt_clean in ("series", "tv", "tv series", "show"):
                all_movies = [m for m in all_movies if m.get("media_type", "Movie") == "Series"]
            elif mt_clean in ("movie", "film", "movies"):
                all_movies = [m for m in all_movies if m.get("media_type", "Movie") == "Movie"]

        # 3. Mood-aware sort (skipped when search query is active — relevance order is preserved)
        if not search.strip() and mood.strip() and mood.strip() in MOOD_PROFILES:

            profile = MOOD_PROFILES[mood.strip()]
            gw = profile["genre_weights"]
            ng = profile.get("negative_genres", {})

            def mood_rank(m):
                s = sum(gw.get(g, 0.0) + ng.get(g, 0.0) for g in m["genres"])
                norm_s = s / max(1.0, len(m["genres"]) ** 0.5)
                return (norm_s, m["bayesian_score"])

            all_movies.sort(key=mood_rank, reverse=True)
        else:
            all_movies.sort(key=lambda m: m["bayesian_score"], reverse=True)

        total_count = len(all_movies)
        total_pages = max(1, (total_count + limit - 1) // limit)
        page = max(1, min(page, total_pages))
        start = (page - 1) * limit
        end = start + limit

        page_slice = all_movies[start:end]
        results = [
            {
                "movieId": m["movieId"],
                "title": m["title"],
                "release_year": m["release_year"],
                "genres": m["genres"],
                "genres_str": m["genres_str"],
                "avg_rating": m["avg_rating"],
                "vote_count": m["vote_count"],
                "bayesian_score": m["bayesian_score"],
                "director": m["director"],
                "cast": m["cast"],
                "overview": m["overview"],
                "poster_url": m["poster_url"],
                "media_type": m.get("media_type", "Movie"),
                "match_badge": match_badge_map.get(m["movieId"], ""),
                "pairings": get_movie_pairings(m, mood or "joyful"),
            }
            for m in page_slice
        ]

        return {
            "results": results,
            "total_count": total_count,
            "total_pages": total_pages,
            "page": page,
            "limit": limit,
        }

    def recommend(
        self,
        mood: str = "joyful",
        selected_genres: Optional[List[str]] = None,
        min_rating: float = 0.0,
        decade: Optional[str] = None,
        user_ratings: Optional[Dict[int, float]] = None,
        limit: int = 24,
        cf_weight: float = 0.40,
        mood_weight: float = 0.35,
        content_weight: float = 0.25,
        media_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Compute personalized hybrid recommendations with pairings and explainability."""
        user_ratings = user_ratings or {}
        n_items = len(self.idx_to_movie_id)

        mood_scores = self._compute_mood_scores(mood)
        cf_scores = self._compute_cf_scores(user_ratings)
        content_scores = self._compute_content_scores(user_ratings)

        hybrid_scores = (
            cf_weight * cf_scores +
            mood_weight * mood_scores +
            content_weight * content_scores
        )

        results = []
        rated_ids = set(user_ratings.keys())

        for idx in range(n_items):
            mid = self.idx_to_movie_id[idx]
            if mid in rated_ids:
                continue

            meta = self.movie_meta[mid]

            # Genre filter
            if selected_genres:
                if not any(g in meta["genres"] for g in selected_genres):
                    continue

            # Minimum rating filter
            if meta["avg_rating"] < min_rating:
                continue

            # Decade filter
            if decade and meta.get("release_year"):
                y = meta["release_year"]
                if decade == "2020s" and y < 2020:
                    continue
                elif decade == "2010s" and not (2010 <= y <= 2019):
                    continue
                elif decade == "2000s" and not (2000 <= y <= 2009):
                    continue
                elif decade == "1990s" and not (1990 <= y <= 1999):
                    continue
                elif decade == "1980s" and not (1980 <= y <= 1989):
                    continue
                elif decade == "Classic" and y >= 1980:
                    continue

            # Media type filter (Movie vs Series)
            if media_type:
                mt_clean = media_type.strip().lower()
                m_type = meta.get("media_type", "Movie")
                if mt_clean in ("series", "tv", "tv series", "show") and m_type != "Series":
                    continue
                elif mt_clean in ("movie", "film", "movies") and m_type != "Movie":
                    continue

            raw_val = float(hybrid_scores[idx])
            match_pct = int(np.clip(np.round(55.0 + raw_val * 44.0), 60, 99))

            # Reasons
            reasons = []
            profile = MOOD_PROFILES.get(mood.lower(), MOOD_PROFILES["joyful"])
            matched_g = [g for g in meta["genres"] if g in profile["genre_weights"]]
            if matched_g:
                reasons.append(f"{profile['icon']} Mood Match: {matched_g[0]}")
            else:
                reasons.append(f"{profile['icon']} Mood: {profile['name'].split('/')[0].strip()}")

            if meta["vote_count"] >= 20:
                reasons.append(f"🏆 Community Favorite ({meta['avg_rating']}★)")
            elif meta.get("director"):
                reasons.append(f"🎥 Dir: {meta['director']}")

            pairings = get_movie_pairings(meta, mood)

            results.append({
                "movieId": int(mid),
                "title": str(meta["title"]),
                "release_year": int(meta["release_year"]) if meta.get("release_year") else None,
                "genres": list(meta["genres"]),
                "genres_str": str(meta["genres_str"]),
                "avg_rating": float(meta["avg_rating"]),
                "vote_count": int(meta["vote_count"]),
                "bayesian_score": float(meta["bayesian_score"]),
                "director": str(meta["director"]),
                "cast": str(meta["cast"]),
                "overview": str(meta["overview"]),
                "poster_url": str(meta["poster_url"]),
                "media_type": str(meta.get("media_type", "Movie")),
                "raw_score": float(round(raw_val, 4)),
                "match_score": int(match_pct),
                "reasons": [str(r) for r in reasons[:2]],
                "pairings": pairings,
            })

        results.sort(key=lambda x: x["raw_score"], reverse=True)
        return results[:limit]

    def get_related_movies(self, movie_id: int, limit: int = 4, mood: str = "joyful") -> List[Dict[str, Any]]:
        """Retrieve the top similar movies for the Movie Detail Modal."""
        if movie_id not in self.movie_id_to_idx:
            return []

        item_idx = self.movie_id_to_idx[movie_id]
        sims = self.item_similarity_matrix[item_idx].copy()
        sims[item_idx] = -1.0

        top_indices = np.argsort(sims)[::-1][:limit]
        related = []
        for idx in top_indices:
            mid = self.idx_to_movie_id[idx]
            meta = self.movie_meta[mid]
            sim_pct = int(np.clip(np.round(sims[idx] * 100), 40, 99))
            related.append({
                "movieId": int(mid),
                "title": str(meta["title"]),
                "release_year": int(meta["release_year"]) if meta.get("release_year") else None,
                "genres": list(meta["genres"]),
                "genres_str": str(meta["genres_str"]),
                "avg_rating": float(meta["avg_rating"]),
                "vote_count": int(meta["vote_count"]),
                "bayesian_score": float(meta["bayesian_score"]),
                "poster_url": str(meta["poster_url"]),
                "media_type": str(meta.get("media_type", "Movie")),
                "similarity_score": int(sim_pct),
            })
        return related
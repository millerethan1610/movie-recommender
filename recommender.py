"""Simple content-based movie recommendation logic."""

from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TEXT_COLUMNS = ["genres", "keywords", "overview", "cast", "director"]
OPTIONAL_COLUMNS = ["rating", "release_year", "poster_url"]
TEXT_OPTIONAL_COLUMNS = ["industry", "language", "media_type"]


def load_movies(file_path: str) -> pd.DataFrame:
    """Load the CSV and add any optional columns that are missing."""
    movies = pd.read_csv(file_path)

    if "title" not in movies.columns:
        raise ValueError("The CSV file must contain a 'title' column.")

    for column in TEXT_COLUMNS:
        if column not in movies.columns:
            movies[column] = ""

    for column in OPTIONAL_COLUMNS:
        if column not in movies.columns:
            movies[column] = np.nan

    default_text_values = {"industry": "Unknown", "language": "Unknown", "media_type": "Movie"}
    for column in TEXT_OPTIONAL_COLUMNS:
        if column not in movies.columns:
            movies[column] = default_text_values[column]

    movies = movies.drop_duplicates(subset="title").reset_index(drop=True)
    movies["title"] = movies["title"].fillna("").astype(str).str.strip()

    for column in TEXT_COLUMNS:
        movies[column] = movies[column].fillna("").astype(str)

    for column in TEXT_OPTIONAL_COLUMNS:
        movies[column] = (
            movies[column]
            .fillna(default_text_values[column])
            .astype(str)
            .str.strip()
        )

    movies["rating"] = pd.to_numeric(movies["rating"], errors="coerce")
    movies["release_year"] = pd.to_numeric(
        movies["release_year"], errors="coerce"
    )
    movies["combined_text"] = movies[TEXT_COLUMNS].agg(" ".join, axis=1)

    return movies


def build_model(movies: pd.DataFrame) -> tuple[TfidfVectorizer, object]:
    """Convert movie descriptions into TF-IDF vectors."""
    vectorizer = TfidfVectorizer(stop_words="english")
    movie_vectors = vectorizer.fit_transform(movies["combined_text"])
    return vectorizer, movie_vectors


def recommend_movies(
    movies: pd.DataFrame,
    movie_vectors: object,
    selected_titles: Iterable[str],
    number_of_recommendations: int | None = None,
) -> pd.DataFrame:
    """Return every movie with a positive similarity, unless a limit is supplied."""
    selected_titles = list(dict.fromkeys(selected_titles))
    selected_indexes = [
        movies.index[movies["title"] == title][0]
        for title in selected_titles
        if title in set(movies["title"])
    ]

    if not selected_indexes:
        return movies.iloc[0:0].copy()

    selected_vectors = movie_vectors[selected_indexes]
    similarity_scores = cosine_similarity(selected_vectors, movie_vectors).mean(axis=0)

    recommendations = movies.copy()
    recommendations["similarity_score"] = similarity_scores
    recommendations = recommendations.drop(index=selected_indexes, errors="ignore")
    recommendations = recommendations.sort_values(
        by="similarity_score", ascending=False
    )

    recommendations = recommendations[recommendations["similarity_score"] > 0]
    if number_of_recommendations is not None:
        recommendations = recommendations.head(number_of_recommendations)

    return recommendations.reset_index(drop=True)


def format_score(score: float) -> str:
    """Make a similarity score easier to understand in the interface."""
    return f"{score * 100:.0f}% match"
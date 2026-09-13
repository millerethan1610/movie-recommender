"""Streamlit interface for the movie recommendation system."""

import json
import os
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from recommender import build_model, format_score, load_movies, recommend_movies


BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "movies.csv"
STYLE_FILE = BASE_DIR / "assets" / "style.css"

st.set_page_config(
    page_title="CineMatch | Movie Recommendations",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def read_styles() -> None:
    """Load the custom stylesheet if it exists."""
    if STYLE_FILE.exists():
        st.markdown(f"<style>{STYLE_FILE.read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def get_movies():
    return load_movies(str(DATA_FILE))


@st.cache_resource
def get_model(movies):
    return build_model(movies)


@st.cache_data(show_spinner=False)
def get_tmdb_poster(title: str, release_year, language: str) -> str:
    """Find an official TMDB poster when a TMDB API key is configured."""
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        return ""

    query = {"api_key": api_key, "query": title, "include_adult": "false"}
    if not _is_missing(release_year):
        query["year"] = str(int(release_year))
    if language == "Hindi":
        query["language"] = "hi-IN"

    request = Request(
        f"https://api.themoviedb.org/3/search/movie?{urlencode(query)}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.load(response)
    except (OSError, ValueError):
        return ""

    for result in payload.get("results", []):
        poster_path = result.get("poster_path")
        if poster_path:
            return f"https://image.tmdb.org/t/p/w500{poster_path}"
    return ""


def show_movie_card(movie, selected_titles):
    """Display one recommendation and a simple, honest explanation."""
    left, right = st.columns([1, 2.7], gap="medium")
    with left:
        poster_url = str(movie.get("poster_url", ""))
        if not poster_url or poster_url == "nan":
            poster_url = get_tmdb_poster(
                str(movie["title"]), movie.get("release_year"), str(movie.get("language", ""))
            )
        if poster_url and poster_url != "nan":
            st.image(poster_url, use_container_width=True)
        else:
            poster_title = escape(str(movie["title"]))
            poster_genres = escape(str(movie.get("genres", "Film")).replace("|", " / "))
            poster_year = movie.get("release_year")
            poster_year_text = ""
            if not _is_missing(poster_year):
                poster_year_text = str(int(poster_year))
            st.markdown(
                f'<div class="poster-placeholder">'
                f'<span class="poster-kicker">CINEMATCH PRESENTS</span>'
                f'<strong class="poster-title">{poster_title}</strong>'
                f'<span class="poster-genres">{poster_genres}</span>'
                f'<span class="poster-footer">{poster_year_text}  /  FEATURE FILM</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with right:
        rating = movie.get("rating")
        year = movie.get("release_year")
        details = []
        industry = movie.get("industry", "")
        language = movie.get("language", "")
        media_type = movie.get("media_type", "Movie")
        if media_type and media_type != "Unknown":
            details.append(str(media_type))
        if industry and industry != "Unknown":
            details.append(str(industry))
        if language and language != "Unknown":
            details.append(str(language))
        if not _is_missing(rating):
            details.append(f"Rating {float(rating):.1f}/10")
        if not _is_missing(year):
            details.append(str(int(year)))
        detail_text = "  |  ".join(details) or "Details unavailable"
        st.markdown(
            f"<div class='movie-title'><h3>{movie['title']}</h3>"
            f"<span>{format_score(movie['similarity_score'])}</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(detail_text)
        st.markdown(f"**{movie['genres'] or 'Genre unavailable'}**")
        st.write(movie["overview"] or "No description is available for this movie.")

        source_movie = selected_titles[0]
        source_row = st.session_state.movies.loc[
            st.session_state.movies["title"] == source_movie
        ].iloc[0]
        source_genres = source_row["genres"] or "its movie characteristics"
        target_genres = movie["genres"] or "similar characteristics"
        with st.expander("Why this movie?"):
            st.write(
                f"You liked **{source_movie}**, which has {source_genres}. "
                f"This recommendation has {target_genres}. "
                "The score is based on shared words from the movie information "
                "using TF-IDF and cosine similarity."
            )


def _is_missing(value) -> bool:
    return value is None or str(value) in {"", "nan", "NaT"}


def main() -> None:
    read_styles()

    if "show_app" not in st.session_state:
        st.session_state.show_app = False

    st.markdown(
        "<div class='topbar'><div class='brand'>Cine<span>Match</span></div>"
        "<div class='topbar-note'>CONTENT-BASED DISCOVERY</div></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.show_app:
        st.markdown(
            "<section class='hero'><p class='eyebrow'>YOUR NEXT GREAT WATCH</p>"
            "<h1>Find stories that feel<br><em>made for you.</em></h1>"
            "<p class='hero-copy'>Choose movies or series you already love. CineMatch studies their "
            "genres, stories, keywords, cast, and directors to uncover your next watch.</p>"
            "</section>",
            unsafe_allow_html=True,
        )
        if st.button("Get started  →", type="primary"):
            st.session_state.show_app = True
            st.rerun()
        st.markdown(
            "<div class='hero-footer'><span>01  SELECT YOUR FAVOURITES</span>"
            "<span>02  GET A PERSONAL SHORTLIST</span><span>03  DISCOVER SOMETHING NEW</span></div>",
            unsafe_allow_html=True,
        )
        return

    try:
        movies = get_movies()
        # Keep cached data from older app versions compatible with new filters.
        for column, default in {
            "industry": "Unknown",
            "language": "Unknown",
            "media_type": "Movie",
        }.items():
            if column not in movies.columns:
                movies[column] = default
        vectorizer, movie_vectors = get_model(movies)
        st.session_state.movies = movies
    except FileNotFoundError:
        st.error("I could not find data/movies.csv. Add your CSV file there and refresh the page.")
        return
    except (ValueError, pd.errors.ParserError) as error:
        st.error(f"The movie dataset needs attention: {error}")
        return

    st.markdown("<p class='eyebrow'>PERSONALIZED DISCOVERY</p><h1 class='page-title'>Pick your favourites</h1>", unsafe_allow_html=True)
    st.write("Select one or more movies. The more you choose, the more tailored your shortlist becomes.")

    with st.form("recommendation_form"):
        selected_titles = st.multiselect(
            "Movies or series you like",
            options=movies["title"].tolist(),
            placeholder="Search titles such as Interstellar or Breaking Bad...",
        )
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            media_type_options = sorted(
                value for value in movies["media_type"].dropna().unique() if value != "Unknown"
            )
            selected_media_type = st.selectbox("Type", ["All types"] + media_type_options)
        with filter_col2:
            industry_options = sorted(
                value for value in movies["industry"].dropna().unique() if value != "Unknown"
            )
            selected_industry = st.selectbox("Industry", ["All industries"] + industry_options)
        with filter_col3:
            language_options = sorted(
                value for value in movies["language"].dropna().unique() if value != "Unknown"
            )
            selected_language = st.selectbox("Language", ["All languages"] + language_options)

        filter_col4, filter_col5, filter_col6 = st.columns(3)
        with filter_col4:
            genre_options = sorted(
                {genre.strip() for values in movies["genres"] for genre in values.split("|") if genre.strip()}
            )
            selected_genre = st.selectbox("Genre", ["Any genre"] + genre_options)
        with filter_col5:
            minimum_rating = st.slider("Minimum rating", 0.0, 10.0, 0.0, 0.5)
        with filter_col6:
            years = movies["release_year"].dropna()
            year_range = st.slider(
                "Release year",
                int(years.min()),
                int(years.max()),
                (int(years.min()), int(years.max())),
            )
        submitted = st.form_submit_button("Recommend titles  →", type="primary", use_container_width=True)

    if not submitted:
        st.info("Choose some favourites above, then press Recommend movies.")
        return
    if not selected_titles:
        st.warning("Please select at least one movie so I know what you enjoy.")
        return

    results = recommend_movies(
        movies, movie_vectors, selected_titles, number_of_recommendations=None
    )
    if selected_media_type != "All types":
        results = results[results["media_type"] == selected_media_type]
    if selected_industry != "All industries":
        results = results[results["industry"] == selected_industry]
    if selected_language != "All languages":
        results = results[results["language"] == selected_language]
    if selected_genre != "Any genre":
        results = results[results["genres"].str.contains(selected_genre, case=False, na=False)]
    results = results[results["rating"].fillna(0) >= minimum_rating]
    results = results[results["release_year"].fillna(0).between(year_range[0], year_range[1])]

    st.markdown(f"<div class='results-heading'><h2>Your watchlist, refined</h2><span>{len(results)} matches</span></div>", unsafe_allow_html=True)
    if results.empty:
        st.warning("No movies match these filters. Try a wider rating, year, or genre filter.")
        return
    for _, movie in results.iterrows():
        show_movie_card(movie, selected_titles)
        st.divider()


if __name__ == "__main__":
    main()
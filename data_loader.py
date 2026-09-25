"""data_loader.py — Dynamic Excel & CSV Data Ingestion Engine for CineMood & Bites.

Features:
- Automatic file detection (.xlsx, .xls, .csv) across project root and `./data/` directories.
- Flexible column normalization matching variant column names (Title, Genre, Rating, Overview, etc.).
- Robust 4-digit release year extraction and title sanitization.
- Support for on-the-fly uploaded custom datasets with zero server restart.
- 100% row preservation with Bayesian rating estimation.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CineMood.DataLoader")

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"

# Common column name aliases for flexible normalization
COLUMN_ALIASES: Dict[str, List[str]] = {
    "title": [
        "title", "movie_title", "movie", "name", "film_title", "film",
        "Title", "Movie_Title", "Movie", "Name"
    ],
    "genres": [
        "genres", "genre", "category", "categories", "genre_list",
        "Genres", "Genre", "Category", "Categories"
    ],
    "rating": [
        "rating", "vote_average", "imdb_score", "score", "ratings", "avg_rating",
        "Rating", "Vote_Average", "IMDB_Score", "Score", "user_rating"
    ],
    "vote_count": [
        "vote_count", "votes", "num_votes", "rating_count", "ratings_count",
        "Vote_Count", "Votes", "Reviews", "review_count"
    ],
    "overview": [
        "overview", "description", "summary", "plot", "synopsis", "story",
        "Overview", "Description", "Summary", "Plot", "Synopsis"
    ],
    "director": [
        "director", "directors", "directed_by", "filmmaker",
        "Director", "Directors", "Directed_By"
    ],
    "cast": [
        "cast", "actors", "stars", "starring", "lead_actors",
        "Cast", "Actors", "Stars", "Starring"
    ],
    "release_year": [
        "release_year", "year", "release_date", "date", "premiered",
        "Release_Year", "Year", "Release_Date", "Date"
    ],
    "poster_url": [
        "poster_url", "poster", "image_url", "poster_path", "img", "image",
        "Poster_Url", "Poster", "Image_Url", "Poster_Path"
    ],
    "movie_id": [
        "movieid", "movie_id", "id", "mid", "film_id",
        "movieId", "MovieId", "Movie_Id", "ID", "Id"
    ],
    "media_type": [
        "media_type", "type", "content_type", "format", "series_or_movie",
        "Media_Type", "Type", "Content_Type"
    ],
}



def load_env() -> None:
    """Load key-value pairs from .env into os.environ if present."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception as e:
            logger.debug("Failed reading .env: %s", e)


def discover_dataset_file(custom_path: Optional[str] = None) -> Optional[Path]:
    """Auto-detect the best candidate Excel or CSV dataset file.
    
    Priority order:
    1. Explicit custom path passed by user.
    2. Excel files (.xlsx, .xls) in project root or ./data/ (e.g., movies.xlsx, dataset.xlsx).
    3. CSV files in project root or ./data/ (e.g., movies.csv, dataset.csv).
    4. Cached MovieLens movies.csv inside ./data/ml-latest-small/.
    """
    if custom_path:
        p = Path(custom_path)
        if p.exists() and p.is_file():
            return p

    search_dirs = [PROJECT_ROOT, DATA_DIR]

    # 1. Search for Excel files first
    for sdir in search_dirs:
        if sdir.exists():
            for ext in ("*.xlsx", "*.xls"):
                for f in sdir.glob(ext):
                    if not f.name.startswith("~$") and f.is_file():
                        logger.info("Found Excel dataset: %s", f)
                        return f

    # 2. Search for CSV files in root and data/
    for sdir in search_dirs:
        if sdir.exists():
            for f in sdir.glob("*.csv"):
                if f.is_file() and not f.name.startswith("ratings"):
                    logger.info("Found CSV dataset: %s", f)
                    return f

    # 3. Check ml-latest-small
    ml_movies = DATA_DIR / "ml-latest-small" / "movies.csv"
    if ml_movies.exists():
        logger.info("Found MovieLens dataset: %s", ml_movies)
        return ml_movies

    return None


def extract_year_and_clean_title(raw_title: str) -> Tuple[str, Optional[int]]:
    """Clean MovieLens / Excel titles and extract 4-digit release year.
    
    Examples:
    - 'Toy Story (1995)' -> ('Toy Story', 1995)
    - 'Dark Knight, The (2008)' -> ('The Dark Knight', 2008)
    - 'Inception' -> ('Inception', None)
    """
    if not isinstance(raw_title, str) or not raw_title.strip():
        return "Featured Film", None

    clean = raw_title.strip()
    year: Optional[int] = None

    # Match year in parentheses at end of title: 'Title (1999)'
    m = re.search(r"^(.*?)\s*(?:\((\d{4})\))?$", clean)
    if m:
        t_part = m.group(1).strip()
        y_part = m.group(2)
        if y_part and y_part.isdigit():
            year = int(y_part)
        clean = t_part

    # Handle MovieLens inverted articles: 'Matrix, The' -> 'The Matrix'
    for article in (", The", ", A", ", An", ", Il", ", Le", ", La", ", Der", ", Das", ", Die"):
        if clean.endswith(article):
            prefix = article.replace(",", "").strip() + " "
            clean = prefix + clean[: -len(article)].strip()
            break

    return clean if clean else raw_title.strip(), year


def normalize_genres(raw_genres: Any) -> List[str]:
    """Convert various genre notations into a sorted list of clean genre names."""
    if pd.isna(raw_genres):
        return ["Cinema"]

    genres_str = str(raw_genres).strip()
    if not genres_str or genres_str in ("(no genres listed)", "None", "nan", ""):
        return ["Cinema"]

    # Split by pipe, comma, semicolon, or slash
    parts = re.split(r"[|,;/]", genres_str)
    result = []
    for p in parts:
        cleaned = p.strip()
        if cleaned and cleaned.lower() not in ("(no genres listed)", "none", "nan"):
            # Capitalize each word properly
            cap = " ".join(w.capitalize() for w in cleaned.split())
            if cap not in result:
                result.append(cap)

    return result if result else ["Cinema"]


def find_matching_column(df_columns: List[str], target_field: str) -> Optional[str]:
    """Match a DataFrame column using flexible alias dictionary."""
    aliases = COLUMN_ALIASES.get(target_field, [])
    # 1. Exact match (case insensitive)
    cols_lower = {c.lower(): c for c in df_columns}
    for alias in aliases:
        if alias.lower() in cols_lower:
            return cols_lower[alias.lower()]

    # 2. Substring match
    for col in df_columns:
        col_l = col.lower()
        for alias in aliases:
            if alias.lower() in col_l:
                return col

    return None


def read_file_to_dataframe(file_path: Path) -> pd.DataFrame:
    """Read Excel (.xlsx, .xls) or CSV into a pandas DataFrame."""
    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        logger.info("Reading Excel spreadsheet: %s", file_path)
        try:
            return pd.read_excel(file_path, engine="openpyxl")
        except Exception:
            return pd.read_excel(file_path)
    else:
        logger.info("Reading CSV dataset: %s", file_path)
        try:
            return pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding="latin1")


def normalize_movies_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize arbitrary DataFrame columns to CineMood standard schema.
    
    Standard Schema:
    - movieId (int)
    - title (clean string)
    - raw_title (original string)
    - release_year (int or None)
    - genres (list of str)
    - genres_str (pipe-joined str)
    - avg_rating (float)
    - vote_count (int)
    - bayesian_score (float)
    - director (str)
    - cast (str)
    - overview (str)
    - poster_url (str)
    """
    cols = list(df_raw.columns)
    col_map = {
        field: find_matching_column(cols, field)
        for field in (
            "title", "genres", "rating", "vote_count", "overview",
            "director", "cast", "release_year", "poster_url", "movie_id", "media_type"
        )
    }


    records: List[Dict[str, Any]] = []
    total_rows = len(df_raw)

    for idx, row in df_raw.iterrows():
        # Title
        raw_title = ""
        if col_map["title"] and pd.notna(row[col_map["title"]]):
            raw_title = str(row[col_map["title"]]).strip()
        elif col_map["movie_id"] and pd.notna(row[col_map["movie_id"]]):
            raw_title = f"Film #{row[col_map['movie_id']]}"
        else:
            raw_title = f"Film #{idx + 1}"

        clean_title, extracted_year = extract_year_and_clean_title(raw_title)

        # Release Year
        year = extracted_year
        if col_map["release_year"] and pd.notna(row[col_map["release_year"]]):
            try:
                y_val = str(row[col_map["release_year"]]).strip()
                ym = re.search(r"\b(19\d{2}|20\d{2})\b", y_val)
                if ym:
                    year = int(ym.group(1))
            except Exception:
                pass

        # Movie ID
        mid = idx + 1
        if col_map["movie_id"] and pd.notna(row[col_map["movie_id"]]):
            try:
                mid = int(row[col_map["movie_id"]])
            except ValueError:
                mid = idx + 1

        # Genres
        raw_g = row[col_map["genres"]] if col_map["genres"] and pd.notna(row[col_map["genres"]]) else ""
        genres_list = normalize_genres(raw_g)

        # Rating / Vote Count
        avg_rating = 3.5
        if col_map["rating"] and pd.notna(row[col_map["rating"]]):
            try:
                val = float(row[col_map["rating"]])
                # Normalize 0-10 or 0-100 scales to 1.0 - 5.0 scale
                if val > 10.0:
                    val = val / 20.0
                elif val > 5.0:
                    val = val / 2.0
                avg_rating = round(float(np.clip(val, 0.5, 5.0)), 2)
            except Exception:
                avg_rating = 3.5

        vote_count = 0
        if col_map["vote_count"] and pd.notna(row[col_map["vote_count"]]):
            try:
                vote_count = max(0, int(float(row[col_map["vote_count"]])))
            except Exception:
                vote_count = 0

        # Overview
        overview = ""
        if col_map["overview"] and pd.notna(row[col_map["overview"]]):
            overview = str(row[col_map["overview"]]).strip()

        # Director & Cast
        director = ""
        if col_map["director"] and pd.notna(row[col_map["director"]]):
            director = str(row[col_map["director"]]).strip()

        cast = ""
        if col_map["cast"] and pd.notna(row[col_map["cast"]]):
            cast = str(row[col_map["cast"]]).strip()

        # Poster URL (if provided directly in dataset)
        poster_url = ""
        if col_map["poster_url"] and pd.notna(row[col_map["poster_url"]]):
            p_val = str(row[col_map["poster_url"]]).strip()
            if p_val.startswith("http://") or p_val.startswith("https://"):
                poster_url = p_val

        # Media Type (Movie vs Series / TV Show)
        media_type = "Movie"
        if col_map.get("media_type") and pd.notna(row[col_map["media_type"]]):
            m_val = str(row[col_map["media_type"]]).strip()
            if m_val.lower() in ("series", "tv", "tv series", "show", "tv show"):
                media_type = "Series"
            elif m_val.lower() in ("movie", "film"):
                media_type = "Movie"
            elif m_val:
                media_type = m_val.capitalize()

        records.append({
            "movieId": mid,
            "title": clean_title,
            "raw_title": raw_title,
            "release_year": year,
            "genres": genres_list,
            "genres_str": " | ".join(genres_list),
            "avg_rating": avg_rating,
            "vote_count": vote_count,
            "director": director,
            "cast": cast,
            "overview": overview,
            "poster_url": poster_url,
            "media_type": media_type,
        })


    normalized_df = pd.DataFrame(records)

    # Compute Bayesian weighted score: WR = (v / (v + m)) * R + (m / (v + m)) * C
    # C = global mean rating, m = minimum votes threshold
    C = float(normalized_df["avg_rating"].mean()) if not normalized_df.empty else 3.5
    m = 10
    v = normalized_df["vote_count"].values
    R = normalized_df["avg_rating"].values
    bayes = (v / (v + m)) * R + (m / (v + m)) * C
    normalized_df["bayesian_score"] = np.round(bayes, 2)

    logger.info("Successfully normalized %d rows (100%% preserved).", len(normalized_df))
    return normalized_df


def load_dataset(file_path: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Load, normalize, and return the complete dataset with ratings.
    
    Returns:
    - movies_df: Normalized 100% movie catalog
    - ratings_df: User ratings DataFrame (from ratings.csv if present, else synthesized)
    - source_name: Human-readable source description
    """
    load_env()
    dataset_file = discover_dataset_file(file_path)

    if dataset_file is None:
        raise FileNotFoundError(
            "No movie dataset found! Place a movies.xlsx or movies.csv in the project folder."
        )

    raw_df = read_file_to_dataframe(dataset_file)
    movies_df = normalize_movies_dataframe(raw_df)

    # Attempt to load ratings.csv if available in same directory
    ratings_df = pd.DataFrame(columns=["userId", "movieId", "rating", "timestamp"])
    possible_ratings = [
        dataset_file.parent / "ratings.csv",
        DATA_DIR / "ml-latest-small" / "ratings.csv",
        PROJECT_ROOT / "ratings.csv",
    ]
    for rpath in possible_ratings:
        if rpath.exists():
            try:
                ratings_df = pd.read_csv(rpath)
                logger.info("Loaded %d ratings from %s", len(ratings_df), rpath.name)
                break
            except Exception as e:
                logger.debug("Failed reading ratings from %s: %s", rpath, e)

    source_desc = f"{dataset_file.name} ({len(movies_df):,} movies)"
    return movies_df, ratings_df, source_desc

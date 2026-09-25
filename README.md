# 🎬 CineMatch AI — Adaptive Mood-Based Movie Recommendation System

A production-ready, full-stack Movie Recommendation System powered by **FastAPI**, **Item-Based Collaborative Filtering (IBCF)**, **TF-IDF Content-Based Filtering**, and **Dynamic Mood & Tone Alignment**, featuring real-time client-side theme transitions.

---

## 🌟 Key Features

1. **Hybrid Recommendation Engine**:
   - **Item-Based Collaborative Filtering (IBCF)**: Computes cosine similarities over a sparse user-item interaction matrix ($9,742 \times 9,742$).
   - **Content-Based Filtering (CBF)**: TF-IDF vectorizer ($6,000$ features, 1–2 n-grams) on movie genres, titles, and metadata tags.
   - **Hybrid Mood & Preference Scorer**: Maps 5 distinct emotional states to genre weightings and penalties with dynamic linear combination.
   - **Cold-Start Handling**: Seamless Bayesian weighted rating fallback ($\frac{v}{v+m}R + \frac{m}{v+m}C$) ensuring relevant recommendations for brand-new users.

2. **5 Dynamic Mood-Driven Themes**:
   - ☀️ **Joyful**: Warm golden amber highlights, energetic light-glow dark mode.
   - 🌧️ **Melancholy**: Deep slate blue, indigo, muted ambient accents.
   - ⚡ **Dark / Thrilling**: Crimson red, stark noir, high-contrast dark aesthetic.
   - 🚀 **Adventurous**: Electric emerald green, teal accents, neon highlights.
   - ☕ **Cozy / Relaxed**: Soft pastel purple, lavender, warm ambient lighting.
   - Real-time client-side transitions adjusting root CSS variables with smooth $0.5\text{s}$ cubic-bezier curves.

3. **Interactive User Engagement**:
   - **Live Star Ratings**: Click 1–5 stars directly on movie cards or in search results to instantly retrain the sparse interaction vector.
   - **Explainability Badges**: Transparent reason tags (e.g., `⚡ Thrilling Mood Match`, `⭐ Because you liked Inception`, `🏆 High Community Consensus`).
   - **Filter & Fine-Tune Controls**: Genre multi-select chips, minimum rating slider, release decade filter, and an **Algorithm Blend slider** (Taste-dominant vs. Mood-dominant).
   - **Watchlist Bookmarks & Ratings Drawer**: Slide-over drawer to view, adjust, or reset session ratings.

4. **Automated Data Pipeline & Offline Fallback**:
   - Automatically downloads and unpacks the MovieLens `ml-latest-small` dataset on first run.
   - Includes an instant bundled fallback dataset with 400+ curated movies and synthetic interaction ratings for 100% offline reliability.

5. **Offline Evaluation Module**:
   - Built-in diagnostics computing **Precision@10**, **Recall@10**, **Catalog Coverage**, and **Matrix Sparsity** on an 80/20 train/test split.

---

## 🏗️ File Structure

```text
├── app.py              # FastAPI endpoints, static file mounting, session lifecycle
├── recommender.py      # IBCF, TF-IDF vectorization, hybrid mood scoring, evaluation
├── data_loader.py      # MovieLens download, caching, fallback generator, preprocessing
├── session_db.py       # SQLite persistence for user star ratings & favorites
├── requirements.txt    # Production Python dependencies
├── README.md           # Setup, architecture & API guide
├── static/
│   ├── index.html      # Responsive Single Page Application dashboard
│   ├── styles.css      # CSS variable-driven theme engine with smooth transitions
│   └── app.js          # State handling, instant theme switching, live recalculation
├── data/
│   ├── movies.csv      # Bundled fallback movie catalog
│   ├── ratings.csv     # Bundled fallback ratings
│   └── ml-latest-small/# Cached MovieLens dataset (auto-downloaded)
└── tests/
    └── test_system.py  # Comprehensive test suite covering ML, API, and storage
```

---

## 🚀 Quickstart & Run Instructions

### 1. Prerequisites
- Python 3.10+ (tested up to Python 3.14)
- `pip` package manager

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5001
```
*(Or `http://localhost:5001`)*

The server automatically downloads and caches MovieLens on first launch and displays the interactive dashboard immediately.

---

## 🧪 Running Automated Tests

Run the automated test suite covering data ingestion, IBCF, mood scoring, offline evaluation, SQLite storage, and REST endpoints:

```bash
python tests/test_system.py
```

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the Single Page Application UI |
| `GET` | `/api/health` | Service health status and catalog counts |
| `GET` | `/api/moods` | Metadata and color themes for all 5 moods |
| `GET` | `/api/genres` | List of all unique genres across the catalog |
| `GET` | `/api/movies?q={query}` | Instant catalog search with title and genre matching |
| `POST` | `/api/recommend` | Computes personalized hybrid recommendations |
| `POST` | `/api/rate` | Saves a user star rating (1.0 to 5.0) in SQLite |
| `GET` | `/api/ratings?session_id={id}` | Retrieves all rated movies for a session |
| `DELETE` | `/api/ratings/{movieId}` | Removes a specific rating |
| `POST` | `/api/ratings/clear` | Resets all user ratings for the session |
| `POST` | `/api/favorite` | Toggles watchlist bookmark for a movie |
| `GET` | `/api/favorites` | Retrieves watchlisted movies |
| `GET` | `/api/metrics` | Returns Precision@10, Recall@10, Coverage, and Sparsity |

---

## 📐 Mathematical Formulation

### 1. Item-Based Collaborative Filtering (IBCF)
Cosine similarity between normalized rating column vectors $u_i$ and $u_j$:
$$\text{Sim}(i, j) = \frac{u_i \cdot u_j}{\|u_i\|_2 \|u_j\|_2}$$

Predicted rating for an unrated candidate movie $j$ given user ratings $\{i: r_i\}$ centered around neutral rating $2.5$:
$$\hat{r}_j = \frac{\sum_{i \in \text{Rated}} \max(0, \text{Sim}(i, j)) \cdot (r_i - 2.5)}{\sum_{i \in \text{Rated}} |\max(0, \text{Sim}(i, j))| + \epsilon}$$

### 2. Bayesian IMDB Cold-Start Consensus
$$WR = \left(\frac{v}{v+m}\right) R + \left(\frac{m}{v+m}\right) C$$
- $v$: number of user votes for the movie
- $m$: minimum vote threshold (10th percentile)
- $R$: average rating for the movie
- $C$: mean rating across the entire catalog

### 3. Mood Genre Alignment
For candidate item $j$ with genre set $G_j$, mood weights $W$, and penalty weights $P$:
$$S_{\text{mood}}(j) = \frac{\sum_{g \in G_j} W(g) + P(g)}{\max(1, \sqrt{|G_j|})}$$

### 4. Hybrid Linear Combination
$$Score_{\text{final}}(j) = w_{\text{cf}} \cdot Score_{\text{CF}}(j) + w_{\text{mood}} \cdot S_{\text{mood}}(j) + w_{\text{content}} \cdot Score_{\text{Content}}(j)$$
Mapped to an intuitive **60%–99% Match Score** displayed on each movie card.

import urllib.request
import json
import sys

def test(name, fn):
    try:
        fn()
        print(f"PASS: {name}")
    except Exception as e:
        import traceback
        print(f"FAIL: {name} -> {e}")
        traceback.print_exc()
        sys.exit(1)

def test_html():
    with urllib.request.urlopen("http://127.0.0.1:8000/") as r:
        html = r.read().decode("utf-8")
        assert "Browse All 9,742 Films" in html, "Missing Browse All tab"
        assert "movieGrid" in html, "Missing movieGrid"
        assert "catalogLoadMore" in html, "Missing catalogLoadMore"
        assert "movieDetailModalBackdrop" in html, "Missing detail modal"

def test_catalog_pagination():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/movies?page=1&limit=24") as r:
        d = json.loads(r.read())
        assert d["total_count"] == 9742, f"Expected 9742 movies, got {d['total_count']}"
        assert len(d["results"]) == 24, f"Expected 24 items on page 1, got {len(d['results'])}"
        assert d["page"] == 1, "Expected page=1"
        assert d["total_pages"] == 406, f"Expected 406 pages, got {d['total_pages']}"

    with urllib.request.urlopen("http://127.0.0.1:8000/api/movies?page=2&limit=24") as r:
        d2 = json.loads(r.read())
        assert d2["page"] == 2, "Expected page=2"
        assert len(d2["results"]) == 24, "Expected 24 items on page 2"
        ids1 = {m["movieId"] for m in d["results"]}
        ids2 = {m["movieId"] for m in d2["results"]}
        assert not (ids1 & ids2), "Page 1 and Page 2 overlap!"

def test_genre_filter():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/movies?page=1&limit=10&genre=Sci-Fi") as r:
        d = json.loads(r.read())
        assert d["total_count"] > 0, "No Sci-Fi movies found"
        for m in d["results"]:
            assert "Sci-Fi" in m["genres"], f"Movie {m['title']} missing Sci-Fi genre"

def test_search():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/movies?q=Interstellar") as r:
        d = json.loads(r.read())
        results = d["results"]
        assert any("Interstellar" in m["title"] for m in results), "Interstellar not in search results"

def test_movie_detail():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/movies/1?mood=joyful") as r:
        d = json.loads(r.read())
        assert "movie" in d and "related_movies" in d, "Missing movie or related_movies"
        assert d["movie"]["movieId"] == 1
        assert "pairings" in d["movie"]
        assert "food" in d["movie"]["pairings"]
        assert "drink" in d["movie"]["pairings"]
        assert len(d["related_movies"]) == 4, "Expected 4 related movies"

def test_poster_api():
    with urllib.request.urlopen("http://127.0.0.1:8000/api/poster/1/url?mood=joyful") as r:
        d = json.loads(r.read())
        assert "poster_url" in d
        assert d["poster_url"].startswith("http") or d["poster_url"].startswith("/api/poster/"), f"Invalid poster URL: {d['poster_url']}"

def test_recommend():
    payload = json.dumps({"session_id": "test_sess", "mood": "thrilling", "limit": 24}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/recommend", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
        assert "results" in d, "Missing results in recommendation response"
        assert len(d["results"]) == 24, f"Expected 24 recommendations, got {len(d['results'])}"
        assert "pairings" in d["results"][0], "Missing pairings in recommendations"

if __name__ == "__main__":
    print("--- Running CineMood & Bites Test Suite ---")
    test("HTML structure & UI tabs", test_html)
    test("Catalog pagination (9,742 movies, 406 pages)", test_catalog_pagination)
    test("Catalog genre filter", test_genre_filter)
    test("Full-text search", test_search)
    test("Movie details & pairings & 4 related films", test_movie_detail)
    test("Dynamic TMDB/SVG poster resolution", test_poster_api)
    test("Personalized hybrid recommendations (24 films)", test_recommend)
    print("--- ALL 7 TESTS PASSED SUCCESSFULLY! ---")

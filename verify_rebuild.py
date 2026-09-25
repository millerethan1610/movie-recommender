import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://127.0.0.1:5001"

def run_test(name, func):
    try:
        func()
        print(f"PASS: {name}")
    except Exception as e:
        import traceback
        print(f"FAIL: {name} -> {e}")
        traceback.print_exc()
        sys.exit(1)

def test_health():
    with urllib.request.urlopen(f"{BASE_URL}/api/health") as r:
        d = json.loads(r.read())
        assert d["status"] == "healthy"
        assert d["engine_ready"] is True
        assert d["movies_loaded"] > 0
        print(f"   [Health] Source: {d['source']}, Movies Loaded: {d['movies_loaded']}")

def test_movies_catalog():
    with urllib.request.urlopen(f"{BASE_URL}/api/movies?page=1&limit=24") as r:
        d = json.loads(r.read())
        assert "results" in d
        assert len(d["results"]) > 0
        assert d["total_count"] > 0
        assert "pairings" in d["results"][0]
        assert "spotify" in d["results"][0]["pairings"]
        print(f"   [Catalog] Total Count: {d['total_count']}, Sample Title: {d['results'][0]['title']}")

def test_search():
    with urllib.request.urlopen(f"{BASE_URL}/api/movies?q=Inception") as r:
        d = json.loads(r.read())
        results = d["results"]
        assert len(results) > 0
        assert any("Inception" in m["title"] for m in results)
        print(f"   [Search] Inception matched {len(results)} titles.")

def test_poster_endpoint():
    with urllib.request.urlopen(f"{BASE_URL}/api/poster/1/url?mood=joyful") as r:
        d = json.loads(r.read())
        assert "poster_url" in d
        assert "source" in d
        print(f"   [Poster URL] Source: {d['source']}, URL: {d['poster_url'][:75]}...")

    with urllib.request.urlopen(f"{BASE_URL}/api/poster/1?mood=joyful") as r:
        svg_content = r.read().decode("utf-8")
        assert "<svg" in svg_content
        assert "</svg>" in svg_content
        assert "CINEMOOD &amp; BITES" in svg_content or "CINEMOOD" in svg_content
        print(f"   [Dynamic SVG] Valid SVG graphic generated ({len(svg_content):,} bytes).")

def test_recommendation_and_spotify():
    payload = json.dumps({"mood": "thrilling", "limit": 12}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/recommend",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
        assert "results" in d
        assert len(d["results"]) > 0
        first = d["results"][0]
        assert "pairings" in first
        assert "spotify" in first["pairings"]
        assert "embed_url" in first["pairings"]["spotify"]
        print(f"   [Recommend] Mood: {d['mood']}, Recs: {len(d['results'])}, Top: {first['title']} ({first['match_score']}%)")

def test_auth_and_persistence():
    import random
    test_user = f"tester_{random.randint(1000, 9999)}"
    test_pass = "secret1234"

    # Register
    reg_payload = json.dumps({"username": test_user, "password": test_pass, "display_name": "Test Cinephile"}).encode("utf-8")
    req_reg = urllib.request.Request(f"{BASE_URL}/api/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_reg) as r:
        d = json.loads(r.read())
        assert d["success"] is True
        token = d["user"]["token"]
        user_id = d["user"]["id"]
        print(f"   [Auth] Registered user '{test_user}' (id={user_id}).")

    # Login
    log_payload = json.dumps({"username": test_user, "password": test_pass}).encode("utf-8")
    req_log = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=log_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_log) as r:
        d_log = json.loads(r.read())
        assert d_log["success"] is True
        assert d_log["user"]["token"] is not None

    # Me
    req_me = urllib.request.Request(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req_me) as r:
        d_me = json.loads(r.read())
        assert d_me["username"] == test_user

    # Rating persistence
    rate_payload = json.dumps({"movie_id": 1, "rating": 5.0}).encode("utf-8")
    req_rate = urllib.request.Request(
        f"{BASE_URL}/api/rate",
        data=rate_payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_rate) as r:
        d_rate = json.loads(r.read())
        assert d_rate["success"] is True

    # Watchlist toggle persistence
    watch_payload = json.dumps({"movie_id": 1}).encode("utf-8")
    req_watch = urllib.request.Request(
        f"{BASE_URL}/api/watchlist/toggle",
        data=watch_payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_watch) as r:
        d_watch = json.loads(r.read())
        assert d_watch["success"] is True
        assert d_watch["is_in_watchlist"] is True

    # Get Watchlist
    req_get_watch = urllib.request.Request(f"{BASE_URL}/api/watchlist", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req_get_watch) as r:
        d_gw = json.loads(r.read())
        assert len(d_gw["results"]) == 1
        assert d_gw["results"][0]["movieId"] == 1
        print(f"   [Watchlist & Ratings] Verified persistence in SQLite for user '{test_user}'.")

def test_dynamic_upload_reindex():
    # Test uploading a new CSV on-the-fly and verifying instant re-indexing
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    csv_content = (
        "movieId,title,genres,rating,vote_count,director\n"
        "10001,Blade Runner 2049,Sci-Fi|Drama,4.6,850,Denis Villeneuve\n"
        "10002,Dune: Part Two,Sci-Fi|Adventure,4.8,920,Denis Villeneuve\n"
        "10003,Grand Budapest Hotel,Comedy|Drama,4.5,780,Wes Anderson\n"
    )

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="custom_test_movies.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/api/upload-dataset",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
        assert d["success"] is True
        assert d["movies_count"] == 3
        print(f"   [Upload] Dynamically re-indexed system to 3 custom movies: {d['message']}")

    # Verify catalog immediately reflects new uploaded movies without server restart
    with urllib.request.urlopen(f"{BASE_URL}/api/movies?page=1&limit=10") as r:
        d_cat = json.loads(r.read())
        assert d_cat["total_count"] == 3
        assert d_cat["results"][0]["title"] in ["Dune: Part Two", "Blade Runner 2049"]
        print(f"   [Dynamic Catalog Verification] Catalog now serves newly uploaded 3 movies live!")

    # Restore default full dataset (movies.csv / movies.xlsx)
    ml_path = r"c:\Users\mille\OneDrive\Desktop\Ethan\movie-recommender\data\ml-latest-small\movies.csv"
    with open(ml_path, "rb") as f:
        file_bytes = f.read()

    body_restore = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="movies.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req_restore = urllib.request.Request(
        f"{BASE_URL}/api/upload-dataset",
        data=body_restore,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req_restore) as r:
        d_res = json.loads(r.read())
        assert d_res["success"] is True
        print(f"   [Restore] Restored full dataset: {d_res['movies_count']} movies live!")

if __name__ == "__main__":
    print("======================================================")
    print(" CineMood & Bites Complete Dynamic Test Suite")
    print("======================================================")
    run_test("System Health & Dynamic File Discovery", test_health)
    run_test("Movies Catalog & Server-Side Pagination", test_movies_catalog)
    run_test("Live Debounced Search (Inception)", test_search)
    run_test("100% Visible Poster Pipeline (TMDB + Dynamic SVG)", test_poster_endpoint)
    run_test("Personalized Recommendations & Spotify Soundtracks", test_recommendation_and_spotify)
    run_test("Mood-Aligned SQLite Auth, Ratings & Watchlist Persistence", test_auth_and_persistence)
    run_test("Dynamic Excel/CSV Upload & Instant Re-Indexing", test_dynamic_upload_reindex)
    print("======================================================")
    print(" ALL 7 END-TO-END TESTS PASSED WITH 100% SUCCESS!")
    print("======================================================")

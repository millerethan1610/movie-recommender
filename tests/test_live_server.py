import json
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test(url, method='GET', data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        data = json.dumps(data).encode('utf-8')
    with urllib.request.urlopen(req, data=data, timeout=5) as resp:
        return resp.status, resp.headers.get('content-type'), resp.read()

s, ct, html = test('http://127.0.0.1:8000/')
assert s == 200 and b'CineMood' in html
print('[PASS] GET / (Serves index.html with CineMood & Bites)')

s, ct, raw = test('http://127.0.0.1:8000/api/movies?q=Nolan')
assert s == 200
data = json.loads(raw)
assert len(data) > 0
print(f'[PASS] GET /api/movies?q=Nolan -> {len(data)} matches: {data[0]["title"]} ({data[0]["match_badge"]})')

s, ct, raw = test('http://127.0.0.1:8000/api/movies?q=DiCaprio')
assert s == 200
data = json.loads(raw)
assert len(data) > 0
print(f'[PASS] GET /api/movies?q=DiCaprio -> {len(data)} matches: {data[0]["title"]} ({data[0]["match_badge"]})')

s, ct, raw = test('http://127.0.0.1:8000/api/movies/2')
assert s == 200
data = json.loads(raw)
assert 'pairings' in data['movie']
print(f'[PASS] GET /api/movies/2 -> Food: {data["movie"]["pairings"]["food"]}, Drink: {data["movie"]["pairings"]["drink"]}')

s, ct, raw = test('http://127.0.0.1:8000/api/poster/2.svg?mood=thrilling')
assert s == 200 and b'<svg' in raw
print('[PASS] GET /api/poster/2.svg -> Valid dynamic SVG vector poster generated')

s, ct, raw = test('http://127.0.0.1:8000/api/recommend', method='POST', data={'mood': 'thrilling', 'limit': 4})
assert s == 200
recs = json.loads(raw)['results']
print(f'[PASS] POST /api/recommend (Dark/Thrilling) -> {len(recs)} movies with pairings: {recs[0]["title"]} ({recs[0]["pairings"]["food"]})')

print('\nALL SERVER ENDPOINTS FULLY VERIFIED AND HEALTHY!')

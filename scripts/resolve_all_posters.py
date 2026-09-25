"""scripts/resolve_all_posters.py
Resolve all 401 movie/series posters from TMDB, update poster_cache.json,
and save the poster URLs back to data/movies.xlsx so they load instantly on startup.
"""

import os
import re
import time
import json
import requests
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "poster_cache.json"
DATA_FILE = ROOT / "data" / "movies.xlsx"
ENV_FILE = ROOT / ".env"

# Load TMDB key from .env
tmdb_key = ""
if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("TMDB_API_KEY="):
                tmdb_key = line.strip().split("=", 1)[1].strip("'\"")

if not tmdb_key:
    raise ValueError("TMDB_API_KEY not found in .env")

# Load existing cache
poster_cache = {}
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        poster_cache = json.load(f)

print(f"Initial cache entries: {len(poster_cache)}")

df = pd.read_excel(DATA_FILE)

def clean_query_variations(raw_title: str):
    clean = raw_title.strip()
    # Remove trailing (YYYY)
    m = re.search(r"^(.*?)\s*(?:\((\d{4})\))?$", clean)
    if m:
        clean = m.group(1).strip()
    
    variations = [clean]
    # Remove inverted articles
    for article in (", The", ", A", ", An"):
        if clean.endswith(article):
            prefix = article.replace(",", "").strip() + " "
            variations.append(prefix + clean[:-len(article)].strip())
    
    # Strip suffixes like Film, Series, Extra, Legacy, Superfan
    v1 = re.sub(r"\s+(Film|Series|Extra|Legacy|Superfan)$", "", clean, flags=re.I).strip()
    if v1 not in variations:
        variations.append(v1)
    
    # Strip 'Season ...'
    v2 = re.sub(r"\s+Season\s+\w+$", "", v1, flags=re.I).strip()
    if v2 not in variations:
        variations.append(v2)

    # Strip TVF prefix
    v3 = re.sub(r"^(TVF\s+)", "", v2, flags=re.I).strip()
    if v3 not in variations:
        variations.append(v3)

    # Strip trailing numbers like '2', '2025'
    v4 = re.sub(r"\s+(\d{1,4})$", "", v3).strip()
    if v4 not in variations:
        variations.append(v4)

    # Strip subheadings like 'The Bihar Chapter', 'Part One', 'India'
    v5 = re.sub(r"\s+(The Bihar Chapter|Part One|India|Part 1)$", "", v4, flags=re.I).strip()
    if v5 not in variations:
        variations.append(v5)

    return variations

sess = requests.Session()
sess.headers.update({"User-Agent": "CineMoodBites/2.5"})

resolved_count = 0
poster_urls_for_df = []

for idx, row in df.iterrows():
    title = str(row["title"]).strip()
    year = int(row["release_year"]) if pd.notna(row["release_year"]) else None
    
    # Sanitize title as poster_service does
    clean_t = title
    m = re.search(r"^(.*?)\s*(?:\((\d{4})\))?$", clean_t)
    ext_y = None
    if m:
        clean_t = m.group(1).strip()
        if m.group(2):
            ext_y = int(m.group(2))
    for article in (", The", ", A", ", An"):
        if clean_t.endswith(article):
            prefix = article.replace(",", "").strip() + " "
            clean_t = prefix + clean_t[:-len(article)].strip()
            break
            
    sy = year or ext_y
    cache_key = f"tmdb:{clean_t}:{sy}"
    
    poster = poster_cache.get(cache_key)
    
    if not poster or not poster.startswith("http"):
        # Try finding poster from variations
        variations = clean_query_variations(title)
        for q in variations:
            for endpoint in ["search/multi", "search/movie", "search/tv"]:
                try:
                    params = {"api_key": tmdb_key, "query": q}
                    if sy and endpoint in ("search/movie",):
                        params["year"] = str(sy)
                    resp = sess.get(f"https://api.themoviedb.org/3/{endpoint}", params=params, timeout=8)
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        for r in results:
                            p_path = r.get("poster_path")
                            if p_path:
                                poster = f"https://image.tmdb.org/t/p/w500{p_path}"
                                break
                    if poster:
                        break
                except Exception as e:
                    time.sleep(0.3)
            if poster:
                break
        
        if poster:
            poster_cache[cache_key] = poster
            print(f"[{idx+1}/{len(df)}] Resolved '{title}' -> {poster}")
        else:
            print(f"[{idx+1}/{len(df)}] NOT FOUND: '{title}'")
            poster = ""
    
    if poster and poster.startswith("http"):
        resolved_count += 1
    poster_urls_for_df.append(poster)

print(f"\nFinal tally: {resolved_count}/{len(df)} resolved!")

# Save to poster_cache.json
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(poster_cache, f, indent=2)
print(f"Saved {len(poster_cache)} items to poster_cache.json")

# Update data/movies.xlsx with the resolved poster URLs!
df["poster_url"] = poster_urls_for_df
df.to_excel(DATA_FILE, index=False)
print(f"Updated data/movies.xlsx with {resolved_count} poster URLs!")

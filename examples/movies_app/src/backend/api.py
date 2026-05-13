import json
import logging
import ssl
import time
import urllib.parse
import urllib.request

_cache = {}
CACHE_TTL = 3600  # 1 hour


def fetch_tmdb(endpoint: str, key: str, params: dict = None) -> dict:
    if not key:
        raise ValueError("API Key missing")
    if not params:
        params = {}
    params["api_key"] = key
    query = urllib.parse.urlencode(params)
    url = f"https://api.themoviedb.org/3/{endpoint}?{query}"

    # Check cache
    if url in _cache:
        cached_data, timestamp = _cache[url]
        if time.time() - timestamp < CACHE_TTL:
            logging.info(f"Cache hit for {url}")
            return cached_data

    logging.info(f"Fetching TMDB endpoint {endpoint} with key={key[:5]}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
            data = json.loads(response.read().decode())
            _cache[url] = (data, time.time())
            return data
    except Exception as e:
        logging.error(f"fetch_tmdb error for {endpoint}: {e}")
        raise

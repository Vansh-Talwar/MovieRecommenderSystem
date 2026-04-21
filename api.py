import logging
import streamlit as st
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    API_KEY, BASE_URL,
    CONNECT_TIMEOUT, READ_TIMEOUT,
    MAX_RETRIES, BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
)

@st.cache_resource
def _tmdb_session() -> requests.Session:
    s = requests.Session()

    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"Accept": "application/json"})
    return s

def fetch_tmdb(endpoint: str, params: dict | None = None):
    params = dict(params or {})
    params["api_key"] = API_KEY

    url = f"{BASE_URL}{endpoint}"
    session = _tmdb_session()

    try:
        r = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.exceptions.RequestException as e:
        logging.exception("TMDB request failed: %s", e)
        return None

    if r.status_code == 401:
        st.error("Invalid TMDB API key. Check TMDB_API in .env.")
        return None
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        st.warning("TMDB rate limited (429). Please try again in a moment.")
        return None
    if r.status_code >= 400:
        logging.warning("TMDB HTTP %s for %s", r.status_code, r.url)
        return None

    try:
        return r.json()
    except ValueError:
        logging.warning("Invalid JSON from TMDB for %s", r.url)
        return None

@st.cache_data(ttl=3600, max_entries=1)
def get_genres():
    data = fetch_tmdb("/genre/movie/list", {"language": "en-US"})
    if data:
        return {g["name"]: g["id"] for g in data.get("genres", [])}
    return {}

@st.cache_data(ttl=1800, max_entries=256)
def search_movie(query: str):
    data = fetch_tmdb("/search/movie", {"query": query, "include_adult": False})
    if data and data.get("results"):
        return data["results"][0]
    return None

@st.cache_data(ttl=1800, max_entries=512)
def get_movies_by_genre(genre_id: int, page: int = 1, sort_by: str = "popularity.desc"):
    data = fetch_tmdb("/discover/movie", {
        "with_genres": genre_id,
        "sort_by": sort_by,
        "page": page,
        "include_adult": False,
        "vote_count.gte": 50,
    })
    if data:
        return data.get("results", [])
    return []

@st.cache_data(ttl=1800, max_entries=512)
def get_similar_movies(movie_id: int, page: int = 1):
    data = fetch_tmdb(f"/movie/{movie_id}/recommendations", {"page": page})
    if data:
        return data.get("results", [])
    return []

@st.cache_data(ttl=1800, max_entries=2)
def get_trending_movies(period: str = "day", page: int = 1):
    data = fetch_tmdb(f"/trending/movie/{period}", {"page": page})
    if data:
        return data.get("results", [])
    return []

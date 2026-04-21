import os
import logging
from dotenv import load_dotenv

# In dev, override=True helps avoid stale env vars from shell/previous runs.
# In prod, you can set override=False if you prefer system env to win.
load_dotenv(override=True)  # [web:32]

API_KEY = os.getenv("TMDB_API")
if not API_KEY:
    raise ValueError("Missing TMDB_API key. Add it to your .env file.")

BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")

# Timeouts: keep connect timeout smaller; read timeout a bit larger.
CONNECT_TIMEOUT = float(os.getenv("CONNECT_TIMEOUT", 3.05))
READ_TIMEOUT = float(os.getenv("READ_TIMEOUT", 10))

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 4))
BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", 0.5))

# Retry on transient statuses, especially 429 + 5xx.
RETRY_STATUS_CODES = tuple(
    int(x) for x in os.getenv("RETRY_STATUS_CODES", "429,500,502,503,504").split(",")
)

DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)

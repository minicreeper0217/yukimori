import os
from pathlib import Path

dir = Path(__file__).resolve().parent

cloudflare_turnstile_key = os.environ["CF_TURNSTILE_KEY"]
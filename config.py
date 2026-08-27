import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

USER_AGENT = "NewsAggregatorBot/1.0 (uso pessoal; contacto: leonel.costa@colep-pk.com)"
REQUEST_TIMEOUT = 15
CRAWL_DELAY_SECONDS = 1.5

DEDUP_DB_PATH = DATA_DIR / "seen_articles.db"

# Quais clubes/fontes estão ativos é uma preferência do utilizador, gerida pelo
# painel de controlo (control_panel.py) e guardada em settings.json — ver settings.py.

CLUB_DISPLAY_NAMES = {
    "fc_porto": "FC Porto",
    "benfica": "Benfica",
    "sporting": "Sporting",
}

# Variações usadas para deteção de clube em fontes que não vêm pré-categorizadas
# (ex: canal de Telegram do Fabrizio Romano). O ojogo.pt já segmenta por clube
# através das páginas de tópico, por isso não precisa deste filtro.
CLUB_KEYWORDS = {
    # "oporto" é como a imprensa espanhola (ex: marca.com) se refere ao FC Porto
    "fc_porto": ["fc porto", "f.c. porto", "fcp", "dragões", "dragoes", "portistas", "oporto"],
    "benfica": ["benfica", "slb", "águias", "aguias", "encarnados"],
    # nota: "sporting" sozinho apanharia falsos positivos (Sporting Braga, Sporting
    # Gijón, Sporting Kansas City, etc.), por isso exige-se sempre a referência a
    # Lisboa/Portugal ou a sigla/alcunha específica do clube.
    "sporting": ["sporting cp", "sporting clube de portugal", "sporting lisboa", "sporting lisbon", "scp", "leões", "leoes"],
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_TIMEOUT_MS = 20000
GEMINI_DELAY_SECONDS = 4.5  # cortesia para não estourar os limites do tier gratuito
MIN_BOMBAST_SCORE_TO_SEND = 6  # notícia de "última hora"/importante ou acima; abaixo só é
# enviada se for de mercado de transferências (ver is_transfer_market) — outras ficam só
# marcadas como vistas, sem envio
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELETHON_API_ID = os.getenv("TELETHON_API_ID")
TELETHON_API_HASH = os.getenv("TELETHON_API_HASH")
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "newsai_session")
TELETHON_SESSION_PATH = str(DATA_DIR / TELETHON_SESSION_NAME)
TELETHON_CHANNEL_USERNAME = os.getenv("TELETHON_CHANNEL_USERNAME", "fabrizioromanotg")
# Em CI (ex: GitHub Actions) não há ficheiro de sessão persistente entre execuções —
# usa-se uma StringSession guardada como secret em vez do ficheiro local.
TELETHON_STRING_SESSION = os.getenv("TELETHON_STRING_SESSION")

"""Leitura do canal público de Telegram do Fabrizio Romano, via Telethon.

Tal como o RSS do Di Marzio, este canal não é segmentado por clube — aplica-se
o filtro de palavras-chave a cada mensagem para decidir se é relevante para
FC Porto, Benfica ou Sporting.

Requer sessão Telethon já autenticada (ver telethon_login.py, a correr uma
vez manualmente). Se a sessão não existir ou não estiver autorizada, este
scraper regista um erro e devolve lista vazia — nunca tenta fazer login
interativo dentro do pipeline automático.

Em CI (ex: GitHub Actions) não há ficheiro de sessão persistente entre
execuções — usa-se antes uma StringSession guardada em TELETHON_STRING_SESSION
(ver telethon_session_to_string.py para gerar essa string uma vez, localmente).
"""

import logging

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from config import (
    TELETHON_API_HASH,
    TELETHON_API_ID,
    TELETHON_CHANNEL_USERNAME,
    TELETHON_SESSION_PATH,
    TELETHON_STRING_SESSION,
)
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem

logger = logging.getLogger(__name__)

SOURCE_NAME = "fabrizio_telegram"

MESSAGES_TO_SCAN = 30


def _fetch_messages():
    if not TELETHON_API_ID or not TELETHON_API_HASH:
        logger.warning("TELETHON_API_ID/TELETHON_API_HASH em falta no .env — a saltar esta fonte")
        return []

    session = StringSession(TELETHON_STRING_SESSION) if TELETHON_STRING_SESSION else TELETHON_SESSION_PATH
    client = TelegramClient(session, int(TELETHON_API_ID), TELETHON_API_HASH)
    try:
        client.connect()
        if not client.is_user_authorized():
            logger.error(
                "Sessão do Telethon não autenticada — corre `python telethon_login.py` manualmente primeiro"
            )
            return []
        return list(client.get_messages(TELETHON_CHANNEL_USERNAME, limit=MESSAGES_TO_SCAN))
    except Exception:
        logger.exception("Falha ao ler mensagens do canal @%s", TELETHON_CHANNEL_USERNAME)
        return []
    finally:
        client.disconnect()


def _collect_all() -> list[NewsItem]:
    messages = _fetch_messages()
    items = []
    for msg in messages:
        text = (msg.text or "").strip()
        if not text:
            continue
        clubs = detect_clubs(text)
        if not clubs:
            continue

        first_line = text.splitlines()[0]
        title = first_line[:140] + ("…" if len(first_line) > 140 else "")
        url = f"https://t.me/{TELETHON_CHANNEL_USERNAME}/{msg.id}"
        published_at = msg.date.isoformat() if msg.date else None

        for club in clubs:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=str(msg.id),
                    club=club,
                    title=title,
                    url=url,
                    published_at=published_at,
                    author="Fabrizio Romano",
                    summary=text,
                    body=text,
                    is_paywalled=False,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

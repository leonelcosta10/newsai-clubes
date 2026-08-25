"""Leitor do RSS do Gianluca Di Marzio.

Ao contrário das outras fontes, este feed não é segmentado por clube — cobre
sobretudo o mercado italiano. Por isso aplica-se o filtro de palavras-chave
(filtering.keywords) ao título+resumo de cada item para decidir a que
clube(s) pertence, e só se guarda o item quando há correspondência.
"""

import logging
import re

import feedparser

from config import REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "dimarzio"

FEED_URL = "https://www.gianlucadimarzio.com/rss/"

_ID_RE = re.compile(r"(\d+)(?:\?.*)?$")


def _fetch_feed_bytes():
    session = build_session()
    try:
        resp = session.get(FEED_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.exception("Falha ao obter o RSS do Di Marzio")
        return None


def _extract_id(entry) -> str:
    guid = entry.get("id") or entry.get("guid") or entry.get("link", "")
    match = _ID_RE.search(guid)
    return match.group(1) if match else guid


def _collect_all() -> list[NewsItem]:
    raw = _fetch_feed_bytes()
    if raw is None:
        return []

    try:
        parsed = feedparser.parse(raw)
    except Exception:
        logger.exception("Falha ao parsear o RSS do Di Marzio — o formato do feed pode ter mudado")
        return []

    if parsed.bozo:
        logger.warning("RSS do Di Marzio devolvido com aviso de formato: %s", parsed.get("bozo_exception"))

    items = []
    for entry in parsed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        clubs = detect_clubs(f"{title} {summary}")
        if not clubs:
            continue
        article_id = _extract_id(entry)
        for club in clubs:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=article_id,
                    club=club,
                    title=title,
                    url=entry.get("link", ""),
                    published_at=entry.get("published"),
                    author="Gianluca Di Marzio",
                    summary=summary,
                    body=None,
                    is_paywalled=False,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

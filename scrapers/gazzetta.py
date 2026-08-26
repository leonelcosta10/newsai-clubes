"""Leitura do live blog diário de mercado da Gazzetta dello Sport (gazzetta.it).

O URL da página do dia tem a data embutida (ex: /Calciomercato/26-08-2026/...),
por isso não se constrói a data manualmente — vai-se sempre buscar o link mais
recente à página de secção do Calciomercato, que aponta sempre para o live do
dia atual.

Não é segmentado por clube, e ao contrário do Foot Mercato não tem marcação
estruturada dos clubes envolvidos — usa-se o filtro de palavras-chave.
"""

import logging
import re

from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "gazzetta"

BASE_URL = "https://www.gazzetta.it"
SECTION_URL = "https://www.gazzetta.it/calciomercato/"

_LIVE_HREF_RE = re.compile(r"/Calciomercato/[\d-]+/notizie-calciomercato-il-live-di-oggi[^\"']*")


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


def _find_today_live_url(session) -> str | None:
    html = _fetch(session, SECTION_URL)
    if html is None:
        return None
    match = _LIVE_HREF_RE.search(html)
    if not match:
        logger.warning("Não encontrei o link do live de hoje em %s", SECTION_URL)
        return None
    href = match.group(0)
    return href if href.startswith("http") else BASE_URL + href


def _parse_entries(html: str) -> list[dict]:
    entries = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for row in soup.select("div.chronicle-row[id]"):
            title_el = row.select_one("h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            body_el = row.select_one("p.paragraph")
            body = body_el.get_text(" ", strip=True) if body_el else None

            time_el = row.select_one("time[datetime]")
            published_at = time_el.get("datetime") if time_el else None

            entries.append(
                {
                    "external_id": row["id"],
                    "title": title,
                    "body": body,
                    "published_at": published_at,
                }
            )
        if not entries:
            logger.warning("Nenhuma entrada encontrada no live blog da Gazzetta")
    except Exception:
        logger.exception("Falha ao parsear o live blog — a estrutura pode ter mudado")
    return entries


def _collect_all() -> list[NewsItem]:
    session = build_session()
    live_url = _find_today_live_url(session)
    if live_url is None:
        return []

    html = _fetch(session, live_url)
    if html is None:
        return []

    items = []
    for entry in _parse_entries(html):
        text = f"{entry['title']} {entry['body'] or ''}"
        clubs = detect_clubs(text)
        if not clubs:
            continue
        for club in clubs:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=entry["external_id"],
                    club=club,
                    title=entry["title"],
                    url=live_url,
                    published_at=entry["published_at"],
                    author="Gazzetta dello Sport",
                    summary=None,
                    body=entry["body"],
                    is_paywalled=False,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

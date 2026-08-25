"""Scraper do abola.pt: páginas de tópico por clube + meta tags de cada artigo.

Ao contrário do ojogo.pt e do record.pt, o abola.pt não usa JSON-LD estruturado
nos artigos — os metadados vêm de meta tags standard (og:description,
article:published_time). Não foram encontrados indicadores de paywall no
conteúdo inspecionado, por isso assume-se acesso livre por omissão.
"""

import logging
import re
import time

from bs4 import BeautifulSoup

from config import CRAWL_DELAY_SECONDS, REQUEST_TIMEOUT
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "abola"

CLUB_TOPIC_URLS = {
    "fc_porto": "https://www.abola.pt/futebol/fc-porto-451",
    "benfica": "https://www.abola.pt/futebol/benfica-450",
    "sporting": "https://www.abola.pt/futebol/sporting-448",
}

_ID_SUFFIX_RE = re.compile(r"-(\d{10,})$")


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


def _parse_listing(html: str) -> list[dict]:
    items = []
    try:
        soup = BeautifulSoup(html, "lxml")
        seen_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/noticias/" not in href:
                continue
            title = a.get_text(strip=True)
            if not title or href in seen_urls:
                continue
            seen_urls.add(href)
            match = _ID_SUFFIX_RE.search(href)
            article_id = match.group(1) if match else href
            items.append({"title": title, "url": href, "article_id": article_id})
    except Exception:
        logger.exception("Falha ao parsear listagem — a estrutura HTML pode ter mudado")
    return items


def _extract_body_text(soup: BeautifulSoup) -> str | None:
    best = None
    best_len = 0
    for container in soup.find_all(["div", "section", "article"]):
        paragraphs = container.find_all("p", recursive=False)
        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
        if len(text) > best_len:
            best_len = len(text)
            best = text
    return best or None


def _parse_article_meta(html: str) -> dict:
    try:
        soup = BeautifulSoup(html, "lxml")

        description = None
        meta_desc = soup.find("meta", attrs={"property": "og:description"}) or soup.find(
            "meta", attrs={"name": "description"}
        )
        if meta_desc:
            description = meta_desc.get("content")

        published_at = None
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date:
            published_at = meta_date.get("content")

        return {
            "description": description,
            "published_at": published_at,
            "author": None,  # não há meta tag de autor consistente neste site
            "is_paywalled": False,  # sem indicadores de paywall encontrados na inspeção
            "body": _extract_body_text(soup),
        }
    except Exception:
        logger.exception("Falha ao parsear metadados do artigo")
        return {}


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    topic_url = CLUB_TOPIC_URLS.get(club)
    if not topic_url:
        logger.error("Clube desconhecido para o abola.pt: %s", club)
        return []

    session = build_session()
    html = _fetch(session, topic_url)
    if html is None:
        return []

    listing = _parse_listing(html)[:limit]
    if not listing:
        logger.warning("Nenhuma notícia encontrada em %s — verificar seletores", topic_url)
        return []

    results = []
    for entry in listing:
        time.sleep(CRAWL_DELAY_SECONDS)
        article_html = _fetch(session, entry["url"])
        if article_html is None:
            continue
        meta = _parse_article_meta(article_html)
        results.append(
            NewsItem(
                source=SOURCE_NAME,
                external_id=entry["article_id"],
                club=club,
                title=entry["title"],
                url=entry["url"],
                published_at=meta.get("published_at"),
                author=meta.get("author"),
                summary=meta.get("description"),
                body=meta.get("body"),
                is_paywalled=meta.get("is_paywalled", False),
            )
        )
    return results

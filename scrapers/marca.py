"""Leitura da secção da Liga Portuguesa no marca.com + JSON-LD do artigo.

A secção da liga portuguesa não é segmentada por clube — mistura FC Porto,
Benfica e Sporting (e por vezes outros clubes portugueses) na mesma página.
Por isso aplica-se o filtro de palavras-chave a cada artigo, tal como no RSS
do Di Marzio. Nota: a imprensa espanhola escreve "Oporto" em vez de "FC Porto"
— por isso essa variante foi acrescentada a CLUB_KEYWORDS em config.py.
"""

import json
import logging
import time

from bs4 import BeautifulSoup

from config import CRAWL_DELAY_SECONDS, REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "marca"

LEAGUE_URL = "https://www.marca.com/futbol/liga-portuguesa.html"


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
        for h2 in soup.select("h2[class*='headline']"):
            a = h2.find_parent("a")
            if not a or not a.get("href"):
                continue
            href = a["href"].split("?")[0]
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title = h2.get_text(strip=True)
            if not title:
                continue
            article_id = href.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
            items.append({"title": title, "url": href, "article_id": article_id})
    except Exception:
        logger.exception("Falha ao parsear listagem — a estrutura HTML pode ter mudado")
    return items


def _parse_article_meta(html: str) -> dict:
    try:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for item in candidates:
                if isinstance(item, dict) and item.get("@type") == "NewsArticle":
                    authors = item.get("author") or []
                    author_name = authors[0].get("name") if authors else None
                    is_free = bool(item.get("isAccessibleForFree", False))
                    return {
                        "description": item.get("description"),
                        "published_at": item.get("datePublished"),
                        "author": author_name,
                        "is_paywalled": not is_free,
                        "body": item.get("articleBody") if is_free else None,
                    }
        logger.warning("Nenhum bloco JSON-LD NewsArticle encontrado — usando metadados vazios")
    except Exception:
        logger.exception("Falha ao parsear metadados do artigo")
    return {}


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    session = build_session()
    html = _fetch(session, LEAGUE_URL)
    if html is None:
        return []

    listing = _parse_listing(html)
    if not listing:
        logger.warning("Nenhuma notícia encontrada em %s — verificar seletores", LEAGUE_URL)
        return []

    results = []
    for entry in listing:
        clubs_in_title = detect_clubs(entry["title"])
        if club not in clubs_in_title and clubs_in_title:
            # já sabemos por só pelo título que é de outro clube — não vale a pena
            # gastar um pedido a buscar o artigo
            continue

        time.sleep(CRAWL_DELAY_SECONDS)
        article_html = _fetch(session, entry["url"])
        if article_html is None:
            continue
        meta = _parse_article_meta(article_html)

        relevance_text = f"{entry['title']} {meta.get('description') or ''}"
        if club not in detect_clubs(relevance_text):
            continue

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
        if len(results) >= limit:
            break
    return results

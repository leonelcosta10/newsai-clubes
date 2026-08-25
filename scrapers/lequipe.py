"""Leitura da secção do Campeonato Português no lequipe.fr + JSON-LD do artigo.

Página não segmentada por clube — mistura FC Porto, Benfica, Sporting e outros
clubes portugueses. Usa-se o filtro de palavras-chave, com uma regra extra local:
em francês escreve-se muitas vezes só "le Sporting" (sem "CP"), o que o filtro
genérico (pensado para evitar confusão com o Sporting Braga/Gijón) não apanharia.
Como esta página já está limitada à liga portuguesa, aceita-se "Sporting" isolado
aqui, desde que o texto não mencione também "Braga".
"""

import json
import logging
import re
import time

from bs4 import BeautifulSoup

from config import CRAWL_DELAY_SECONDS, REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "lequipe"

LEAGUE_URL = "https://www.lequipe.fr/Football/Championnat-du-portugal/"
BASE_URL = "https://www.lequipe.fr"

_BARE_SPORTING_RE = re.compile(r"\bsporting\b", re.IGNORECASE)


def _detect_clubs_local(text: str) -> set[str]:
    clubs = detect_clubs(text)
    if "sporting" not in clubs and _BARE_SPORTING_RE.search(text) and "braga" not in text.lower():
        clubs.add("sporting")
    return clubs


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
        for h2 in soup.select("h2[class*='ColeaderWidget__title']"):
            a = h2.find_parent("a")
            if not a or not a.get("href"):
                continue
            href = a["href"].split("?")[0]
            if not href.startswith("http"):
                href = BASE_URL + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title = h2.get_text(strip=True)
            if not title:
                continue
            article_id = href.rstrip("/").rsplit("/", 1)[-1]
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
            graph = data.get("@graph", [data]) if isinstance(data, dict) else data
            for item in graph:
                if isinstance(item, dict) and item.get("@type") == "NewsArticle":
                    return {
                        "description": item.get("description"),
                        "published_at": item.get("datePublished"),
                        "author": None,  # não há autor consistente neste JSON-LD
                        "is_paywalled": False,  # sem indicador de paywall encontrado na inspeção
                        "body": item.get("articleBody"),
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
        clubs_in_title = _detect_clubs_local(entry["title"])
        if club not in clubs_in_title and clubs_in_title:
            continue  # título já identifica outro(s) clube(s) — não vale a pena buscar o artigo

        time.sleep(CRAWL_DELAY_SECONDS)
        article_html = _fetch(session, entry["url"])
        if article_html is None:
            continue
        meta = _parse_article_meta(article_html)

        relevance_text = f"{entry['title']} {meta.get('description') or ''}"
        if club not in _detect_clubs_local(relevance_text):
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

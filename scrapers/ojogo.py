"""Scraper do ojogo.pt: páginas de tópico por clube + metadados JSON-LD de cada artigo.

Boas práticas aplicadas: User-Agent identificável, atraso entre pedidos, e
tratamento de erros para não sobrecarregar o site nem falhar de forma ruidosa.
"""

import json
import logging
import time

from bs4 import BeautifulSoup

from config import CRAWL_DELAY_SECONDS, REQUEST_TIMEOUT
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "ojogo"

CLUB_TOPIC_URLS = {
    "fc_porto": "https://www.ojogo.pt/topico/fc-porto",
    "benfica": "https://www.ojogo.pt/topico/benfica",
    "sporting": "https://www.ojogo.pt/topico/sporting",
}


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


def _parse_listing(html: str) -> list[dict]:
    """Extrai título, URL e ID de cada notícia da página de tópico.

    Depende da presença de um <h2 class*="Title"> dentro de um <a> com href —
    as classes CSS têm hash e podem mudar entre deploys, mas a estrutura
    título-dentro-de-link tem-se mantido estável.
    """
    items = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for h2 in soup.select("h2[class*='Title']"):
            a = h2.find_parent("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            article_id = href.rstrip("/").split("/")[-1]
            title = h2.get_text(strip=True)
            if not article_id.isdigit():
                # padrão inesperado no URL — ignora este item em vez de falhar tudo
                logger.warning("URL de artigo sem ID numérico no fim, a ignorar: %s", href)
                continue
            if title.lower().startswith("mercado ao minuto"):
                # live blog atualizado continuamente — o título na listagem muda ao
                # longo do dia mas o URL é fixo, por isso um resumo feito num instante
                # fica desalinhado do título assim que o blog for atualizado de novo
                continue
            items.append({"title": title, "url": href, "article_id": article_id})
    except Exception:
        logger.exception("Falha ao parsear listagem — a estrutura HTML pode ter mudado")
    return items


def _parse_article_meta(html: str) -> dict:
    """Extrai metadados do bloco JSON-LD NewsArticle: description, data, autor, paywall."""
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
                    body = None
                    if is_free:
                        body = _extract_body_text(soup)
                    return {
                        "description": item.get("description"),
                        "published_at": item.get("datePublished"),
                        "author": author_name,
                        "is_paywalled": not is_free,
                        "body": body,
                    }
        logger.warning("Nenhum bloco JSON-LD NewsArticle encontrado — usando metadados vazios")
    except Exception:
        logger.exception("Falha ao parsear metadados do artigo")
    return {}


def _extract_body_text(soup: BeautifulSoup) -> str | None:
    container = soup.select_one("div[class*='AGBodyContent']")
    if not container:
        return None
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = " ".join(p for p in paragraphs if p)
    return text or None


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    """Recolhe as notícias mais recentes de um clube. Devolve lista vazia em caso de erro
    (nunca propaga exceção — o pipeline principal deve continuar com as outras fontes/clubes)."""
    topic_url = CLUB_TOPIC_URLS.get(club)
    if not topic_url:
        logger.error("Clube desconhecido para o ojogo.pt: %s", club)
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

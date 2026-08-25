"""Scraper do record.pt: páginas de tópico por clube (liga-betclic/{clube}) + JSON-LD do artigo.

A listagem mistura links para artigos normais (".../detalhe/...") com vídeos e
páginas de jogo ao vivo (".../multimedia/videos/...", ".../jogos-em-direto/...");
só seguimos os links "/detalhe/", que são os que têm JSON-LD NewsArticle fiável.
"""

import json
import logging
import time

from bs4 import BeautifulSoup

from config import CRAWL_DELAY_SECONDS, REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "record"

CLUB_TOPIC_URLS = {
    "fc_porto": "https://www.record.pt/futebol/futebol-nacional/liga-betclic/fc-porto",
    "benfica": "https://www.record.pt/futebol/futebol-nacional/liga-betclic/benfica",
    "sporting": "https://www.record.pt/futebol/futebol-nacional/liga-betclic/sporting",
}


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


# Secções da página de tópico que não são notícias do próprio clube: "cstudio" é
# publicidade nativa/patrocinada, "noticias_clube" é um widget de recirculação
# com notícias de OUTROS clubes (ex: apareceu Sevilha/Barcelona/andebol na
# página do FC Porto). Ambas têm nomes de classe semânticos e estáveis.
_EXCLUDED_SECTION_CLASSES = {"cstudio", "noticias_clube"}


def _is_in_excluded_section(h2) -> bool:
    section = h2.find_parent("section")
    if not section:
        return False
    classes = set(section.get("class") or [])
    return bool(classes & _EXCLUDED_SECTION_CLASSES)


def _parse_listing(html: str) -> list[dict]:
    items = []
    try:
        soup = BeautifulSoup(html, "lxml")
        seen_urls = set()
        for h2 in soup.find_all("h2"):
            if _is_in_excluded_section(h2):
                continue
            container = h2.parent.parent if h2.parent else None
            if not container:
                continue
            a = container.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if (
                "/detalhe/" not in href
                or "/multimedia/" in href
                or "/jogos-em-direto/" in href
                or "/iniciativas/" in href  # publicidade nativa (defesa extra além do filtro de secção)
            ):
                continue  # ignora vídeos, páginas de jogo ao vivo e conteúdo patrocinado
            href = href.split("?")[0]
            if not href.startswith("http"):
                href = "https://www.record.pt" + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title = h2.get_text(strip=True)
            if not title:
                continue
            items.append({"title": title, "url": href, "article_id": href})
    except Exception:
        logger.exception("Falha ao parsear listagem — a estrutura HTML pode ter mudado")
    return items


def _extract_body_text(soup: BeautifulSoup) -> str | None:
    container = soup.select_one("div[class*='text_container']")
    if not container:
        return None
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = " ".join(p for p in paragraphs if p)
    return text or None


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
                    author = item.get("author") or {}
                    is_free = bool(item.get("isAccessibleForFree", False))
                    body = _extract_body_text(soup) if is_free else None
                    return {
                        "description": item.get("description"),
                        "published_at": item.get("datePublished"),
                        "author": author.get("name") if isinstance(author, dict) else None,
                        "is_paywalled": not is_free,
                        "body": body,
                    }
        logger.warning("Nenhum bloco JSON-LD NewsArticle encontrado — usando metadados vazios")
    except Exception:
        logger.exception("Falha ao parsear metadados do artigo")
    return {}


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    topic_url = CLUB_TOPIC_URLS.get(club)
    if not topic_url:
        logger.error("Clube desconhecido para o record.pt: %s", club)
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

        # Rede de segurança: a página de tópico tem secções genéricas (ex: "lista_generica")
        # que por vezes misturam conteúdo sem relação com o clube. Confirma-se a relevância
        # pelo título+resumo antes de aceitar o item.
        relevance_text = f"{entry['title']} {meta.get('description') or ''}"
        if club not in detect_clubs(relevance_text):
            logger.info("A ignorar item sem relação aparente com %s: %s", club, entry["title"])
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
    return results

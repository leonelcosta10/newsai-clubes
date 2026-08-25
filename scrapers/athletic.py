"""Leitura da página de autor do David Ornstein no The Athletic (nytimes.com).

Conteúdo inteiramente por assinatura: um único pedido HTTP por execução (só a
página do autor, nunca as páginas de artigo individuais) e extraem-se apenas
título+excerto públicos — o mesmo que qualquer visitante não-subscritor vê,
nunca o texto do artigo.

Tal como o RSS do Di Marzio, esta página não é segmentada por clube — aplica-se
o filtro de palavras-chave ao título+excerto de cada artigo.
"""

import logging
import re

from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "athletic"

AUTHOR_URL = "https://www.nytimes.com/athletic/author/david-ornstein/"

_ARTICLE_HREF_RE = re.compile(r"^https://www\.nytimes\.com/athletic/(\d+)/(\d{4})/(\d{2})/(\d{2})/")


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
        seen = set()
        for a in soup.find_all("a", href=True):
            match = _ARTICLE_HREF_RE.match(a["href"])
            if not match:
                continue
            href = a["href"]
            if href in seen:
                continue
            seen.add(href)

            article_id, year, month, day = match.groups()

            # O texto visível dos cartões varia de layout para layout (título direto,
            # ou às vezes uma frase de contexto antes do título) — mas o "alt" da
            # imagem contém sempre o título real, de forma consistente.
            img = a.find("img")
            title = img.get("alt", "").strip() if img else None
            if not title:
                continue

            description = None
            excerpt_el = a.find("p", class_=re.compile("excerpt"))
            if excerpt_el:
                description = excerpt_el.get_text(" ", strip=True)

            items.append(
                {
                    "title": title,
                    "url": href,
                    "article_id": article_id,
                    "published_at": f"{year}-{month}-{day}",
                    "description": description,
                }
            )
    except Exception:
        logger.exception("Falha ao parsear a página do autor — a estrutura HTML pode ter mudado")
    return items


def _collect_all() -> list[NewsItem]:
    session = build_session()
    html = _fetch(session, AUTHOR_URL)
    if html is None:
        return []

    listing = _parse_listing(html)
    items = []
    for entry in listing:
        text = f"{entry['title']} {entry.get('description') or ''}"
        clubs = detect_clubs(text)
        if not clubs:
            continue
        for club in clubs:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=entry["article_id"],
                    club=club,
                    title=entry["title"],
                    url=entry["url"],
                    published_at=entry["published_at"],
                    author="David Ornstein",
                    summary=entry.get("description"),
                    body=None,  # conteúdo integral é pago; nunca se tenta aceder a ele
                    is_paywalled=True,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

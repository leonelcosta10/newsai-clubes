"""Leitura do live blog de transferências do footmercato.net.

A página "transferts-en-direct" é um único live blog (schema.org LiveBlogPosting)
atualizado ao longo do dia, mas — ao contrário do "Mercado ao minuto" do
ojogo.pt — cada atualização vem bem estruturada no JSON-LD, com o seu próprio
título, corpo e data de publicação, por isso não sofre do mesmo problema de
desalinhamento entre título e conteúdo.

Não é segmentado por clube — aplica-se o filtro de palavras-chave a cada
atualização, tal como no RSS do Di Marzio.

Como as atualizações não têm URL/id próprio (só a página do live blog em si),
usa-se um hash de data+título como identificador único para efeitos de dedup.
"""

import hashlib
import json
import logging

from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "footmercato"

LIVE_URL = "https://www.footmercato.net/transferts-en-direct"


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


def _parse_updates(html: str) -> list[dict]:
    updates = []
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
                if isinstance(item, dict) and item.get("@type") == "LiveBlogPosting":
                    for update in item.get("liveBlogUpdate", []):
                        title = update.get("headline")
                        body = update.get("articleBody")
                        published_at = update.get("datePublished")
                        if not title or not body:
                            continue
                        external_id = hashlib.sha1(f"{published_at}|{title}".encode("utf-8")).hexdigest()[:16]
                        updates.append(
                            {
                                "title": title,
                                "body": body,
                                "published_at": published_at,
                                "external_id": external_id,
                            }
                        )
        if not updates:
            logger.warning("Nenhuma atualização encontrada em %s — verificar estrutura da página", LIVE_URL)
    except Exception:
        logger.exception("Falha ao parsear o live blog — a estrutura pode ter mudado")
    return updates


def _collect_all() -> list[NewsItem]:
    session = build_session()
    html = _fetch(session, LIVE_URL)
    if html is None:
        return []

    items = []
    for update in _parse_updates(html):
        text = f"{update['title']} {update['body']}"
        clubs = detect_clubs(text)
        if not clubs:
            continue
        for club in clubs:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=update["external_id"],
                    club=club,
                    title=update["title"],
                    url=LIVE_URL,
                    published_at=update["published_at"],
                    author="Foot Mercato",
                    summary=None,
                    body=update["body"],
                    is_paywalled=False,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

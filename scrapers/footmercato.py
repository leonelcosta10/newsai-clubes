"""Leitura do live blog de transferências do footmercato.net.

A página "transferts-en-direct" é um live blog atualizado ao longo do dia.
Cada atualização ("brief") tem um id estável, uma data, título, corpo, e — o
mais útil — os logótipos dos clubes envolvidos, com link para a página de
cada clube (ex: /club/fc-porto/). Usa-se essa marcação editorial para saber
a que clube(s) a notícia pertence, em vez de só palavras-chave — é mais
fiável, já que é o próprio site a identificar os clubes da notícia.

Como rede de segurança, se uma atualização não tiver nenhum logo dos nossos
3 clubes mas mencionar um deles no texto, o filtro de palavras-chave apanha-a
também (útil para atualizações sem essa marcação).
"""

import logging
import re

from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT
from filtering.keywords import detect_clubs
from scrapers.base import NewsItem, build_session

logger = logging.getLogger(__name__)

SOURCE_NAME = "footmercato"

LIVE_URL = "https://www.footmercato.net/transferts-en-direct"

# slug da página do clube no footmercato.net -> chave interna do clube
CLUB_SLUG_MAP = {
    "fc-porto": "fc_porto",
    "sl-benfica": "benfica",
    "sporting-clube-de-portugal": "sporting",
}

_CLUB_HREF_RE = re.compile(r"/club/([^/]+)/")


def _fetch(session, url):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.exception("Falha ao obter %s", url)
        return None


def _clubs_from_logos(brief) -> set[str]:
    clubs = set()
    for a in brief.select("div.brief__logos a[href*='/club/']"):
        match = _CLUB_HREF_RE.search(a["href"])
        if match and match.group(1) in CLUB_SLUG_MAP:
            clubs.add(CLUB_SLUG_MAP[match.group(1)])
    return clubs


def _parse_briefs(html: str) -> list[dict]:
    briefs = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for brief in soup.select("div.brief[id]"):
            title_el = brief.select_one("h2.brief__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            body_el = brief.select_one("div.wysiwygContent")
            paragraphs = body_el.find_all("p") if body_el else []
            body = " ".join(p.get_text(" ", strip=True) for p in paragraphs)

            time_el = brief.select_one("time[datetime]")
            published_at = time_el.get("datetime") if time_el else None

            clubs = _clubs_from_logos(brief)
            if not clubs:
                clubs = detect_clubs(f"{title} {body}")
            if not clubs:
                continue

            briefs.append(
                {
                    "external_id": brief["id"],
                    "title": title,
                    "body": body or None,
                    "published_at": published_at,
                    "clubs": clubs,
                }
            )
        if not briefs:
            logger.warning("Nenhuma atualização relevante encontrada em %s", LIVE_URL)
    except Exception:
        logger.exception("Falha ao parsear o live blog — a estrutura pode ter mudado")
    return briefs


def _collect_all() -> list[NewsItem]:
    session = build_session()
    html = _fetch(session, LIVE_URL)
    if html is None:
        return []

    items = []
    for brief in _parse_briefs(html):
        for club in brief["clubs"]:
            items.append(
                NewsItem(
                    source=SOURCE_NAME,
                    external_id=brief["external_id"],
                    club=club,
                    title=brief["title"],
                    url=LIVE_URL,
                    published_at=brief["published_at"],
                    author="Foot Mercato",
                    summary=None,
                    body=brief["body"],
                    is_paywalled=False,
                )
            )
    return items


def collect(club: str, limit: int = 10) -> list[NewsItem]:
    all_items = _collect_all()
    club_items = [item for item in all_items if item.club == club]
    return club_items[:limit]

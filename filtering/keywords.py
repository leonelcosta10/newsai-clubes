"""Deteção de clube por palavras-chave, para fontes que não vêm pré-categorizadas
(ex: canal de Telegram do Fabrizio Romano). Fontes já segmentadas por clube,
como as páginas de tópico do ojogo.pt, não precisam disto.

Usa correspondência por limites de palavra (\\b) em vez de substring simples —
"oporto" como substring apanhava falsos positivos como "aeroporto" (aeroporto,
em italiano), por exemplo.
"""

import re

from config import CLUB_KEYWORDS

_CLUB_PATTERNS = {
    club: [re.compile(r"\b" + re.escape(variation) + r"\b", re.IGNORECASE) for variation in variations]
    for club, variations in CLUB_KEYWORDS.items()
}


def detect_clubs(text: str) -> set[str]:
    if not text:
        return set()
    matched = set()
    for club, patterns in _CLUB_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            matched.add(club)
    return matched

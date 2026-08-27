from dataclasses import dataclass, field

import requests

from config import USER_AGENT


@dataclass
class NewsItem:
    source: str  # ex: "ojogo", "dimarzio", "fabrizio_telegram"
    external_id: str  # identificador único dentro da fonte, usado para dedup
    club: str  # "fc_porto" | "benfica" | "sporting"
    title: str
    url: str
    published_at: str | None = None
    author: str | None = None
    summary: str | None = None  # lead/description curto, usado quando o corpo está bloqueado
    body: str | None = None  # texto completo, quando acessível
    is_paywalled: bool = False
    raw_meta: dict = field(default_factory=dict)
    llm_summary: str | None = None  # resumo gerado pelo Gemini, preenchido antes do envio
    bombast_score: int | None = None  # 0-10, "nível de notícia bombástica" avaliado pelo Gemini
    is_transfer_market: bool | None = None  # é sobre mercado de transferências? avaliado pelo Gemini


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session

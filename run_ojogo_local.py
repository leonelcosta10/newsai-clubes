"""Corre só o scraper do ojogo.pt, a partir deste PC (o ojogo.pt bloqueia pedidos
vindos dos IPs do GitHub Actions, por isso esta fonte não funciona na nuvem).

Partilha o mesmo repositório privado de dados (data/, clonado do
newsai-clubes-data) que o pipeline na nuvem usa, para não haver notícias
duplicadas entre os dois — ver storage/data_sync.py.
"""

import logging
import time

import settings
from config import CLUB_DISPLAY_NAMES, GEMINI_DELAY_SECONDS, MIN_BOMBAST_SCORE_TO_SEND
from logging_config import setup_logging
from notifier.telegram_bot import discover_new_recipients, is_configured, send_club_digest
from scrapers import ojogo
from storage import data_sync
from storage.dedup import is_seen, mark_seen
from summarizer.gemini_summarizer import is_configured as gemini_is_configured
from summarizer.gemini_summarizer import summarize

logger = logging.getLogger(__name__)


def run():
    setup_logging()
    logger.info("=== Início da execução local (só ojogo.pt) ===")

    data_sync.pull()

    active_clubs = settings.active_clubs()
    logger.info("Clubes ativos: %s", ", ".join(active_clubs) or "nenhum")

    if is_configured():
        for r in discover_new_recipients():
            logger.info("Novo destinatário inscrito via Telegram: %s (chat_id=%s)", r["name"], r["chat_id"])

    total_new = 0
    for club in active_clubs:
        logger.info("A recolher notícias do ojogo.pt para %s...", CLUB_DISPLAY_NAMES[club])
        items = ojogo.collect(club)
        new_items = [item for item in items if not is_seen(item.source, item.external_id)]
        logger.info("%d notícias novas do ojogo.pt para %s", len(new_items), CLUB_DISPLAY_NAMES[club])

        for item in new_items:
            result = summarize(item)
            if result:
                item.llm_summary = result["summary"]
                item.bombast_score = result["bombast_score"]
                item.is_transfer_market = result["is_transfer_market"]
            if gemini_is_configured():
                time.sleep(GEMINI_DELAY_SECONDS)

        items_to_send = [
            item
            for item in new_items
            if item.bombast_score is None or item.is_transfer_market or item.bombast_score >= MIN_BOMBAST_SCORE_TO_SEND
        ]
        skipped = len(new_items) - len(items_to_send)
        if skipped:
            logger.info(
                "%d notícia(s) não enviada(s) (fora do mercado e pontuação < %d)", skipped, MIN_BOMBAST_SCORE_TO_SEND
            )

        if items_to_send:
            sent = send_club_digest(CLUB_DISPLAY_NAMES[club], items_to_send)
            logger.info("%d mensagem(ns) enviada(s) para o Telegram (%s)", sent, CLUB_DISPLAY_NAMES[club])

        for item in new_items:
            mark_seen(item.source, item.external_id, club=club, title=item.title, url=item.url)
            total_new += 1

    data_sync.push("Atualiza estado do pipeline (local, ojogo.pt)")
    logger.info("=== Fim da execução local — %d notícias novas processadas ===", total_new)


if __name__ == "__main__":
    run()

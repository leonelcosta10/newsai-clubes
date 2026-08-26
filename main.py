"""Pipeline principal: recolha + resumo (Gemini) + dedup + envio por Telegram."""

import logging
import time

import settings
from config import CLUB_DISPLAY_NAMES, GEMINI_DELAY_SECONDS, MIN_BOMBAST_SCORE_TO_SEND
from logging_config import setup_logging
from notifier.telegram_bot import discover_new_recipients, is_configured, send_club_digest
from scrapers import abola, athletic, dimarzio, fabrizio_telegram, footmercato, gazzetta, lequipe, marca, ojogo, record
from storage import data_sync
from storage.dedup import is_seen, mark_seen
from summarizer.gemini_summarizer import is_configured as gemini_is_configured
from summarizer.gemini_summarizer import summarize

logger = logging.getLogger(__name__)

SCRAPER_REGISTRY = {
    "ojogo": ojogo,
    "abola": abola,
    "record": record,
    "dimarzio": dimarzio,
    "fabrizio_telegram": fabrizio_telegram,
    "athletic": athletic,
    "marca": marca,
    "lequipe": lequipe,
    "footmercato": footmercato,
    "gazzetta": gazzetta,
}


def run():
    setup_logging()
    logger.info("=== Início da execução ===")

    data_sync.pull()

    active_clubs = settings.active_clubs()
    active_scrapers = [SCRAPER_REGISTRY[name] for name in settings.active_sources()]
    logger.info("Clubes ativos: %s", ", ".join(active_clubs) or "nenhum")
    logger.info("Fontes ativas: %s", ", ".join(s.SOURCE_NAME for s in active_scrapers) or "nenhuma")

    if not is_configured():
        logger.warning(
            "Telegram não configurado (TELEGRAM_BOT_TOKEN em falta no .env) — "
            "as notícias vão ser recolhidas e marcadas como vistas, mas não enviadas"
        )
    else:
        new_recipients = discover_new_recipients()
        for r in new_recipients:
            logger.info("Novo destinatário inscrito via Telegram: %s (chat_id=%s)", r["name"], r["chat_id"])
    if not gemini_is_configured():
        logger.warning(
            "Gemini não configurado (GEMINI_API_KEY em falta no .env) — "
            "vai usar-se o resumo original da fonte em vez de um resumo gerado"
        )

    total_new = 0
    for club in active_clubs:
        club_new_items = []
        for scraper in active_scrapers:
            logger.info("A recolher notícias de %s para %s...", scraper.SOURCE_NAME, CLUB_DISPLAY_NAMES[club])
            items = scraper.collect(club)
            logger.info("%d notícias obtidas de %s para %s", len(items), scraper.SOURCE_NAME, CLUB_DISPLAY_NAMES[club])

            new_items = [item for item in items if not is_seen(item.source, item.external_id)]
            logger.info("%d são novas (%s)", len(new_items), scraper.SOURCE_NAME)
            club_new_items.extend(new_items)

        for item in club_new_items:
            result = summarize(item)
            if result:
                item.llm_summary = result["summary"]
                item.bombast_score = result["bombast_score"]
            if gemini_is_configured():
                time.sleep(GEMINI_DELAY_SECONDS)

        items_to_send = [
            item for item in club_new_items if item.bombast_score is None or item.bombast_score >= MIN_BOMBAST_SCORE_TO_SEND
        ]
        skipped = len(club_new_items) - len(items_to_send)
        if skipped:
            logger.info("%d notícia(s) de rotina não enviada(s) (pontuação < %d)", skipped, MIN_BOMBAST_SCORE_TO_SEND)

        if items_to_send:
            sent = send_club_digest(CLUB_DISPLAY_NAMES[club], items_to_send)
            logger.info("%d mensagem(ns) enviada(s) para o Telegram (%s)", sent, CLUB_DISPLAY_NAMES[club])

        for item in club_new_items:
            mark_seen(item.source, item.external_id, club=club, title=item.title, url=item.url)
            total_new += 1

    data_sync.push("Atualiza estado do pipeline")
    logger.info("=== Fim da execução — %d notícias novas processadas ===", total_new)


if __name__ == "__main__":
    run()

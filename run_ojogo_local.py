"""Corre só o scraper do ojogo.pt, a partir deste PC (o ojogo.pt bloqueia pedidos
vindos dos IPs do GitHub Actions, por isso esta fonte não funciona na nuvem).

Partilha o mesmo repositório privado de dados (data/, clonado do
newsai-clubes-data) que o pipeline na nuvem usa, para não haver notícias
duplicadas entre os dois. Por isso faz sempre `git pull` antes de processar
e `git push` depois de marcar as notícias como vistas.
"""

import logging
import subprocess
import time

import settings
from config import BASE_DIR, CLUB_DISPLAY_NAMES, GEMINI_DELAY_SECONDS
from logging_config import setup_logging
from notifier.telegram_bot import discover_new_recipients, is_configured, send_club_digest
from scrapers import ojogo
from storage.dedup import is_seen, mark_seen
from summarizer.gemini_summarizer import is_configured as gemini_is_configured
from summarizer.gemini_summarizer import summarize

logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "data"


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=DATA_DIR, capture_output=True, text=True)


def _sync_data_pull():
    result = _git("pull", "--rebase")
    if result.returncode != 0:
        logger.warning("git pull em data/ falhou: %s", result.stderr.strip())


def _sync_data_push():
    _git("add", "seen_articles.db", "recipients.json", "telegram_update_offset.txt")
    diff = _git("diff", "--staged", "--quiet")
    if diff.returncode == 0:
        return  # nada para commitar
    _git("commit", "-m", "Atualiza estado do pipeline (local, ojogo.pt)")
    push = _git("push")
    if push.returncode != 0:
        logger.warning("git push falhou, a tentar sincronizar e repetir: %s", push.stderr.strip())
        _git("pull", "--rebase")
        retry = _git("push")
        if retry.returncode != 0:
            logger.error("git push falhou de novo: %s", retry.stderr.strip())


def run():
    setup_logging()
    logger.info("=== Início da execução local (só ojogo.pt) ===")

    _sync_data_pull()

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
            if gemini_is_configured():
                time.sleep(GEMINI_DELAY_SECONDS)

        if new_items:
            sent = send_club_digest(CLUB_DISPLAY_NAMES[club], new_items)
            logger.info("%d mensagem(ns) enviada(s) para o Telegram (%s)", sent, CLUB_DISPLAY_NAMES[club])

        for item in new_items:
            mark_seen(item.source, item.external_id, club=club, title=item.title, url=item.url)
            total_new += 1

    _sync_data_push()
    logger.info("=== Fim da execução local — %d notícias novas processadas ===", total_new)


if __name__ == "__main__":
    run()

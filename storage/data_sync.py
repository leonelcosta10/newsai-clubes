"""Sincronização git da pasta data/ (clone do repositório privado newsai-clubes-data)
com o repositório remoto — usado pelos scripts que correm localmente (main.py,
run_ojogo_local.py) para partilharem o mesmo estado (dedup, destinatários) que
o pipeline na nuvem, evitando notícias duplicadas."""

import logging
import subprocess

from config import BASE_DIR

logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "data"
_TRACKED_FILES = ("seen_articles.db", "recipients.json", "telegram_update_offset.txt")


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=DATA_DIR, capture_output=True, text=True)


def pull():
    result = _git("pull", "--rebase")
    if result.returncode != 0:
        logger.warning("git pull em data/ falhou: %s", result.stderr.strip())


def push(commit_message: str):
    _git("add", *_TRACKED_FILES)
    diff = _git("diff", "--staged", "--quiet")
    if diff.returncode == 0:
        return  # nada para commitar

    _git("commit", "-m", commit_message)
    result = _git("push")
    if result.returncode != 0:
        logger.warning("git push falhou, a tentar sincronizar e repetir: %s", result.stderr.strip())
        _git("pull", "--rebase")
        retry = _git("push")
        if retry.returncode != 0:
            logger.error("git push falhou de novo: %s", retry.stderr.strip())
